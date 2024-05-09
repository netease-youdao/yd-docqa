# -*- coding: utf-8 -*-

from functools import lru_cache
from configs.cur_config import *

import sys

from kernel.PdfChunksLoader import PdfChunksLoader
sys.path.append(SYSTEM_PATH_PREFIX)

import tempfile
from flask import Flask, Response, send_file, send_from_directory
from flask import request, url_for, redirect, flash, jsonify, render_template
from flask import stream_with_context
from kernel.global_vars import *
import queue
import threading
import json
import base64
from flask_cors import CORS
from kernel.parse_pdf import *
from kernel.summary import *
from kernel.query import *
from kernel.llm import *
import hashlib
from langchain.vectorstores import FAISS

from qanything_kernel.utils.custom_log import debug_logger

import nest_asyncio
nest_asyncio.apply()

os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ['KMP_DUPLICATE_LIB_OK']='True'
print(f'os.environ = {os.environ}')


# app = Flask(__name__, static_url_path='/static', static_folder='static') # 为了能访问 static 目录下的网页
# app = Flask(__name__)
app = Flask(__name__, static_url_path='', static_folder='dist') # 为了能访问 static 目录下的网页

app.config['JSON_AS_ASCII'] = False # 确保输出正常的 unicode 字符，而不是 \uXXXX 这种。

CORS(app) # 允许所有跨域请求

if not os.path.exists('vdbs'):
    os.makedirs('vdbs')


##############################################################

# NOTE: 开启即往 profiles 目录下写入性能分析文件。正式服不要开启。

# from werkzeug.middleware.profiler import ProfilerMiddleware
# app.wsgi_app = ProfilerMiddleware(app.wsgi_app, restrictions=[30], profile_dir='profiles')

##############################################################
from flask import g
import logging
import logging.handlers
import queue
import threading

def hash_str(orig_str):
    hash_obj = hashlib.md5(orig_str.encode('utf-8'))  # 使用md5算法进行哈希计算
    hash_value = hash_obj.hexdigest()  # 将哈希值转换为16进制字符串
    return hash_value

def hash_pdf_b64(base64_str):
    bytes_data = base64.b64decode(base64_str)  # 将base64字符串转换为bytes类型
    hash_obj = hashlib.md5(bytes_data)  # 使用md5算法进行哈希计算
    hash_value = hash_obj.hexdigest()  # 将哈希值转换为16进制字符串
    return hash_value

def try_get_cached_doc(redis_client, doc_id):
    if not redis_client.exists(doc_id):
        return None
    return json.loads(redis_client.get(doc_id))

"""
上传pdf。
用户传上来，直接转发给士琪的解析服务。
"""
@app.route('/upload', methods=["POST"])
def upload():

    if 'file' not in request.files:
        return 'No file part in the request', 400

    file = request.files['file']
    if file.filename == '':
        return 'No selected file', 400

    # 读取文件内容并进行Base64编码
    file_content = file.read()
    file_data_b64 = base64.b64encode(file_content).decode('utf-8')

    # 获取布尔类型参数
    do_summarize = request.form.get('do_summarize')
    do_prepare_for_QA = request.form.get('do_prepare_for_QA')
    do_summarize = (do_summarize.lower() == 'true')
    do_prepare_for_QA = (do_prepare_for_QA.lower() == 'true')
    print(f'[upload API] do_summarize = {do_summarize}, do_prepare_for_QA = {do_prepare_for_QA}')

    doc_id = hash_pdf_b64(file_data_b64)
    print(f'doc_id = {doc_id}')
    # 先检查本地是否有缓存结果。如果有，直接把全部缓存返回回去。没有就重新做切段之类的。
    chunks_json = try_get_cached_doc(redis_client, doc_id)  # TODO 注意啊，现在这里获取到的 summary 肯定都是空的。因为后面真正做了摘要请求后，也是写到了 redis 中以 (doc_id, chunk_id) 为 key 的 item 里了，而不是写在 doc 本身的 item 里。
    if chunks_json is None:
    # if True: # DEBUG 强制重解析

        # 解析用本机的 pymupdf+ppstructure
        temp_file = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        print(f'[upload API] temp_file.name = {temp_file.name}')
        try:
            file.seek(0)
            file.save(temp_file.name)
            pdf_path = temp_file.name
            with tempfile.TemporaryDirectory() as temp_dir:
                chapters = pdf_parse_to_chapters(pdf_path, temp_dir)
            chunks_json = blocks2chunks_for_ppstructure(chapters)
        except:
            print(f'[upload API except] traceback = {traceback.format_exc()}')
        finally:
            # os.remove(temp_file.name)
            print(f'[upload API finally] traceback = {traceback.format_exc()}')
            pass

        # 把 chunks 内容整理到 redis 中。本地做逐段摘要，需要这些。
        save_chunks_to_db(redis_client, doc_id, chunks_json)

    if do_prepare_for_QA:
        # 构造 vdb
        file_loader = PdfChunksLoader(doc_id, redis_client, chunks_json)
        docs = file_loader.load()
        file_loader.parse_doc_info_and_save_to_redis() # 目前主要是把大标题存起来，方便问题改写环节使用。再加上存几个随机的字多的段落，用于生成脑暴问题。
        cur_doc_vdb = FAISS.from_documents(docs, embed_engine)
        candidate_vdb_paths = construct_vdb_paths(doc_id, embed_engine)
        for vdb_p in candidate_vdb_paths:
            folder_path = vdb_p
            print(f'[get_vdb_by_docid] trying to mkdir: {folder_path}')
            if not os.path.exists(folder_path):
                os.makedirs(folder_path)
            print(f'[get_vdb_by_docid] trying to save vdb file for: {doc_id}')
            cur_doc_vdb.save_local(folder_path)


    if do_summarize:
        do_summarize_for_doc(redis_client, doc_id, llm)

    # 存一下原始pdf文件和解析结果chunks json，用于前端在刷新 pdfView 页时能重新获取改pdf的内容
    save_pdf_to_disk(doc_id, file_content, chunks_json)

    response = jsonify({'chunks': chunks_json,
                        'doc_id': doc_id})
    # 添加响应头
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response

def save_pdf_to_disk(doc_id, file_content, chunks_json):
    doc_directory = os.path.join(FILE_STORAGE_PATH, doc_id)

    # 创建文档对应的文件夹
    if not os.path.exists(doc_directory):
        os.makedirs(doc_directory)

    # 保存 PDF 文件
    pdf_file_path = os.path.join(doc_directory, f'{doc_id}.pdf')
    with open(pdf_file_path, 'wb') as pdf_file:
        pdf_file.write(file_content)

    # 保存 chunks.json
    chunks_file_path = os.path.join(doc_directory, 'chunks.json')
    with open(chunks_file_path, 'w', encoding='utf-8') as chunks_file:
        json.dump(chunks_json, chunks_file)


"""
上传单个 chunk 的 id，然后服务端请求 summarize，并返回 summary，同时记录到本地内存中。等整个文件完成，再写入文件作为缓存。
"""
@app.route('/chunk2summary', methods=['GET', 'POST'])
def chunk2summary():
    summary = {
        'state': ""
    }
    # 需要的参数，包括 chunk_id, doc_id
    if (request.is_json):
        jso = request.get_json()
        doc_id = jso['doc_id']
        chunk_id = jso['chunk_id']

        # 加载这个 doc_id 对应的 chunks 原文文件。其中的组织方式是：{chunk_id: chunk_dict}
        _summary, error = get_summary_of_1_chunk(redis_client, doc_id, chunk_id, llm)
        if error == "Invalid_doc":
            print(f'state1: Invalid_doc')
            summary = {
                "state": error
            }
        elif error == "Invalid_chunk":
            print(f'state2: Invalid_chunk')
            summary = {
                "state": error
            }
        elif error == "Doing":
            print(f'state3: Doing')
            summary = {
                "tldr": "",
                "state": "Doing"
            }
        else: # 这才是真的能取到有效的 summary 了
            print(f'state4, error = {error}')
            summary = _summary

    response = jsonify(summary)
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response

def construct_vdb_paths(doc_id, embed_engine):
    # # 用 embed_engine 现请求一次，看看最新的 embedding 版本号
    # embedding_version = embed_engine.get_embedding_version()

    res = []
    vdb_roots = [
        'vdbs'
    ]
    for vr in vdb_roots:
        res.append(f"{vr}/{doc_id}__{EMBEDDING_SERVICE_SOURCE}")
        print(f'[{cur_func_name()}] res = {res}')
    return res

def get_vdb_by_docid(doc_id, chunks_json, embed_engine, try_old_vdb=False, src_product=None):
    cur_doc_vdb = None
    # 首先构造可能的文件路径们，然后遍历它们，依次尝试读取。如果全都没有，说明需要现建库。
    candidate_vdb_paths = construct_vdb_paths(doc_id, embed_engine)

    # 当前函数退出时，要在 finally 中确保 vdb_path 对应的本地临时文件都被删除了。否则会导致满盘！
    # TODO 开源版就不管这事了，让用户自己手动删吧。

    for vdb_p in candidate_vdb_paths:
        try:
            cur_doc_vdb = load_vdb_from_file(vdb_p, embed_engine)
            if cur_doc_vdb is not None:
                break
        except:
            # 当前尝试读取的路径失败了，需要尝试下一个。
            debug_logger.info(f'[get_vdb_by_docid][before downloading from nos] load vdb from local file failed: {vdb_p}')
            continue
    return cur_doc_vdb

def bridge(async_gen, q):
    # 这个函数在另一个线程中执行，运行异步生成器并将结果放入队列
    loop = asyncio.new_event_loop()

    async def run():
        async for item in async_gen:
            q.put(item)
        q.put(None)  # 使用 None 作为结束信号

    loop.run_until_complete(run())

def generate_piece(q):
    # 这个生成器会从队列中获取数据并 yield
    while True:
        data = q.get()
        if data is None:
            break
        yield data

@lru_cache(maxsize=256)
def load_vdb_from_file(vdb_path, embed_engine):
    return FAISS.load_local(vdb_path, embed_engine, allow_dangerous_deserialization=True)

def stream_error_msg(error_msg):
    piece = 'event: error\ndata: '
    piece += error_msg
    piece += '\n\n'
    yield piece


@app.route('/chat_qa', methods=["GET", "POST"])
def stream_qa_subservice():
    doc_id = request.args.get('doc_id', "", type=str)
    q_msg = request.args.get('message', "", type=str)
    lang = request.args.get('lang', "zh", type=str)
    attachment = request.form.get('attachment', "", type=str)
    q_type = request.args.get('type', "0", type=str)
    stream_json = request.args.get('stream_json', False) # TODO 默认值应为 False，与旧版的词典客户端兼容！！！！

    jso = None
    try:

        jso = {
            "doc_id": doc_id,
            "lang": lang,
            "message": q_msg,
            "q_type": int(q_type),
            "attachment": attachment,
            "stream_json": True if stream_json else False
        }
        debug_logger.info(f"chat_qa, jso = {jso} ")
        # print(f'[chat_qa] chat_qa, jso = {json.dumps(jso, indent=4, ensure_ascii=False)} ')

        cur_doc_vdb = get_vdb_by_docid(doc_id, chunks_json=None, embed_engine=embed_engine)
        if cur_doc_vdb is None:
            error_msg = "未找到 doc_id 对应的文档，请确认 doc_id 或重新上传文档。"
            response = Response(stream_error_msg(error_msg), mimetype='text/event-stream')
            return response

        # 流式(yield)输出结果
        q = queue.Queue()

        # 在一个新线程中运行 bridge 函数
        threading.Thread(target=bridge, args=(stream_query_on_doc_vdb(redis_client, jso, vdb=cur_doc_vdb), q)).start()

        # stream_with_context 确保请求上下文在生成器中可用
        response = Response(stream_with_context(generate_piece(q)), mimetype='text/event-stream')
        # response = Response(stream_with_context(stream_query_on_doc_vdb(redis_client, jso, vdb=cur_doc_vdb)), mimetype='text/event-stream')

    except Exception as e:
        log_msg = jso if jso is not None else {}
        log_msg['traceback'] = traceback.format_exc()
        debug_logger.info(f'[chat_qa] error_log_msg [{e}] = {json.dumps(log_msg, ensure_ascii=False)}')
        # print(f'[chat_qa] error_log_msg [{e}] = {json.dumps(log_msg, ensure_ascii=False)}')

        error_msg = f"{traceback.format_exc()}"
        response = Response(stream_error_msg(error_msg), mimetype='text/event-stream')

    response.headers['Cache-Control'] = 'no-cache'
    return response

def get_chunks_content(doc_id):
    chunks_file_path = os.path.join(FILE_STORAGE_PATH, doc_id, 'chunks.json')
    try:
        with open(chunks_file_path, 'r', encoding='utf-8') as chunks_file:
            chunks_content = chunks_file.read()
        return json.loads(chunks_content)
    except:
        return ""

@app.route('/get_pdf_info/<doc_id>', methods=['GET'])
def get_file_url(doc_id):
    # pdf_url = f"http://your_domain.com/files/{doc_id}/XXXX.pdf"  # 替换 your_domain.com 为你的域名
    pdf_url = f"files/{doc_id}/{doc_id}.pdf"  # 替换 your_domain.com 为你的域名
    chunks_content = get_chunks_content(doc_id)
    response = {
        'pdf_url': pdf_url,
        'chunks': chunks_content
    }
    return jsonify(response)

@app.route('/files/<path:file_path>', methods=['GET'])
def download_file(file_path):
    full_file_path = os.path.join(FILE_STORAGE_PATH, file_path)
    if os.path.exists(full_file_path):
        return send_file(full_file_path, as_attachment=True)
    else:
        return "File not found", 404


@app.route("/")
def index():
    # return redirect('/dist/index.html')
    # return send_from_directory('templates', 'index.html')


    # js_file = url_for('static', filename='assets/index.3e5e833b.js')
    # vendor_js_file = url_for('static', filename='assets/vendor.c67ec806.js')
    # css_file = url_for('static', filename='assets/index.f4a1f9f7.css')
    # return render_template('index.html', js_file=js_file, vendor_js_file=vendor_js_file, css_file=css_file)
    return app.send_static_file('index.html')

@app.route('/<path:path>')
def static_proxy(path):
    # 确保对于Vue中的任何路由，都返回`index.html`
    # Vue Router在前端会处理正确的路由
    if not path.startswith('assets/'):
        return app.send_static_file('index.html')
    return send_from_directory('dist', path)

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=38765, use_reloader=False, threaded=True)