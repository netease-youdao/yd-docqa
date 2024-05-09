from argparse import ArgumentParser
from qanything_kernel.configs.model_config import DT_7B_MODEL_PATH, \
    DT_7B_DOWNLOAD_PARAMS, DT_3B_MODEL_PATH, DT_3B_DOWNLOAD_PARAMS
import qanything_kernel.configs.model_config as model_config
from qanything_kernel.connector.llm.llm_for_openai_api import OpenAILLM
from qanything_kernel.utils.custom_log import debug_logger
from qanything_kernel.utils.general_utils import download_file, get_gpu_memory_utilization, check_package_version
from modelscope import snapshot_download
from modelscope.hub.file_download import model_file_download
import torch
import subprocess
import os
from redis import Redis
from configs.cur_config import *

redis_client = Redis(host=REDIS_HOST_AND_PORT_AND_DBNUM[0], port=REDIS_HOST_AND_PORT_AND_DBNUM[1], db=REDIS_HOST_AND_PORT_AND_DBNUM[2])

class Arguments:
    def __init__(self):
        self.use_cpu = USE_CPU
        self.use_openai_api = USE_OPENAI_API
        self.openai_api_base = OPENAI_API_BASE
        self.openai_api_key = OPENAI_API_KEY        
        self.openai_api_model_name = OPENAI_API_MODEL_NAME
        self.openai_api_context_length = OPENAI_API_CONTEXT_LENGTH
        self.model_size = LLM_MODEL_SIZE
        self.device_id = DEVICE_ID

import platform
os_system = platform.system()
print(f'os_system = {os_system}')
parser = ArgumentParser()

if os_system != 'Darwin':
    cuda_version = torch.version.cuda
    if cuda_version is None:
        raise ValueError("CUDA is not installed.")
    elif float(cuda_version) < 12:
        raise ValueError("CUDA version must be 12.0 or higher.")

    python_version = platform.python_version()
    python3_version = python_version.split('.')[1]
    os_system = platform.system()
    if os_system == "Windows":
        raise ValueError("The project must be run in the WSL environment on Windows system.")
    if os_system != "Linux":
        raise ValueError(f"Unsupported system: {os_system}")
    system_name = 'manylinux_2_28_x86_64'
    # # 官方发布的1.17.1不支持cuda12以上的系统，需要根据官方文档:https://onnxruntime.ai/docs/install/里提到的地址手动下载whl
    # if not check_package_version("onnxruntime-gpu", "1.17.1"):
    #     download_url = f"https://aiinfra.pkgs.visualstudio.com/PublicPackages/_apis/packaging/feeds/9387c3aa-d9ad-4513-968c-383f6f7f53b8/pypi/packages/onnxruntime-gpu/versions/1.17.1/onnxruntime_gpu-1.17.1-cp3{python3_version}-cp3{python3_version}-{system_name}.whl/content"
    #     debug_logger.info(f'开始从{download_url}下载onnxruntime，也可以手动下载并通过pip install *.whl安装')
    #     whl_name = f'onnxruntime_gpu-1.17.1-cp3{python3_version}-cp3{python3_version}-{system_name}.whl'
    #     download_file(download_url, whl_name)
    #     os.system(f"pip install {whl_name}")
    if not check_package_version("vllm", "0.2.7"):
        os.system(f"pip install vllm==0.2.7 -i https://pypi.mirrors.ustc.edu.cn/simple/ --trusted-host pypi.mirrors.ustc.edu.cn")

    # from vllm.engine.arg_utils import AsyncEngineArgs

    # parser = AsyncEngineArgs.add_cli_args(parser)

else:
    print(f'[Darwin] 开始检查是否安装了 xcode')
    # 检查是否安装了xcode
    if not check_package_version("llama_cpp_python", "0.2.60"):
        os.system(f'CMAKE_ARGS="-DLLAMA_METAL_EMBED_LIBRARY=ON -DLLAMA_METAL=on" pip install -U llama-cpp-python --no-cache-dir -i https://pypi.mirrors.ustc.edu.cn/simple/ --trusted-host pypi.mirrors.ustc.edu.cn')
    parser.add_argument('--model', dest='model', help='LLM model path')
    print(f'[Darwin] 安装 xcode 检查完了')

args_cli = parser.parse_args()
args = Arguments()
args.__dict__.update(args_cli.__dict__)

print('use_cpu:', args.use_cpu, flush=True)
print('use_openai_api:', args.use_openai_api, flush=True)
print(f'type(use_openai_api): {type(args.use_openai_api)}', flush=True)

if args.use_cpu:
    model_config.CUDA_DEVICE = args.device_id
    os.environ["CUDA_VISIBLE_DEVICES"] = args.device_id

model_download_params = None
if not args.use_openai_api:
    model_size = args.model_size
    if os_system == "Linux":
        args.gpu_memory_utilization = get_gpu_memory_utilization(model_size, args.device_id)
        debug_logger.info(f"GPU memory utilization: {args.gpu_memory_utilization}")
    if model_size == '3B':
        args.model = DT_3B_MODEL_PATH
        model_download_params = DT_3B_DOWNLOAD_PARAMS
    elif model_size == '7B':
        args.model = DT_7B_MODEL_PATH
        model_download_params = DT_7B_DOWNLOAD_PARAMS
    else:
        raise ValueError(f"Unsupported model size: {model_size}, supported model size: 3B, 7B")

# 如果模型不存在, 下载模型
if args.use_openai_api:
    debug_logger.info(f'使用openai api {args.openai_api_model_name} 无需下载大模型')
elif not os.path.exists(args.model):
    debug_logger.info(f'开始下载大模型：{model_download_params}')
    # if os_system == 'Darwin':
    #     cache_dir = model_file_download(**model_download_params)
    #     debug_logger.info(f'模型下载完毕！{cache_dir}')
    # else:
    #     cache_dir = snapshot_download(**model_download_params)
    cache_dir = snapshot_download(**model_download_params)
    debug_logger.info(f'模型下载完毕！{cache_dir}')
    # output = subprocess.check_output(['ln', '-s', cache_dir, args.model], text=True)
    # debug_logger.info(f'模型下载完毕！cache地址：{cache_dir}, 软链接地址：{args.model}')
    debug_logger.info(f"CUDA_DEVICE: {model_config.CUDA_DEVICE}")
else:
    debug_logger.info(f'{args.model}路径已存在，不再重复下载大模型（如果下载出错可手动删除此目录）')
    debug_logger.info(f"CUDA_DEVICE: {model_config.CUDA_DEVICE}")

if platform.system() == 'Linux':
    if args.use_openai_api:
        llm: OpenAILLM = OpenAILLM(args)
    else:
        from qanything_kernel.connector.llm import OpenAICustomLLM
        llm: OpenAICustomLLM = OpenAICustomLLM(args)
    from qanything_kernel.connector.rerank.rerank_onnx_backend import RerankOnnxBackend
    from qanything_kernel.connector.embedding.embedding_onnx_backend import EmbeddingOnnxBackend
    local_rerank_backend: RerankOnnxBackend = RerankOnnxBackend(args.use_cpu)
    embeddings: EmbeddingOnnxBackend = EmbeddingOnnxBackend(args.use_cpu)
else:
    if args.use_openai_api:
        llm: OpenAILLM = OpenAILLM(args)
    else:
        from qanything_kernel.connector.llm import LlamaCPPCustomLLM
        llm: LlamaCPPCustomLLM = LlamaCPPCustomLLM(args)
    from qanything_kernel.connector.rerank.rerank_torch_backend import RerankTorchBackend
    from qanything_kernel.connector.embedding.embedding_torch_backend import EmbeddingTorchBackend
    local_rerank_backend: RerankTorchBackend = RerankTorchBackend(args.use_cpu)
    embeddings: EmbeddingTorchBackend = EmbeddingTorchBackend(args.use_cpu)

embed_engine = embeddings