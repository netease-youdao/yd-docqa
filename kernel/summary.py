import asyncio
import redis
import json
from concurrent.futures import ThreadPoolExecutor
import time
import requests
import urllib
import urllib.request
import urllib.parse
from kernel.llm import *
from .llm import *
from kernel.llm import *
from qanything_kernel.utils.custom_log import debug_logger

executor = ThreadPoolExecutor(max_workers=8)



def request_remote_summary(redis_client, orig_text, llm=None):
    content = f"{orig_text} \n\n---\n你现在是一个文本摘要生成器，你要用超级超级精简的话，用中文提炼上面这段文字的要点，一定不要啰嗦，一定要精简！一定要用中文！\n中文摘要："
    reply_answer = asyncio.run(get_async_llm_answer(llm, content, history=[], streaming=False))
    return reply_answer, None

def check_doc_id(redis_client, doc_id):
    if redis_client.exists(doc_id):
        return True
    return False

def check_chunk_id(redis_client, doc_id, chunk_id):
    if redis_client.exists(str((doc_id, chunk_id))):
        return True
    return False

def update_summary(redis_client, doc_id, chunk_id, llm):
    # 由于线程池的限制，当前这个任务可能已经排队很久了，那它进来的时候，有可能前面已经有同一块chunk被做完了摘要。所以先检查一下，如果已经Done了，就不再重复请求LLM。
    k_summary_state = str((doc_id, chunk_id, "SUMMARY_STATE"))
    retried_times = 0
    if redis_client.exists(k_summary_state):
        retried_times = int(redis_client.get(k_summary_state)) # 表示重试次数。0表示当前还没进行过LLM请求，或需要再次进行LLM请求。最多到3，到3时会重置为0，并重新请求一次LLM服务。而当获得了LLM返回的结果后，置为-1，表示Done。
    if retried_times == -1:
        return
    debug_logger.info(f'[] retried_times = {retried_times}, not -1, so call LLM.')

    # 先拿到 chunk 原文
    chunk_json = json.loads(redis_client.get(str((doc_id, chunk_id))))
    orig_text = chunk_json["text"]
    # 再请求 LLM，获得其摘要
    summary_text, __ = request_remote_summary(redis_client, orig_text, llm)

    # 把摘要写入 redis
    chunk_json["summary"] = {
        "tldr": summary_text,
        "state": "Done"
    }
    redis_client.set(str((doc_id, chunk_id)), json.dumps(chunk_json))

    # 为了避免上面这句写入 tldr 到 redis 时失败，使得当前 chunk 的摘要陷入永远 Doing 的状态。需要先从 redis 读一下，看看是否有 tldr 字段。如果有，说明已经完成了摘要的请求了。此时才能把 k_summary_state 置为 -1，表示 Done。
    chunk_json = json.loads(redis_client.get(str((doc_id, chunk_id))))
    if 'summary' in chunk_json and 'tldr' in chunk_json['summary'] and chunk_json['summary']['tldr'] != "":
        redis_client.set(k_summary_state, -1)

def get_summary_of_1_chunk(redis_client, doc_id, chunk_id, llm, initing=False):
    # 先检查 doc_id 和 chunk_id 的合法性。
    doc_id_valid = check_doc_id(redis_client, doc_id)
    if not doc_id_valid:
        return None, "Invalid_doc"
    chunk_id_valid = check_chunk_id(redis_client, doc_id, chunk_id)
    if not chunk_id_valid:
        return None, "Invalid_chunk"

    # 根据 doc_id + chunk_id，查库。
    k = str((doc_id, chunk_id))
    chunk_json_str = redis_client.get(k).decode('utf-8')
    chunk_json = json.loads(chunk_json_str)
    if "summary_status" in chunk_json and (chunk_json["summary_status"] == 0):
        return None, "Invalid_chunk"

    summary_json = chunk_json['summary']
    k_summary_state = str((doc_id, chunk_id, "SUMMARY_STATE"))
    if initing: # 如果在对当前 doc_id 对应的摘要进行初始化，则需要重置这些 k_summary_state，以避免曾经做过这篇的摘要，导致这里的状态仍然记着 -1，使得该段落无法被重新触发摘要。
        redis_client.set(k_summary_state, 0)

    retried_times = 0
    if redis_client.exists(k_summary_state):
        retried_times = int(redis_client.get(k_summary_state)) # 表示重试次数。0表示当前还没进行过LLM请求，或需要再次进行LLM请求。最多到3，到3时会重置为0，并重新请求一次LLM服务。而当获得了LLM返回的结果后，置为-1，表示Done。
    debug_logger.info(f'[get_summary_of_1_chunk] retried_times = {retried_times}')

    if 'tldr' in summary_json and summary_json['tldr'] != "": # 也即 retried_times == -1
        return chunk_json["summary"], "Done"
    elif retried_times > 0:
        # 至此，说明已经有正在进行中的摘要请求了，无需重新请求。
        retried_times += 1
        if retried_times > 3:
            retried_times = 0

        redis_client.set(k_summary_state, retried_times) # 表示重试次数。最多到3，到3时会重置为0，并重新请求一次LLM服务。而当获得了LLM返回的结果后，置为-1，表示Done。

    if retried_times == 0:
        # 至此，说明是首次请求当前 chunk 的摘要。开个线程去后台做。
        # 提交任务到线程池中
        _args = [redis_client, doc_id, chunk_id, llm]
        future = executor.submit(lambda p: update_summary(*p), _args)
        debug_logger.info(f'[] submitted a summary request: chunk {chunk_id} ')

        redis_client.set(str((doc_id, chunk_id, "SUMMARY_STATE")), 1) # 表示重试次数。最多到3，到3时会重置为0，并重新请求一次LLM服务。而当获得了LLM返回的结果后，置为-1，表示Done。
    return None, "Doing"

def do_summarize_for_doc(redis_client, doc_id, llm):
    if redis_client.exists(str((doc_id, 'TEXT_CHUNK_IDS'))):
        chunk_ids = json.loads(redis_client.get(str((doc_id, 'TEXT_CHUNK_IDS'))))
        for chunk_id in chunk_ids:
            get_summary_of_1_chunk(redis_client, doc_id, chunk_id, llm, initing=True)
