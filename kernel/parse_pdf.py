# -*- coding: utf-8 -*-

from flask import Flask, Response
from flask import request, url_for, redirect, flash, jsonify, render_template
import random
import time
import requests
import io
import json
import base64
from flask_cors import CORS
import urllib
from kernel.llm import *
from kernel.pp_parse_pdf import *
from kernel.pp_parse_pdf import _design_chapter
from kernel.pp_parse_pdf import _replace_image_area
from kernel.pp_parse_pdf import _sign_title_blocks
from kernel.pp_parse_pdf import _images_sort
from kernel.pp_parse_pdf import _delete_head_and_foot

"""
用 pymupdf + ppstructure 解析的结果，要对齐到速读原有解析格式上来。
"""
def blocks2chunks_for_ppstructure(chapters):
    first_title_found = False
    res = []
    chunk_id = 0
    for i, chapter in enumerate(chapters):
        for block in chapter:
            """
            block 是个 dict，结构形如：
            {
                "area": [   # xyxy
                    159,
                    222,
                    203,
                    238
                ],
                "text": "Abstract\n",
                "type": "title",
                "page_number": 0
            }{
                "area": [
                    89,
                    244,
                    273,
                    424
                ],
                "text": "We introduce a new language representa-\ntion model called BERT, which stands for\nBidirectional Encoder Representations from\nTransformers. Unlike recent language repre-\nsentation models (Peters et al., 2018a; Rad-\nford et al., 2018), BERT is designed to pre-\ntrain deep bidirectional representations from\nunlabeled text by jointly conditioning on both\nleft and right context in all layers. As a re-\nsult, the pre-trained BERT model can be \ufb01ne-\ntuned with just one additional output layer\nto create state-of-the-art models for a wide\nrange of tasks, such as question answering and\nlanguage inference, without substantial task-\nspeci\ufb01c architecture modi\ufb01cations.\n",
                "type": "text",
                "page_number": 0
            }
            """

            p = {}
            if block['type'] == 'title':
                if (not first_title_found):
                    p['chunk_type'] = 'title'
                    first_title_found = True
                else:
                    p['chunk_type'] = 'h1'
            else:
                p['chunk_type'] = 'normal'

            p['text'] = block['text']
            p['page_ids'] = [block['page_number']]
            p['locations'] = block['locations'] if 'locations' in block else None,
            if p['locations'] and type(p['locations'][0]) == type([]):
                p['locations'] = p['locations'][0]
            p["chunk_id"] = str(chunk_id)
            p["summary"] = {}
            p["summary_status"] = 0 if (p["chunk_type"] == "title" or p["chunk_type"] == "h1") else 1
            res.append(p)
            chunk_id += 1
    return res

def save_chunks_to_db(redis_client, doc_id, chunks):
    chunk_ids = []
    for chunk in chunks:
        if chunk["summary_status"] != 0:
            chunk_ids.append(chunk["chunk_id"])
    redis_client.set(str((doc_id, 'TEXT_CHUNK_IDS')), json.dumps(chunk_ids))
    for chunk in chunks:
        chunk_id = chunk["chunk_id"]
        chunk_json_str = json.dumps(chunk)
        redis_client.set(str((doc_id, chunk_id)), chunk_json_str)
    redis_client.set(doc_id, json.dumps(chunks))


