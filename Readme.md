<div align="center">

 

# 有道速读

</div>

<div align="center">

<a href="https://qanything.ai"><img src="https://img.shields.io/badge/%E5%9C%A8%E7%BA%BF%E4%BD%93%E9%AA%8C-QAnything-purple"></a>
&nbsp;&nbsp;&nbsp;&nbsp;
<a href="https://read.youdao.com#/home"><img src="https://img.shields.io/badge/%E5%9C%A8%E7%BA%BF%E4%BD%93%E9%AA%8C-有道速读-purple"></a>
&nbsp;&nbsp;&nbsp;&nbsp;

<a href="./LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-yellow"></a>
&nbsp;&nbsp;&nbsp;&nbsp;
<a href="https://github.com/netease-youdao/yd-docqa/pulls"><img src="https://img.shields.io/badge/PRs-welcome-red"></a>
&nbsp;&nbsp;&nbsp;&nbsp;
<a href="https://twitter.com/YDopensource"><img src="https://img.shields.io/badge/follow-%40YDOpenSource-1DA1F2?logo=twitter&style={style}"></a>
&nbsp;&nbsp;&nbsp;&nbsp;

</div>

<details open="open">
<summary>目 录</summary>

- [什么是有道速读](#什么是有道速读)
- [开始之前](#开始之前)
- [安装&开始使用](#开始)
- [交流&支持](#交流--支持)
- [协议](#协议)

</details>


# 什么是有道速读？
[有道速读](https://read.youdao.com/)是基于 [QAnything](https://github.com/netease-youdao/QAnything) 开发的、针对各类 PDF 文档的 AI 辅助阅读工具。

本代码库是有道速读网站的开源版本，支持了 PDF 解析算法和 LLM、embedding 等模型的完全本地部署。功能上保留了有道速读最核心的**自由问答、截图问答、逐段摘要**。


## 特点
- 数据安全，支持全程拔网线使用。
- 支持跨语种问答，中英文问答随意切换，无所谓文件是什么语种。
- 易用性，无需繁琐的配置，一键安装部署，拿来就用。


# 开始之前
**在GitHub上加星，即可立即收到新版本的通知！**
![star_us](https://github.com/netease-youdao/QAnything/assets/29041332/fd5e5926-b9b2-4675-9f60-6cdcaca18e14)
* [🏄 在线试用QAnything](https://qanything.ai)
* [📚 在线试用有道速读](https://read.youdao.com)


# 开始
## Step 1. 安装

**纯python环境的安装仅作为demo体验，不建议生产环境部署。**


环境要求:

- Python 3.10+ (建议使用aoaconda3来管理Python环境)
- System
    - Linux: glibc 2.28+ and Cuda 12.0+ (如果使用GPU)
    - Windows: WSL with Ubuntu 20.04+ and GEFORCE EXPERIENCE 535.104+ (如果使用GPU)
    - MacOS（版本 >= 14.4）: M1/M2/M3 Mac with Xcode 15.0+
请创建一个干净的Python虚拟环境，以避免潜在冲突（推荐使用Anaconda3）。

请依次运行如下命令安装环境：
```shell
conda create -n yd-docqa python=3.10
conda activate yd-docqa
git clone https://github.com/netease-youdao/yd-docqa.git
cd yd-docqa
pip install -r requirements.txt
```

启动前，请求确保配置文件符合预期。启动依赖于 `configs/cur_config.py` 文件，您可以将其作为软链接指向 `configs` 目录下的现有配置模板。例如，用OpenAI的LLM API的话：
```shell
ln -s configs/config_openai_api.py configs/cur_config.py
export OPENAI_API_BASE="{您的openai api base}"
export OPENAI_API_KEY="{您的key}"
```

然后，运行 `run.sh` 脚本，即可启动服务。
```shell
sh run.sh
```

## Step 2. 开始体验

#### 前端页面
运行成功后，即可在浏览器输入以下地址进行体验。

- 前端地址: http://`your_host`:38765/

#### API
服务的API见：[速读开源 API 文档](docs/API.md)

#### DEBUG
如果想要查看相关日志，请查看`logs/debug_logs`目录下的日志文件。


## Step 3. 关闭服务

Ctrl/Command + C 即可

## 注意
随着服务的运行和使用，源码目录下会多出 `vdbs` 和 `user_files` 两个目录，上传文档越多，这俩目录体积越大。其中分别保存了问答依赖的向量数据库、文档副本和文档解析结果。您可以手动删除其中的文件，以释放磁盘空间。

## 贡献代码
我们感谢您对贡献到我们项目的兴趣。无论您是修复错误、改进现有功能还是添加全新内容，我们都欢迎您的贡献！


# 交流 & 支持

## Discord <a href="https://discord.gg/5uNpPsEJz8"><img src="https://img.shields.io/discord/1197874288963895436?style=social&logo=discord"></a>
欢迎加入QAnything [Discord](https://discord.gg/5uNpPsEJz8) 社区！



## 微信
欢迎关注微信公众号，获取最新QAnything信息

<img src="docs/images/qrcode_for_qanything.jpg" width="30%" height="auto">

欢迎扫码进入QAnything交流群

<img src="docs/images/Wechat.jpg" width="30%" height="auto">

## 邮箱
如果你需要私信我们团队，请通过下面的邮箱联系我们：

qanything@rd.netease.com

## GitHub issues & discussions
有任何公开的问题，欢迎提交issues，或者在discussions区讨论
- [Github issues](https://github.com/netease-youdao/QAnything/issues)
- [Github discussions](https://github.com/netease-youdao/QAnything/discussions)
<a href="https://github.com/netease-youdao/QAnything/discussions">
  <!-- Please provide path to your logo here -->
  <img src="https://github.com/netease-youdao/QAnything/assets/29041332/ad027ec5-0bbc-4ea0-92eb-81b30c5359a1" alt="Logo" width="600">
</a>


# 协议

**有道速读** 依照 [Apache 2.0 协议](./LICENSE)开源。

