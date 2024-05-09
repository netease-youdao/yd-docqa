
from datetime import datetime
import os

DEBUG_PDF_INCOMPLETE = False
DEBUG_SAVE_OCR_IMG = False
################################################################################
# 问答策略相关常量
SYMBOL_NO_NEED_TO_REWRITE_QUERY = "NO_NEED_TO_REWRITE"
MAX_TOKENS_FOR_REFERENCE_INFORMATION = 2400 # 3000
MAX_TOKENS_FOR_HISTORY = 600

################################################################################
# 当前代码目录的父目录
SYSTEM_PATH_PREFIX = "/Users/xiaoyunlong/code/opensource/"
# 用户文件存储路径
FILE_STORAGE_PATH = "user_files"

################################################################################
# QAnything 的 LLM、embedding 配置
USE_CPU = True
USE_OPENAI_API = True
OPENAI_API_BASE = os.environ.get("OPENAI_API_BASE")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_API_MODEL_NAME = "gpt-3.5-turbo-1106"
OPENAI_API_CONTEXT_LENGTH = "4096"
LLM_MODEL_SIZE = "3B"
DEVICE_ID = "0"

################################################################################
EMBEDDING_SERVICE_SOURCE = "OpenSource"

################################################################################
# pdf 解析算法版本。解析算法更新时，需要重新解析pdf、重新生成vdb。
PARSE_SERVICE_VERSION = "0.0.1"

################################################################################
#  REDIS_HOST_AND_PORT_AND_DBNUM = ("localhost", 6379, 0)
REDIS_HOST_AND_PORT_AND_DBNUM = ("localhost", 6379, 2) # TODO 临时调试用
################################################################################