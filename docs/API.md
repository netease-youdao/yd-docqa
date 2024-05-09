# 有道速读开源 接口文档


## <h2><p id="上传文档POST">1. 上传文档（POST）</p></h2>

### <h3>URL：<http://{your_host}:38765/upload> </h3>

### <h3><p id="上传文档请求参数">上传文档请求参数</p></h3>

Body: form-data

| 参数名  | 示例参数值 | 是否必填 | 参数类型 | 描述说明                                |
| ------- | ---------- | -------- | -------- | --------------------------------------- |
| file   | 文件二进制                         | 是       | File     | 需要上传的文件，目前仅支持pdf                      |
| do_summarize | "true"      | 是       | String   | 是否生成逐段摘要，生成后可通过`chunk2summary`接口获取指定段落的摘要 |
| do_prepare_for_QA | "true"  | 是       | String   | 是否构建用于问答的向量数据库             |

### <h3><p id="上传文档请求示例">上传文档请求示例</p></h3>

JavaScript XHR：
```javascript
const data = new FormData();
data.append("file", ["/Users/xiaoyunlong/Downloads/cxy-test2.pdf"]);
data.append("do_summarize", "true");
data.append("do_prepare_for_QA", "true");

const xhr = new XMLHttpRequest();
xhr.withCredentials = true;

xhr.addEventListener("readystatechange", function () {
  if (this.readyState === this.DONE) {
    console.log(this.responseText);
  }
});

xhr.open("POST", "http://127.0.0.1:38765/upload");

xhr.send(data);
```

### <h3><p id="上传文档响应示例">上传文档响应示例</p></h3>

```json
{
	"chunks": [
		{
			"chunk_id": "0",
			"chunk_type": "title",
			"enriched_text": "尽可能少，尽可能多:\n基于对比条件反射的过翻译和欠翻译检测\nJannis Vamvas1 and Rico Sennrich1,2\n\n1Department of Computational Linguistics, University of Zurich\n2School of Informatics, University of Edinburgh\n{vamvas,sennrich}@cl.uzh.ch\n",
			"enriched_text_tokens": 90,
			"locations": [ // locations 中的坐标和字体大小，都用于前端渲染高亮文本块
				{
					"bbox": [
						168,
						80,
						426,
						109
					],
					"lines": [
						{
							"line_bbox": "169, 78, 258, 32",
							"line_fontsize": 30,
							"line_text": "尽可能少，尽可能多:\n基于对比条件反射的过翻译和欠翻译检测\n"
						}
					],
					"page_h": 842,
					"page_id": 0,
					"page_w": 595
				}
			],
			"page_ids": [
				0
			],
			"real_text": "尽可能少，尽可能多:\n基于对比条件反射的过翻译和欠翻译检测\n",
			"summary": {},
			"summary_status": 0, // summary_status = 0 表示不需要摘要（chunk_type一般是title类型）；1 表示需要摘要（chunk_type是正文text类型）。
			"text": "尽可能少，尽可能多:\n基于对比条件反射的过翻译和欠翻译检测\n"
		},
		{
			"chunk_id": "1",
			"chunk_type": "normal",
			"enriched_text": "尽可能少，尽可能多:\n基于对比条件反射的过翻译和欠翻译检测\nJannis Vamvas1 and Rico Sennrich1,2\n\n1Department of Computational Linguistics, University of Zurich\n2School of Informatics, University of Edinburgh\n{vamvas,sennrich}@cl.uzh.ch\nAbstract\n",
			"enriched_text_tokens": 92,
			"locations": [
				{
					"bbox": [
						146,
						127,
						453,
						181
					],
					"lines": [
						{
							"line_bbox": "202, 122, 193, 19",
							"line_fontsize": 17,
							"line_text": "Jannis Vamvas1 and Rico Sennrich1,2\n"
						},
						{
							"line_bbox": "145, 140, 308, 42",
							"line_fontsize": 40,
							"line_text": "1Department of Computational Linguistics, University of Zurich\n2School of Informatics, University of Edinburgh\n{vamvas,sennrich}@cl.uzh.ch\n"
						}
					],
					"page_h": 842,
					"page_id": 0,
					"page_w": 595
				}
			],
			"page_ids": [
				0
			],
			"real_text": "Jannis Vamvas1 and Rico Sennrich1,2\n\n1Department of Computational Linguistics, University of Zurich\n2School of Informatics, University of Edinburgh\n{vamvas,sennrich}@cl.uzh.ch\n",
			"summary": {},
			"summary_status": 1,
			"text": "Jannis Vamvas1 and Rico Sennrich1,2\n\n1Department of Computational Linguistics, University of Zurich\n2School of Informatics, University of Edinburgh\n{vamvas,sennrich}@cl.uzh.ch\n"
		},
		
		...
		
		{
			"chunk_id": "7",
			"chunk_type": "normal",
			"enriched_text": "1\n简介\nNMT中的覆盖错误\n在各种语言的人工评价\n研究中都观察到了目标词的添加和省略，其中\n省略是出现频率较高的错误类型(Castilho et al.,\n2017; Zheng et al., 2018)。它们作为典型的翻译\n问题包含在多维质量度量(MQM)框架(Lommel\net al., 2014)中。添加被定义为准确性问题，当\n目标文本包含源文本中不存在的文本时，省略\n被定义为准确性问题，即翻译中缺少内容，但\n源文本中存在内容。2\n\nFreitag et al. (2021) 使用MQM手工重新标注\n提交给WMT 2020新闻翻译任务(Barrault et al.,\n2020)的英德和汉英机器翻译。他们的发现证\n实了最先进的神经机器翻译系统仍然会错误\n地添加和省略目标词，而且省略的情况比添加\n的情况更频繁。类似的模式可以在英法机器翻\n译中找到，这些机器翻译已经用文档级QE共\n享任务(Specia et al., 2018; Fonseca et al., 2019;\nSpecia et al., 2020)的细粒度MQM标签进行了注\n释。\n\n检测和减少覆盖率错误\n基于参考的方法包括\n测量n-gram与参考的重叠(Yang et al., 2018)和\n分析与源词的对齐(Kong et al., 2019)，这项工\n作侧重于无参考的覆盖错误检测。\n神经机器翻译(NMT)容易出现添加多余目标词\n或遗漏重要源内容等覆盖错误。以前检测此\n类错误的方法使用参考翻译(Yang et al., 2018)\n或者采用一个单独的质量估计(QE)模型，该模\n型在针对语言对(Tuan et al., 2021; Zhou et al.,\n2021)的合成数据上进行训练。\n本文提出了一种基于假设推理的无参考算\n法。我们的前提是，如果翻译使用尽可能少\n的信息而使用尽可能多的信息来传达源序列，\n那么翻译就具有最佳的覆盖率。因此，额外的\n错误意味着包含较少信息的翻译将更好地传达\n源。相反，省略错误意味着译文更适合信息较\n少的源序列。\n采用我们的对比条件反射方法(Vamvas and\nSennrich, 2021)，我们使用NMT模型的概率分\n数来近似这种覆盖率的概念。为源序列和翻\n译创建解析树，并将它们的组成部分视为信\n息单元。遗漏错误是通过系统地从源序列中删\n除部分成分和估计以该部分源序列为条件的翻\n译概率来检测的。如果概率分数高于以完整源\n为条件的翻译，则删除的组成部分可能在翻译\n中没有对应项(图1)。通过交换源序列和目标\n序列，我们将相同的原理应用于加法错误的检\n测。\n当将检测到的错误与片段级别上人工标注的\n覆盖错误进行比较(Freitag et al., 2021)时，所\n提出方法超过了在大量合成覆盖错误上训练的\n监督QE基线。人工评分人员发现，单词级别\n",
			"enriched_text_tokens": 1079,
			"locations": [
				{
					"bbox": [
						305,
						387,
						525,
						709
					],
					"lines": [
						{
							"line_bbox": "306, 387, 220, 120",
							"line_fontsize": 118,
							"line_text": "NMT中的覆盖错误\n在各种语言的人工评价\n研究中都观察到了目标词的添加和省略，其中\n省略是出现频率较高的错误类型(Castilho et al.,\n2017; Zheng et al., 2018)。它们作为典型的翻译\n问题包含在多维质量度量(MQM)框架(Lommel\net al., 2014)中。添加被定义为准确性问题，当\n目标文本包含源文本中不存在的文本时，省略\n被定义为准确性问题，即翻译中缺少内容，但\n源文本中存在内容。2\n"
						},
						{
							"line_bbox": "306, 511, 220, 133",
							"line_fontsize": 131,
							"line_text": "Freitag et al. (2021) 使用MQM手工重新标注\n提交给WMT 2020新闻翻译任务(Barrault et al.,\n2020)的英德和汉英机器翻译。他们的发现证\n实了最先进的神经机器翻译系统仍然会错误\n地添加和省略目标词，而且省略的情况比添加\n的情况更频繁。类似的模式可以在英法机器翻\n译中找到，这些机器翻译已经用文档级QE共\n享任务(Specia et al., 2018; Fonseca et al., 2019;\nSpecia et al., 2020)的细粒度MQM标签进行了注\n释。\n"
						},
						{
							"line_bbox": "306, 658, 218, 51",
							"line_fontsize": 49,
							"line_text": "检测和减少覆盖率错误\n基于参考的方法包括\n测量n-gram与参考的重叠(Yang et al., 2018)和\n分析与源词的对齐(Kong et al., 2019)，这项工\n作侧重于无参考的覆盖错误检测。\n"
						}
					],
					"page_h": 842,
					"page_id": 0,
					"page_w": 595
				}
			],
			"page_ids": [
				0
			],
			"real_text": "NMT中的覆盖错误\n在各种语言的人工评价\n研究中都观察到了目标词的添加和省略，其中\n省略是出现频率较高的错误类型(Castilho et al.,\n2017; Zheng et al., 2018)。它们作为典型的翻译\n问题包含在多维质量度量(MQM)框架(Lommel\net al., 2014)中。添加被定义为准确性问题，当\n目标文本包含源文本中不存在的文本时，省略\n被定义为准确性问题，即翻译中缺少内容，但\n源文本中存在内容。2\n\nFreitag et al. (2021) 使用MQM手工重新标注\n提交给WMT 2020新闻翻译任务(Barrault et al.,\n2020)的英德和汉英机器翻译。他们的发现证\n实了最先进的神经机器翻译系统仍然会错误\n地添加和省略目标词，而且省略的情况比添加\n的情况更频繁。类似的模式可以在英法机器翻\n译中找到，这些机器翻译已经用文档级QE共\n享任务(Specia et al., 2018; Fonseca et al., 2019;\nSpecia et al., 2020)的细粒度MQM标签进行了注\n释。\n\n检测和减少覆盖率错误\n基于参考的方法包括\n测量n-gram与参考的重叠(Yang et al., 2018)和\n分析与源词的对齐(Kong et al., 2019)，这项工\n作侧重于无参考的覆盖错误检测。\n",
			"summary": {},
			"summary_status": 1,
			"text": "NMT中的覆盖错误\n在各种语言的人工评价\n研究中都观察到了目标词的添加和省略，其中\n省略是出现频率较高的错误类型(Castilho et al.,\n2017; Zheng et al., 2018)。它们作为典型的翻译\n问题包含在多维质量度量(MQM)框架(Lommel\net al., 2014)中。添加被定义为准确性问题，当\n目标文本包含源文本中不存在的文本时，省略\n被定义为准确性问题，即翻译中缺少内容，但\n源文本中存在内容。2\n\nFreitag et al. (2021) 使用MQM手工重新标注\n提交给WMT 2020新闻翻译任务(Barrault et al.,\n2020)的英德和汉英机器翻译。他们的发现证\n实了最先进的神经机器翻译系统仍然会错误\n地添加和省略目标词，而且省略的情况比添加\n的情况更频繁。类似的模式可以在英法机器翻\n译中找到，这些机器翻译已经用文档级QE共\n享任务(Specia et al., 2018; Fonseca et al., 2019;\nSpecia et al., 2020)的细粒度MQM标签进行了注\n释。\n\n检测和减少覆盖率错误\n基于参考的方法包括\n测量n-gram与参考的重叠(Yang et al., 2018)和\n分析与源词的对齐(Kong et al., 2019)，这项工\n作侧重于无参考的覆盖错误检测。\n"
		},
		
		... // 篇幅有限，省略更多段落内容
		
	],
	"doc_id": "b9532f7000291f2049318d4921947e66" // 用于后续请求 chunk2summary 和 chat_qa 时，指定当前访问的文档是哪篇。
}
```

## <h2><p id="获取段落摘要">2. 获取段落摘要（GET）</p></h2>

### <h3>URL：<http://{your_host}:38765/chunk2summary></p></h3>

### <h3><p id="获取段落摘要请求参数body">获取段落摘要请求参数（Body）</p></h3>
Body: json

| 参数名      | 示例参数值                           | 是否必填 | 参数类型 | 描述说明              |
| ----------- | ------------------------------------ | -------- | -------- | --------------------- |
| doc_id   | "57d64892efb0eec8e648112c62fa9fac"      | 是       | String   | 文档id，即`upload`接口返回的`doc_id` |
| chunk_id       | "27" | 是       | String   | 待获取摘要的段落id，对应于`upload`接口返回的`chunks`中各个段落的`chunk_id` |
| lang       | "zh" | 是       | String   | 摘要语种，可选值为"zh"（中文）、"en"（英文） |

### <h3><p id="获取段落摘要请求示例">获取段落摘要请求示例</p></h3>

JavaScript XHR：
```javascript
const data = "{\n   \"doc_id\": \"57d64892efb0eec8e648112c62fa9fac\", \n    \"chunk_id\": \"27\",\n    \"lang\": \"zh\"\n}";

const xhr = new XMLHttpRequest();
xhr.withCredentials = true;

xhr.addEventListener("readystatechange", function () {
  if (this.readyState === this.DONE) {
    console.log(this.responseText);
  }
});

xhr.open("GET", "http://127.0.0.1:38765/chunk2summary");
xhr.setRequestHeader("content-type", "application/json");

xhr.send(data);
```

### <h3><p id="获取段落摘要响应示例">获取段落摘要响应示例</p></h3>

```json
{
    "state":"Done",
    "tldr":"1. \u521d\u59cb\u72b6\u6001\uff1a\u5bf9\u8bdd\u5f00\u59cb\u548c\u7528\u6237\u67e5\u8be2\u5b8c\u5168\u5904\u7406\u540e\u8fd4\u56de\u7684\u72b6\u6001\u3002\n2. \u9000\u51fa\u72b6\u6001\uff1a\u7cfb\u7edf\u68c0\u6d4b\u5230\u7528\u6237\u60f3\u8981\u7ec8\u6b62\u5bf9\u8bdd\u65f6\u8fdb\u5165\u7684\u72b6\u6001\u30021. \u521d\u59cb\u72b6\u6001\uff1a\u5bf9\u8bdd\u5f00\u59cb\u548c\u7528\u6237\u67e5\u8be2\u5b8c\u5168\u5904\u7406\u540e\u8fd4\u56de\u7684\u72b6\u6001\u3002\n2. \u9000\u51fa\u72b6\u6001\uff1a\u7cfb\u7edf\u68c0\u6d4b\u5230\u7528\u6237\u60f3\u8981\u7ec8\u6b62\u5bf9\u8bdd\u65f6\u8fdb\u5165\u7684\u72b6\u6001\u3002"
}

```


## <h2><p id="问答post">3. 问答（POST）</p></h2>

### <h3> URL：<http://{your_host}:38765/chat_qa></p></h3>

### <h3><p id="问答请求参数"> 问答请求参数</p></h3>

参数包括两部分：
1. Query：

| 参数名    | 示例参数值                                                                   | 是否必填 | 参数类型     | 描述说明                                 |
| --------- | ---------------------------------------------------------------------------- | -------- | ------------ | ---------------------------------------- |
| doc_id   | "b9532f7000291f2049318d4921947e66"                                                                        | 是       | String       | 文档id，即`upload`接口返回的`doc_id`                                  |
| message    | "本文讲了啥？" | 是       | String        | 用户问题 |
| stream_json   | "true"                          | 是       | String | 返回的消息片段是否包装为json。若置为`"false"`，则每个片段会直接返回裸文本，会丢失片段首尾的空格、换行符等。                                 |


2. Body：form-data  

| 参数名    | 示例参数值                                                                   | 是否必填 | 参数类型     | 描述说明                                 |
| --------- | ---------------------------------------------------------------------------- | -------- | ------------ | ---------------------------------------- |
| attachment   | "/9j/4AAQSkZJRgABAQEASABIAAD......"（略）                                                                        | 否       | String       | 截图问答时的图片 base64 编码字符串           



### <h3><p id="-问答流式请求示例"> 问答流式请求示例</p></h3>

JavaScript XHR：
```javascript
const data = new FormData();

const xhr = new XMLHttpRequest();
xhr.withCredentials = true;

xhr.addEventListener("readystatechange", function () {
  if (this.readyState === this.DONE) {
    console.log(this.responseText);
  }
});

xhr.open("POST", "http://127.0.0.1:38765/chat_qa?doc_id=57d64892efb0eec8e648112c62fa9fac&message=本文讲了啥&stream_json=true");

xhr.send(data);
```

### <h3><p id="-问答流式响应示例"> 问答流式响应示例</p></h3>

末尾的 `docsrc` 片段是“信息来源”。
```Text
data: {"content": "根"}

data: {"content": "据"}

data: {"content": "提"}

data: {"content": "供"}

data: {"content": "的"}

data: {"content": "参"}

data: {"content": "考"}

data: {"content": "信息"}

data: {"content": "，"}

data: {"content": "本"}

data: {"content": "文"}

data: {"content": "主"}

data: {"content": "要"}

data: {"content": "讨"}

data: {"content": "论"}

data: {"content": "了"}

... // 省略中间内容

data: {"content": "的"}

data: {"content": "保"}

data: {"content": "护"}

data: {"content": "和"}

data: {"content": "修"}

data: {"content": "复"}

data: {"content": "工"}

data: {"content": "作"}

data: {"content": "。"}

event: docsrc
data: {"sources": [{"doc_id": "2b338b1cc1df448daff4d79dfcf5f956", "chunk_id": "1", "_inside_chunk_id": "VIRT-8", "clickable_chunk_id": "1", "page_id": 0}, {"doc_id": "2b338b1cc1df448daff4d79dfcf5f956", "chunk_id": "2", "_inside_chunk_id": "VIRT-8", "clickable_chunk_id": "2", "page_id": 0}, {"doc_id": "2b338b1cc1df448daff4d79dfcf5f956", "chunk_id": "4", "_inside_chunk_id": "VIRT-8", "clickable_chunk_id": "4", "page_id": 0}, {"doc_id": "2b338b1cc1df448daff4d79dfcf5f956", "chunk_id": "6", "_inside_chunk_id": "VIRT-15", "clickable_chunk_id": "6", "page_id": 0}]}


event: end
data: {"message": "Connection closed", "sources": [{"doc_id": "2b338b1cc1df448daff4d79dfcf5f956", "chunk_id": "1", "_inside_chunk_id": "VIRT-8", "clickable_chunk_id": "1", "page_id": 0}, {"doc_id": "2b338b1cc1df448daff4d79dfcf5f956", "chunk_id": "2", "_inside_chunk_id": "VIRT-8", "clickable_chunk_id": "2", "page_id": 0}, {"doc_id": "2b338b1cc1df448daff4d79dfcf5f956", "chunk_id": "4", "_inside_chunk_id": "VIRT-8", "clickable_chunk_id": "4", "page_id": 0}, {"doc_id": "2b338b1cc1df448daff4d79dfcf5f956", "chunk_id": "6", "_inside_chunk_id": "VIRT-15", "clickable_chunk_id": "6", "page_id": 0}]}
```


## <h2><p id="获取已解析过的PDF信息">4. 获取已解析过的PDF信息（GET）</p></h2>

### <h3>URL：<http://{your_host}:38765/get_pdf_info/{doc_id}></p></h3>

### <h3><p id="获取已解析过的PDF信息请求参数">获取已解析过的PDF信息请求参数</p></h3>
无参数。把 doc_id 直接拼在 URL 中即可。

### <h3><p id="获取已解析过的PDF信息请求示例">获取已解析过的PDF信息请求示例</p></h3>

JavaScript XHR：
```javascript
const data = null;

const xhr = new XMLHttpRequest();
xhr.withCredentials = true;

xhr.addEventListener("readystatechange", function () {
  if (this.readyState === this.DONE) {
    console.log(this.responseText);
  }
});

xhr.open("GET", "http://127.0.0.1:38765/get_pdf_info/b9532f7000291f2049318d4921947e66");

xhr.send(data);
```

### <h3><p id="获取已解析过的PDF信息响应示例">获取已解析过的PDF信息响应示例</p></h3>

```json
{
    "chunks": ... // 略。结构与 upload 接口返回的 chunks 字段完全一致。
    "pdf_url": "files/b9532f7000291f2049318d4921947e66/b9532f7000291f2049318d4921947e66.pdf"
}

```


## <h2><p id="获取PDF文件">5. 获取PDF文件（GET）</p></h2>

### <h3>URL：<http://{your_host}:38765/{pdf_url}></p></h3>

### <h3><p id="获取PDF文件请求参数">获取PDF文件请求参数</p></h3>
无参数。把 `get_pdf_info` 接口返回的 `pdf_url` 直接拼在 URL 中即可。

### <h3><p id="获取PDF文件请求示例">获取PDF文件请求示例</p></h3>

JavaScript XHR：
```javascript
const data = null;

const xhr = new XMLHttpRequest();
xhr.withCredentials = true;

xhr.addEventListener("readystatechange", function () {
  if (this.readyState === this.DONE) {
    console.log(this.responseText);
  }
});

xhr.open("GET", "http://127.0.0.1:38765/files/b9532f7000291f2049318d4921947e66/b9532f7000291f2049318d4921947e66.pdf");

xhr.send(data);
```

### <h3><p id="获取已解析过的PDF信息响应示例">获取已解析过的PDF信息响应示例</p></h3>

略。该请求返回的就是PDF文件。


