from abc import ABC, abstractmethod
import json
import random
from typing import List, Optional, Any
import traceback

from qanything_kernel.utils.custom_log import debug_logger
from langchain.docstore.document import Document
from langchain.document_loaders.base import BaseLoader
from configs.cur_config import PARSE_SERVICE_VERSION
from kernel.utils import *

from kernel.global_vars import llm



def is_chunk_clickable(chunk):
    if chunk["chunk_type"] == "normal":
        return True
    return False

class PdfChunksLoader(BaseLoader):
    """
    v1.0.0 Document 先实现为 一个 chunk 一个 Document。
    """
    def __init__(self, doc_id: str, redis_client: Any, chunks_json: dict):
        super().__init__()
        self.doc_id = doc_id
        self.chunks_json = chunks_json
        self.redis_client = redis_client

    def parse_doc_info_and_save_to_redis(self):
        # 先解析出大标题吧。以后再考虑什么摘要之类的。
        title = ""
        for i, chunk in enumerate(self.chunks_json):
            if chunk["chunk_type"] == "title": # 说明是大标题
                title = chunk["text"]
                break

        # 随机找几段文字多的，用于生成脑暴问题。
        NUM_TO_RETURN = 4
        candidates = []
        for i, chunk in enumerate(self.chunks_json):
            if "chunk_type" in chunk and chunk["chunk_type"] == "normal":
                if len(chunk["text"]) > 160:
                    candidates.append(chunk["text"])
        chunks_for_brainstorm_questions = random.sample(candidates, min(len(candidates), NUM_TO_RETURN))

        doc_info = {
            "title": title,
            "chunks_for_brainstorm_questions": chunks_for_brainstorm_questions,
        }
        doc_info_str = json.dumps(doc_info)
        try:
            self.redis_client.set(str((self.doc_id, "DOC_INFO", PARSE_SERVICE_VERSION)), doc_info_str)
            debug_logger.info(f'[{cur_func_name()}] successfully set DOC_INFO into Redis, kk = {str((self.doc_id, "DOC_INFO", PARSE_SERVICE_VERSION))}')
        except:
            debug_logger.info(f'[{cur_func_name()}] traceback = {traceback.format_exc()}')


    """
    最终往 prompt 里拼的，应该是 doc.metadata["chunk_info"]["enriched_text"]
    """
    def load(self) -> List[Document]:
        res = []

        max_page_id = -1
        chunk_ids = []
        chunks = self.chunks_json
        for i, chunk in enumerate(self.chunks_json):
            chunk_id = chunk["chunk_id"]
            chunk_ids.append(chunk_id)
            try:
                page_id = int(chunk['locations'][0]['page_id'])
            except:
                debug_logger.debug(f'[DEBUG0422] traceback = {traceback.format_exc()}')
                debug_logger.debug(f'[DEBUG0422] chunk = {json.dumps(chunk, indent=4, ensure_ascii=False)}')
            max_page_id = max(max_page_id, page_id)

            # 需要扩充一下 chunk 内容。从原来的 text 字段，变更为  real_text 和 text_for_prompt 两部分，前者是真实内容，后者是向上下扩展一两段的结果
            chunk["real_text"] = chunk["text"]
            enriched_text = ""
            if i - 1 >= 0:
                pre_1_chunk = chunks[i-1]["text"]
                enriched_text = pre_1_chunk
            enriched_text += chunk["text"]
            if i + 1 < len(chunks):
                enriched_text += chunks[i+1]["text"]


            chunk["enriched_text"] = enriched_text
            chunk['enriched_text_tokens'] = llm.num_tokens_from_messages([enriched_text])
            page_id = chunk["locations"][0]["page_id"]
            res.append(Document(
                page_content = chunk["text"],
                metadata = {
                    "doc_id": self.doc_id,
                    "chunk_info": chunk,
                    "source": {
                        # "filename": self.filename,
                        "doc_id":self.doc_id,
                        "chunk_id": chunk["chunk_id"],
                        "clickable_chunk_ids": [chunk["chunk_id"]] if is_chunk_clickable(chunk) else [],
                        "page_id": page_id # 第一个真实段落的起点所在的页码，从0开始计数
                    }
                },
            ))

        ################## 至此是所有的原始 chunk #################
        if len(chunk_ids) < 1200 and max_page_id <= 40: # 超过40页的，连VIRT都可以不要了。
            # 接下来要把段落们合并后构成的虚拟段落也加入数据库，用于问答时的检索，提高正确参考信息的召回率。
            MAX_MERGED_CHUNK_LEN_LIST = [100, 200, 300, 500]#, 1000]
            virtual_chunk_ids = []
            virtual_index = 0
            used_orig_chunkids_set = set()
            for MAX_MERGED_CHUNK_LEN in MAX_MERGED_CHUNK_LEN_LIST:
                for i in range(0, len(chunks)):
                    start_id = i
                    start_chunk = chunks[i]
                    merged_chunk_ids = [i]
                    clickable_chunk_ids = []
                    if is_chunk_clickable(start_chunk):
                        clickable_chunk_ids.append(start_chunk["chunk_id"])
                    page_id = start_chunk["locations"][0]["page_id"]

                    merged_text = start_chunk["text"]
                    for j in range(i + 1, len(chunks)):
                        cur_chunk = chunks[j]
                        cur_chunk_len = len(cur_chunk['text'])
                        if len(merged_text) + cur_chunk_len < MAX_MERGED_CHUNK_LEN:
                            merged_chunk_ids.append(j)
                            if is_chunk_clickable(cur_chunk):
                                clickable_chunk_ids.append(cur_chunk["chunk_id"])
                            merged_text += cur_chunk['text']
                        else:
                            break
                    if len(merged_chunk_ids) <= 1: # 即当前段落够长了，未进行有效合并。
                        continue
                    if tuple(merged_chunk_ids) in used_orig_chunkids_set:
                        continue
                    # 以 virtual chunk 的名字，加入 redis
                    virtual_index += 1
                    virtual_chunk_id = f'VIRT-{virtual_index}'
                    virtual_chunk_ids.append(virtual_chunk_id)
                    virtual_chunk = {
                        "text": merged_text,
                        "real_text": merged_text,
                        "enriched_text": merged_text,
                        "enriched_text_tokens": llm.num_tokens_from_messages([merged_text]),
                        "real_chunk_ids": merged_chunk_ids
                    }
                    res.append(Document(
                        page_content = virtual_chunk["real_text"],
                        metadata = {
                            "doc_id": self.doc_id,
                            "chunk_info": virtual_chunk,
                            "source": {
                                # "filename": self.filename,
                                "doc_id":self.doc_id,
                                "chunk_id": virtual_chunk_id,
                                "clickable_chunk_ids": clickable_chunk_ids,
                                "page_id": page_id # 第一个真实段落的起点所在的页码，从0开始计数
                            }
                        },
                    ))
                    used_orig_chunkids_set.add(tuple(merged_chunk_ids))

            # 把真实和虚拟chunk ID列表合并到一起，方便统计已经处理了多少段落
            chunk_ids.extend(virtual_chunk_ids)

        ################## 至此是所有的合并段落得到的 VIRT chunk #################
        # 得限制一下太长的文档。传一本几百页的书的话，下面的 SUB 段落就得有上万个。那 embedding 得算好久好久。实际上，遇到特别长的文档，就先不要算 SUB 的段落了。
        if len(chunk_ids) < 2000 and max_page_id <= 100: # 超过100页的，都不要SUB了。

            # 新增大段落拆分成小份的，命名为 SUB-{int}
            sub_chunk_id_from_0 = 0
            sub_chunk_ids = []
            for i, orig_chunk in enumerate(chunks):
                orig_chunk_id = orig_chunk["chunk_id"]
                # 对于 SUB 型的 chunk，其 enriched_text 反正都是一样的。目的都是，只要有一小句话命中了，就把一大块上下关联的段落加进 prompt 里。
                enriched_text = ""
                clickable_chunk_ids = []
                
                if i - 1 >= 0:
                    pre_1_chunk = chunks[i-1]["text"]
                    enriched_text = pre_1_chunk
                    if is_chunk_clickable(chunks[i-1]):
                        clickable_chunk_ids.append(chunks[i-1]["chunk_id"])
                enriched_text += orig_chunk["text"]
                if is_chunk_clickable(orig_chunk):
                    clickable_chunk_ids.append(orig_chunk["chunk_id"])
                page_id = orig_chunk["locations"][0]["page_id"]
                
                if i + 1 < len(chunks):
                    enriched_text += chunks[i+1]["text"]
                    if is_chunk_clickable(chunks[i+1]):
                        clickable_chunk_ids.append(chunks[i+1]["chunk_id"])

                #  需要扩充一下 chunk 内容。从原来的 text 字段，变更为 real_text 和 text_for_prompt 两部分，前者是真实内容，后者是向上下扩展一两段的结果
                #  每个 real_text 都应该是一句话？
                sent_tokenize_list = sent_tokenize(orig_chunk["text"]) # 切成小句子
                # 以1句、2句、3句两种粒度
                for j, sent in enumerate(sent_tokenize_list):
                    if j + 2 < len(sent_tokenize_list):
                        # 把双句的构造出来
                        chunk = {
                            "text": sent + sent_tokenize_list[j+1] + sent_tokenize_list[j+2],
                            "real_text": sent + sent_tokenize_list[j+1] + sent_tokenize_list[j+2],
                            "enriched_text": enriched_text,
                            "enriched_text_tokens": llm.num_tokens_from_messages([enriched_text]),
                            "real_chunk_ids": [orig_chunk_id]
                        }
                        sub_chunk_id = f"SUB-{sub_chunk_id_from_0}-{orig_chunk_id}"
                        sub_chunk_ids.append(sub_chunk_id)
                        res.append(Document(
                            page_content = chunk["real_text"],
                            metadata = {
                                "doc_id": self.doc_id,
                                "chunk_info": chunk,
                                "source": {
                                    # "filename": self.filename,
                                    "doc_id":self.doc_id,
                                    "chunk_id": sub_chunk_id,
                                    "clickable_chunk_ids": clickable_chunk_ids,
                                    "page_id": page_id # 第一个真实段落的起点所在的页码，从0开始计数
                                }
                            },
                        ))
                        sub_chunk_id_from_0 += 1
                    if j + 1 < len(sent_tokenize_list):
                        # 把双句的构造出来
                        chunk = {
                            "text": sent + sent_tokenize_list[j+1],
                            "real_text": sent + sent_tokenize_list[j+1],
                            "enriched_text": enriched_text,
                            "enriched_text_tokens": llm.num_tokens_from_messages([enriched_text]),
                            "real_chunk_ids": [orig_chunk_id]
                        }
                        sub_chunk_id = f"SUB-{sub_chunk_id_from_0}-{orig_chunk_id}"
                        sub_chunk_ids.append(sub_chunk_id)
                        res.append(Document(
                            page_content = chunk["real_text"],
                            metadata = {
                                "doc_id": self.doc_id,
                                "chunk_info": chunk,
                                "source": {
                                    # "filename": self.filename,
                                    "doc_id":self.doc_id,
                                    "chunk_id": sub_chunk_id,
                                    "clickable_chunk_ids": clickable_chunk_ids,
                                    "page_id": page_id # 第一个真实段落的起点所在的页码，从0开始计数
                                }
                            },
                        ))
                        sub_chunk_id_from_0 += 1
                    # 把单句的构造出来
                    chunk = {
                        "text": sent,
                        "real_text": sent,
                        "enriched_text": enriched_text,
                        "enriched_text_tokens": llm.num_tokens_from_messages([enriched_text]),
                        "real_chunk_ids": [orig_chunk_id]
                    }
                    sub_chunk_id = f"SUB-{sub_chunk_id_from_0}-{orig_chunk_id}"
                    sub_chunk_ids.append(sub_chunk_id)
                    res.append(Document(
                        page_content = chunk["real_text"],
                        metadata = {
                            "doc_id": self.doc_id,
                            "chunk_info": chunk,
                            "source": {
                                # "filename": self.filename,
                                "doc_id":self.doc_id,
                                "chunk_id": sub_chunk_id,
                                "clickable_chunk_ids": clickable_chunk_ids,
                                "page_id": page_id # 第一个真实段落的起点所在的页码，从0开始计数
                            }
                        },
                    ))
                    sub_chunk_id_from_0 += 1

            chunk_ids.extend(sub_chunk_ids)
        debug_logger.debug(f'[PdfChunksLoader][load] chunk_ids = {chunk_ids}')

        ################## 至此是所有的段落细粒度切分得到的 SUB chunk #################

        return res

