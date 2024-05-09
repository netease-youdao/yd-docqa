import os
import traceback
import redis
import random
from datetime import datetime
import json
from concurrent.futures import ThreadPoolExecutor
import time
import requests
import base64
from PIL import Image
from io import BytesIO
#  from nltk.tokenize import sent_tokenize
import re

import json
import urllib
import urllib.request
import urllib.parse
from configs.cur_config import *
from kernel.utils import *
from kernel.llm import *
from kernel.summary import *
from kernel.parse_pdf import *
from kernel.global_vars import *
from qanything_kernel.utils.custom_log import debug_logger

from flask import g
from flask import current_app

from langchain.vectorstores import FAISS

executor_q = ThreadPoolExecutor(max_workers=24)

import heapq
import numpy as np
from scipy.spatial.distance import cosine


def get_paper_title_when_using_vdb(redis_client, doc_id):
    kk = str((doc_id, "DOC_INFO", PARSE_SERVICE_VERSION))
    try:
        if not redis_client.exists(kk):
            return "", "Invalid_doc, fail to get DOC_INFO."
        doc_info_json_str = redis_client.get(kk)
        if not doc_info_json_str:
            return "", "Invalid_doc, DOC_INFO empty."
        doc_info = json.loads(doc_info_json_str)
        return doc_info['title'], None
    except:
        return "", "Redis connection failed. Exception caught."

def get_paper_title_from_parseResult(redis_client, doc_id):
    # 先从 redis 尝试获取 title。如果拿不到，说明 redis 数据被干掉了。那就重新从 nos 上下载文章解析结果，从中提取 title。
    title, error_msg = get_paper_title_when_using_vdb(redis_client, doc_id)
    return title, error_msg


def modify_query_by_chatgpt_decomposing_query_when_using_vdb(redis_client, doc_id, q, history=[], db_conn_pool=None, parent_req_info=None, is_monitoring=False):
    title, _error_msg = get_paper_title_from_parseResult(redis_client, doc_id)

    # 先控制一下prompt总token数。
    # 优先删 history 内容。
    q_tokens = num_tokens_from_messages([q])
    while q_tokens > MAX_TOKENS_FOR_REFERENCE_INFORMATION:
        q = q[:int(len(q) * 0.8)]
        q_tokens = num_tokens_from_messages([q])
    history_tokens = num_tokens_from_messages([f"{json.dumps(history, indent=4, ensure_ascii=False)}"])
    while history_tokens + q_tokens > MAX_TOKENS_FOR_REFERENCE_INFORMATION:
        history = history[:-1]
        history_tokens = num_tokens_from_messages([f"{json.dumps(history, indent=4, ensure_ascii=False)}"])

    if not history:
        prompt = f"""
用户在阅读一篇名为《{title}》的文档时提出了这个问题：“{q}”
我现在需要通过这个问题的 embedding 去索引文档中相应的内容，但由于这个问法可能太过宽泛，索引不到。所以需要你在当前问题比较宽泛时，根据这个问题的内涵和外延，帮我把这个问题改造成一到两个更明确的问题，不要引入额外的信息。改写时，避免思维过于发散，而是要确保改写后的问题与用户的原问题含义紧密相关。而且改写时，尽量避免写成一般疑问句即“是否怎样怎样”之类的问题。只输出你改造后的问题，每个问题占一行，且每行中避免带标号，要只包括问题本身。
        """
    else: # 有有效的聊天记录时，就让 LLM 来判断是否只针对聊天记录做后续的流式回答
        prompt = f"""
你是我的阅读助手，可以帮助我快速阅读和理解文档。
我正在阅读的文档标题是《{title}》。
你要牢记，咱们俩凡是提到“本文”、“这篇文档”之类的表达，都是指的它，即《{title}》。
---
咱俩刚才的对话片段如下：
{json.dumps(history, indent=4, ensure_ascii=False)}
---
下面我提出新的问题或指令，你需要判断是否需要其他信息来回复我。如果我的问题或指令是仅仅针对刚才咱俩对话的内容的，比如“翻译成中文”、“我都问了哪些问题？”、“你说得不太对”之类的，那你就直接输出“{SYMBOL_NO_NEED_TO_REWRITE_QUERY}”。而其他一切情况下，你都要把我的问题或指令改写成两个问题或句子，我会用你输出的内容去做embedding相似度检索，从文档中检索一些片段出来供你参考，所以你要确保你输出的这两个问题或句子是与我的原始问题或指令的内涵和外延紧密相关的。
---
我的新问题或指令：
{q}
---
你输出的内容：

        """

    if is_monitoring:
        prompt = 'Say Hi'
    loop = asyncio.get_event_loop()
    res = loop.run_until_complete(get_async_llm_answer(llm, prompt, history=[], streaming=False))

    res_jso = {
        'prompt': prompt,
        'modified_query': res,
        'title': title,
        'orig_query': q,
        'history': history
    }
    debug_logger.info(f'[modified_query] {json.dumps(res_jso, ensure_ascii=False)}')

    # 与原始问题拼接成新的 query。
    return res

def construct_prompt_on_vdb(redis_client, doc_id, msg, ocr_res, lang, history=[], vdb=None, q_type=0, db_conn_pool=None, parent_req_info=None, is_monitoring=False):
    picked_citations = []

    if (not ocr_res) and q_type == 1: # 走"选中解释"的逻辑，则把 ocr_res 与 msg 对调。
        ocr_res = msg
        msg = ""

    # 查库
    # 先改写问题。
    orig_query = msg
    all_questions = []
    if orig_query:
        LLM_output = modify_query_by_chatgpt_decomposing_query_when_using_vdb(redis_client, doc_id, orig_query, history=history, db_conn_pool=db_conn_pool, parent_req_info=parent_req_info, is_monitoring=is_monitoring)
        if LLM_output.find(SYMBOL_NO_NEED_TO_REWRITE_QUERY) > -1:
            # 说明不需要改写问题，而是应该直接依赖聊天记录来对话。
            # 那就不再需要检索相关片段了吧？
            return orig_query, [], picked_citations
        else:
            # 需要改写问题，那就把改写后的问题解析出来，走旧有的单轮问答逻辑即可。
            mod_queries = LLM_output.split('\n')
            if len(mod_queries) >= 2:
                mod_query = ' '.join(mod_queries[-2:])
            else:
                mod_query = LLM_output
            all_questions.extend([orig_query, mod_query])
    if ocr_res:
        all_questions.append(ocr_res)
    dynamic_k = 10 // len(all_questions) if all_questions else 10
    docs = []
    picked_chunks_infos = set([])
    topk_pieces = []
    total_token_num = 0
    # 改成并发。拿到所有结果后再统一排序、去重。
    token_exceeded = False
    for q in all_questions:
        if token_exceeded:
            break
        docs_by_orig_query = vdb.max_marginal_relevance_search(q, k=dynamic_k) # k=4
        for _doc in docs_by_orig_query:
            cur_chunk_key = (_doc.metadata["doc_id"], _doc.metadata["source"]["chunk_id"])
            cur_chunk_token_num = num_tokens_from_messages([_doc.metadata["chunk_info"]["enriched_text"]])
            if cur_chunk_token_num + total_token_num > MAX_TOKENS_FOR_REFERENCE_INFORMATION:
                token_exceeded = True
            if cur_chunk_key not in picked_chunks_infos :
                docs.append(_doc)
                picked_chunks_infos.add(cur_chunk_key)
                topk_pieces.append(_doc.metadata["chunk_info"]["enriched_text"])
                total_token_num += cur_chunk_token_num
    
    # # [20231225] 加入 rerank
    # try:
    #     topk_pieces = rerank_prompt(orig_query, topk_pieces)
    # except:
    #     print(f'[{cur_func_name()}] traceback = {traceback.format_exc()}')

    seg = "\n"
    information = f"{seg.join(topk_pieces)}"

    language = 'English' if lang=='en' else 'Chinese'
    i_dont_know = "I don't know" if lang=='en' else '我不知道。'

    # 先拿到文章 title
    title, _error_msg = get_paper_title_from_parseResult(redis_client, doc_id)

    if msg:
        # 限制一下各部分的总 token 数。information + msg 应该总共不超过 2400 token
        information_tokens = num_tokens_from_messages([information])
        msg_tokens = num_tokens_from_messages([msg])
        while msg_tokens > MAX_TOKENS_FOR_REFERENCE_INFORMATION:
            msg = msg[:int(len(msg) * 0.8)]
            msg_tokens = num_tokens_from_messages([msg])
        while information_tokens + msg_tokens > MAX_TOKENS_FOR_REFERENCE_INFORMATION:
            # 如果超了，就优先砍 information，除非 msg 太长，msg 本身已经超出 MAX_TOKENS_FOR_REFERENCE_INFORMATION
            information = information[:int(len(information) * 0.8)]
            information_tokens = num_tokens_from_messages([information])

        content = f"""
参考信息：
本文标题为《{title}》
{information}
---
我的问题或指令：
{msg}
---
辅助问题：
{mod_query}
---
请根据上述辅助问题的启发，回答我的问题或回复我的指令。前面的参考信息和辅助问题，可能有用，也可能没用，你需要从我给出的参考信息中选出与我的问题最相关的那些，来为你的回答提供依据。如果你发现我给出的辅助问题没啥用，就不要参考这些辅助问题。如果仅依赖我给定的参考信息，不足以回答我的问题的话，你就直接说“对不起，我不知道”，而不要胡乱编造，特别是涉及数据、日期等等事实性问题时，一定要确保你的回答是完全基于我给的参考信息的。
你的回复（用{'英文' if language == 'English' else '中文'}）：
        """
    else:
        information_tokens = num_tokens_from_messages([information])
        ocr_res_tokens = num_tokens_from_messages([ocr_res])
        while ocr_res_tokens > MAX_TOKENS_FOR_REFERENCE_INFORMATION:
            ocr_res = ocr_res[:int(len(ocr_res) * 0.8)]
            ocr_res_tokens = num_tokens_from_messages([ocr_res])
        while information_tokens + ocr_res_tokens > MAX_TOKENS_FOR_REFERENCE_INFORMATION:
            # 如果超了，就优先砍 information，除非 msg 太长，msg 本身已经超出 MAX_TOKENS_FOR_REFERENCE_INFORMATION
            information = information[:int(len(information) * 0.8)]
            information_tokens = num_tokens_from_messages([information])
        content = f"""
参考信息：
本文标题为《{title}》
{information}
---
待解释的话：
{ocr_res}
---
待解释的话，我看不懂，请你帮我解释一下。前面的参考信息可能有用，也可能没用。如果你发现我给出的信息和待解释的话没啥关系，就不要参考这些参考信息。如果你不知道答案，就说不知道，不要瞎编。
你的解释（用{'英文' if language == 'English' else '中文'}）：
        """

    return content, docs, picked_citations


def parse_OCR_res(js):
    if js["Status"] == "error":
        return ""
    jr = js['Result']
    regions = jr["regions"]
    all_text = ""
    for r in regions:
        lines = r['lines']
        region_text = ""
        for line in lines:
            text = line["text"]
            if len(region_text) == 0:
                region_text += text
            elif region_text[-1] != '-':
                region_text += ' ' + text
            else:
                region_text = region_text[:-1] + text
        all_text += region_text + "\n"
    return all_text

def save_ocr_img(b64):
    # 解码图片
    img_data = img_data.encode('utf-8')
    img_data = base64.b64decode(img_data)

    # 转换为PIL Image对象
    img = Image.open(BytesIO(img_data))

    # 保存图片
    # 获取当前时间
    now = datetime.now()
    timestamp = datetime.timestamp(now)
    img.save(f'{int(timestamp)}.jpg')


def request_OCR(b64):
    data = {
        'img': b64,
        # 'uid': 'youdaoocr',
        # 'type': '10012',
        'options': ''
    }
    d = urllib.parse.urlencode(data).encode(encoding='UTF8')  # 字典 data 中保存请求数据，包括输入图片和请求参数等

    if DEBUG_SAVE_OCR_IMG:
        save_ocr_img(b64)

    f = urllib.request.urlopen(
        url = 'http://api2.ocr.youdao.com/accurate_ocr',
        data = d
    )
    s = f.read()
    js = json.loads(str(s, 'utf-8'))
    js['Result'] = json.loads(js['Result'])

    OCR_text = parse_OCR_res(js)
    return OCR_text


def search_real_reference_chunks_on_vdb(redis_client, doc_id, answer, vdb):
    recalled_info_jsons = []
    docs_by_orig_query = vdb.similarity_search_with_score(answer, k=5) # k=4
    top1_score = 99.0
    for ii, (_doc, score) in enumerate(docs_by_orig_query):
        if (score > 0.5): # vdb 默认用的是 l2 距离作为 score。越小越好。大于阈值的就说明相关性很差了，不要了就。
            break
        if score - top1_score > 0.2:
            break
        recalled_info_jsons.append(_doc)
        if ii == 0:
            top1_score = score

    return recalled_info_jsons


def get_history_short_enough(redis_client, user_id, doc_id, prompt, max_tokens_num=4000):
    kk = f'{user_id}__{doc_id}__HISTORY'
    debug_logger.debug(f'[get_history_short_enough] user_id = {user_id}')
    debug_logger.debug(f'[get_history_short_enough] doc_id = {doc_id}')
    debug_logger.debug(f'[get_history_short_enough] kk = {kk}')
    if not redis_client.exists(kk):
        debug_logger.debug(f'[get_history_short_enough] key not exists: {kk}')
        return []

    # 先统计prompt消耗的 token数。
    prompt_token_num = num_tokens_from_messages([prompt]) if prompt else 0

    # 再从 redis 中取出数据。倒序遍历，能取几个取几个。根据 token_num 字段的值来累加。但注意最终返回的 history 中的项们不要包含 token_num 字段。
    history_from_redis = redis_client.lrange(kk, 0, -1)
    picked_cnt = 0
    res = []
    total_token_num = prompt_token_num
    for h_bytes in history_from_redis[::-1]:
        h = json.loads(h_bytes)
        if h['token_num'] + total_token_num > max_tokens_num:
            break
        res.append({
            'role': h['role'],
            'content': h['content']
        })
        picked_cnt += 1
        total_token_num += h['token_num']

    return res[::-1][-2:] # [20231122] 只保留最后一次问答的历史吧，留的太多的话，容易误导问题改写环节。


def save_current_qa_into_history(redis_client, user_id, doc_id, user_query, ocr_res_text, q_type, answer):
    kk = f'{user_id}__{doc_id}__HISTORY'

    if ocr_res_text: # 截图解释
        query_content = f"""帮我解释下面这些从图中识别出来的内容：
        {ocr_res_text}"""
    elif q_type == 1: # 选中文字解释
        query_content = f"""帮我解释下面这段话：
        {user_query}"""
    else: # 常规问答
        query_content = user_query
    cur_query_json = {}
    cur_query_json['role'] = 'user'
    cur_query_json['content'] = query_content
    cur_query_json['token_num'] = num_tokens_from_messages([query_content])
    cur_query_json_str = json.dumps(cur_query_json, ensure_ascii=False)
    redis_client.rpush(kk, cur_query_json_str)
    debug_logger.info(f'[save_current_qa_into_history] pushed history to {kk}: {(cur_query_json_str)}')

    cur_answer_json = {}
    cur_answer_json['role'] = 'assistant'
    cur_answer_json['content'] = answer
    cur_answer_json['token_num'] = num_tokens_from_messages([answer])
    cur_answer_json_str = json.dumps(cur_answer_json, ensure_ascii=False)
    redis_client.rpush(kk, cur_answer_json_str)
    debug_logger.info(f'[save_current_qa_into_history] pushed history to {kk}: {(cur_answer_json_str)}')


# 流式接口
async def stream_query_on_doc_vdb(redis_client, jso, vdb=None, parent_req_info=None, db_conn_pool=None):
    if "doc_id" not in jso:
        error_msg = "No doc_id specified."
        data_json = {
            "error": error_msg
        }
        yield f"event: error\ndata: {json.dumps(data_json, ensure_ascii=False)}\n\n"
    doc_id = jso.get("doc_id")

    lang = jso.get("lang", "zh")
    attachment = jso.get("attachment", "")
    q_type = jso.get("q_type", 0)
    is_monitoring = jso.get("is_monitoring", False)
    user_id = jso.get("user_id", None) 
    stream_json = jso.get("stream_json", False) # 请求时是否指定返回的流式片段中的正文被json包起来

    ocr_res_text = ""
    error = "OK"
    if attachment: # 当前带图片，需要请求OCR服务
        try:
            ocr_res_text = request_OCR(attachment)
            debug_logger.info(f'[stream_query_on_doc_vdb] ocr_res_text: {ocr_res_text}')
        except:
            answer = "图片不含有效文字，或图片格式不合法"
            error = "Invalid img."
            data_json = {
                "error": error
            }
            debug_logger.error(f'[stream_query_on_doc_vdb] ocr failed: {answer}')
            yield f"event: error\ndata: {json.dumps(data_json, ensure_ascii=False)}\n\n"

    msg_text = jso.get("message")
    # 拼成prompt，请求LLM
    history_for_query_understanding = get_history_short_enough(redis_client, user_id, doc_id, prompt=None, max_tokens_num=2000) # 先拿到一些历史记录，便于让LLM判断当前用户问题是否依赖历史聊天记录。
    prompt, found_docs, picked_citations = construct_prompt_on_vdb(redis_client, doc_id, msg_text, ocr_res_text, lang, history=history_for_query_understanding, vdb=vdb, q_type=q_type, db_conn_pool=db_conn_pool, parent_req_info=parent_req_info)
    if is_monitoring:
        prompt = "Say Hi"

    if user_id is not None:
        history = get_history_short_enough(redis_client, user_id, doc_id, prompt, max_tokens_num=MAX_TOKENS_FOR_HISTORY)
    else:
        history = []

    debug_logger.info(f'[stream_query_on_doc_vdb] got history: {json.dumps(history, indent=4, ensure_ascii=False)}')

    answer = ""
    try:
        async for piece_obj in llm.generatorAnswer(prompt, history=history, streaming=True):
            piece = piece_obj.llm_output['answer']
            if piece.startswith("data: [DONE]"):
                break
            # if len(piece) >= 6 and piece.startswith("data:"):
            pure_piece = json.loads(piece[6:])['answer']
            # answer += (piece[6:].replace('\n\n', '')) # 跳过开头的 data: ，把有效内容拼起来，以期获得完整的答案，备用（主要可用于后续拿答案重新过滤“信息来源”列表）
            answer += (pure_piece.replace('\n\n', '')) # 跳过开头的 data: ，把有效内容拼起来，以期获得完整的答案，备用（主要可用于后续拿答案重新过滤“信息来源”列表）

            if stream_json:
                data_to_yield = {
                    # 'content': piece[6:-2]
                    'content': json.loads(piece[6:])['answer']
                }
                piece_to_yield = json.dumps(data_to_yield, ensure_ascii=False)
                yield f'data: {piece_to_yield}\n\n'
            else:
                yield pure_piece
    except:
        error = "LLM Service refused this request, please retry several seconds later."
        traceback.print_exc()
        debug_logger.info(traceback.format_exc())
        data_json = {
            "error": error
        }
        yield f"event: error\ndata: {json.dumps(data_json, ensure_ascii=False)}\n\n"

    # 把历史记录存 redis，主要就是本次的对话和答案。
    try:
        if user_id is not None:
            save_current_qa_into_history(redis_client, user_id=user_id, doc_id=doc_id, user_query=msg_text, ocr_res_text=ocr_res_text, q_type=q_type, answer=answer)
    except:
        traceback.print_exc()
        debug_logger.info(traceback.format_exc())

    # 增加日志记录：1.确保所有回答“我不知道”的问题，其query召回的原文片段都被记录在日志中；2.其他有正常答案的问题，随机抽10%，记录其召回原文片段。
    query_infos_json = {}
    query_infos_json['prompt'] = prompt
    query_infos_json['answer'] = answer
    query_infos_json['doc_id'] = doc_id
    query_infos_json['orig_query'] = msg_text
    query_infos_json['lang'] = lang
    query_infos_json['attatchment_base64'] = attachment
    query_infos_json['recalled'] = found_docs

    #  # 用拼接出来的完整 answer，重新搜一下全文，找到真正有价值的参考信息们，放在最后的片段中返回给用户。
    debug_logger.info(f'[stream_query_on_doc] prompt = {prompt}, answer = {answer}, doc_id = {doc_id}')
    res_jso = {
        'prompt': prompt,
        'answer': answer,
        'doc_id': doc_id,
        'orig_query': msg_text,
        'lang': lang
    }
    debug_logger.info(f'[stream_query_on_doc] {json.dumps(res_jso, ensure_ascii=False)}')
    # [20230529] 为了改善一大段综合答案直接检索时可能置信度不够高的问题，尝试把它分句再逐个去检索。最终与整段检索得到的结果合并。
    sent_tokenize_list = sent_tokenize(answer)

    answer_sentences = [answer]
    answer_sentences.extend(sent_tokenize_list)
    params_list = []
    for s in answer_sentences:
        params_list.append((redis_client, doc_id, s, vdb))
    futures = []
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(search_real_reference_chunks_on_vdb, *args) for args in params_list]

    final_recalled_jsons = []
    for fu in futures:
        final_recalled_jsons.extend(fu.result())


    # 发送一个 end 事件，告诉客户端关闭连接，并附上回答的证据信息来源

    # 当有效信息源是虚拟段落（人为合并出来的段落）时，需要换算成原始 chunk_id，以便前端高亮渲染
    sources = []

    for doc in final_recalled_jsons:
        # 要拿到 page_id 和 clickable_chunk_id
        _doc_id = doc.metadata["doc_id"]
        _chunk = doc.metadata["chunk_info"]
        _source = doc.metadata["source"]
        debug_logger.info(f'[stream_query_on_doc_vdb][final_recalled_jsons] _chunk = {json.dumps(_chunk, indent=4, ensure_ascii=False)}')
        chunk_id = _source["chunk_id"]
        debug_logger.info(f'[stream_query_on_doc_vdb][final_recalled_jsons] chunk_id = {chunk_id}')
        clickable_chunk_ids = _source["clickable_chunk_ids"]
        for clickable_chunk_id in clickable_chunk_ids:
            sources.append({
                "doc_id": _doc_id,
                "chunk_id": clickable_chunk_id,
                "_inside_chunk_id": chunk_id,
                "clickable_chunk_id": clickable_chunk_id,
                "page_id": _source['page_id']
            })

    # 对chunk去重
    distinct_sources = []
    distinct_docid_and_chunkid_set = set()

    if not picked_citations:
        for ss in sources:
            cur_src = (ss['doc_id'], ss['chunk_id'])
            if cur_src in distinct_docid_and_chunkid_set:
                continue
            distinct_sources.append(ss)
            distinct_docid_and_chunkid_set.add(cur_src)

    yield 'event: docsrc\ndata: {}\n\n\n'.format(json.dumps(
        {
            'sources': distinct_sources
        }))

    yield 'event: end\ndata: {}\n\n'.format(json.dumps(
        {
            'message': 'Connection closed',
            'sources': distinct_sources
        }))

def norm_str(line):
    # 统一小写化，去除空格，只保留英文字符
    new_line = []
    line = line.lower()
    for ch in list(line):
        if ch.isalpha() or ch.isnumeric():
            new_line.append(ch)
    return ''.join(new_line)
