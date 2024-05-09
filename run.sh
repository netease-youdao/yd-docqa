## !/bin/bash

source activate qanything-python

################################################################################
ln -s configs/config_openai_api.py configs/cur_config.py

################################################################################
if [ "$system" = "M1mac" ]; then
    # 检查 xcode-select 命令是否存在
    if ! command -v xcode-select &> /dev/null; then
        echo "xcode-select 命令不存在。请前往App Store下载Xcode。"
        # 结束脚本执行
        exit 1
    fi

    # 执行 xcode-select -p 获取当前Xcode路径
    xcode_path=$(xcode-select -p)

    # 检查 xcode-select 的输出是否以 /Applications 开头
    if [[ $xcode_path != /Applications* ]]; then
        echo "当前Xcode路径不是以 /Applications 开头。"
        echo "请确保你已从App Store下载了Xcode，如果已经下载，请执行以下命令："
        echo "sudo xcode-select --switch /Applications/Xcode.app/Contents/Developer"
        exit 1
    else
        echo "Xcode 已正确安装在路径：$xcode_path"
    fi
fi

# 检测 Redis 服务是否在运行
if ! pgrep redis-server > /dev/null
then
    echo "Redis 服务未运行"

    # 尝试启动 Redis 服务
    if command -v redis-server &> /dev/null
    then
        echo "尝试启动 Redis 服务..."
        redis-server --daemonize yes
        echo "Redis 服务已启动"
    else
        echo "Redis 未安装，请按照官方指南安装 Redis：https://redis.io/download"
        exit 1
    fi
else
    echo "Redis 服务已在运行"
fi


# 速读开源版开发服
python app.py 
# nohup python app.py > /dev/null 2>&1 & 

