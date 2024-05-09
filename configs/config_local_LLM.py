from datetime import datetime

DEBUG_PDF_INCOMPLETE = False
DEBUG_SAVE_OCR_IMG = False
################################################################################
# 问答策略相关常量
SYMBOL_NO_NEED_TO_REWRITE_QUERY = "NO_NEED_TO_REWRITE"
MAX_TOKENS_FOR_REFERENCE_INFORMATION = 2400 # 3000
MAX_TOKENS_FOR_HISTORY = 600

################################################################################
# 当前代码目录的父目录
import os

current_file_path = os.path.abspath(__file__)
parent_dir = os.path.abspath(os.path.join(current_file_path, os.pardir))
grandparent_dir = os.path.abspath(os.path.join(parent_dir, os.pardir))
SYSTEM_PATH_PREFIX = grandparent_dir
# 用户文件存储路径
FILE_STORAGE_PATH = "user_files"

################################################################################
# QAnything 的 LLM、embedding 配置
USE_CPU = True
USE_OPENAI_API = False
LLM_MODEL_SIZE = "3B"
DEVICE_ID = "0"

################################################################################
EMBEDDING_SERVICE_SOURCE = "OpenSource"

################################################################################
# pdf 解析算法版本。解析算法更新时，需要重新解析pdf、重新生成vdb。
PARSE_SERVICE_VERSION = "0.0.1"

################################################################################
REDIS_HOST_AND_PORT_AND_DBNUM = ("localhost", 6379, 2)
################################################################################