# Agent 与工具：qwen3-asr 自研实现 vs LangChain 对比详解

## 🎯 什么是 Agent 与工具？

**核心概念**：让 LLM 不只是"聊天"，而是能**调用外部工具**完成实际任务。

```
用户提问 → LLM 判断是否需要工具 → 调用工具 → 获取结果 → 生成回答
                ↑                          |
                └──── 决策循环 ─────────────┘
```

**类比**：人脑（LLM）+ 双手（工具）。光有脑不能干活，得有手才能操作。

---

## 📐 你项目的 Agent 架构（自研）

### 整体流程图

```
┌─────────────────────────────────────────────────────────────┐
│  用户请求 (ChatRequest)                                      │
│  enable_search=True/False, optimize_search=True/False        │
└──────────────────────┬──────────────────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────────────────┐
│  ai_worker.py :: api_chat_stream()                           │
│                                                              │
│  ① 上下文截断 (trim_messages)                                 │
│     └→ 保留 system + 最近对话，截断旧消息                       │
│                                                              │
│  ② 判断是否需要搜索 (if enable_search)                        │
│     ├→ 提取最后一条用户消息                                     │
│     ├→ [可选] AI 关键词优化 (LLM → 提炼搜索词)                 │
│     ├→ 执行搜索 (WebSearcher)                                 │
│     │   ├→ SearXNG (私有) → Serper (Google) → DuckDuckGo     │
│     │   └→ BM25 重排序                                        │
│     └→ 搜索结果注入为 system 消息                               │
│                                                              │
│  ③ 流式生成 (summarizer.chat_stream)                         │
│     ├→ 本地模型 (HuggingFace/Transformers)                    │
│     ├→ Ollama 模型 (本地 API)                                 │
│     └→ 远程模型 (OpenAI 兼容 API)                              │
│                                                              │
│  ④ 返回 SSE 流式响应                                          │
└──────────────────────────────────────────────────────────────┘
```

### 关键代码解析

#### 1️⃣ 工具定义：WebSearcher（web_searcher.py）

```python
# 你的实现：一个类封装了完整的搜索工具
class WebSearcher:
    def search(self, query, max_results=5) -> List[SearchResult]:
        # 三引擎自动降级：SearXNG → Serper → DuckDuckGo
        # + BM25 重排序
    
    def format_for_llm(self, results) -> str:
        # 将搜索结果格式化为 LLM 可理解的文本
```

**LangChain 对应**：
```python
from langchain.tools import Tool
from langchain_community.utilities import SerpAPIWrapper

search = Tool(
    name="web_search",
    description="搜索互联网获取最新信息",
    func=SerpAPIWrapper().run
)
```

#### 2️⃣ Agent 决策逻辑：ai_worker.py 中的搜索判断

```python
# 你的实现：硬编码的条件判断
if request.enable_search and searcher:
    # 1. 提取用户最后一条消息
    last_user_msg = ...
    
    # 2. [可选] AI 关键词优化
    if request.optimize_search and len(query_text) > 10:
        keywords = summarizer.chat([{"role": "user", "content": keyword_prompt}])
        search_query = keywords
    
    # 3. 执行搜索
    search_results = searcher.search(search_query)
    search_context = searcher.format_for_llm(search_results)
    
    # 4. 注入搜索结果到消息中
    messages.insert(last_user_idx, search_system_msg)
```

**LangChain 对应**：
```python
from langchain.agents import initialize_agent, AgentType

# LLM 自己决定是否调用工具
agent = initialize_agent(
    tools=[search_tool],
    llm=llm,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION
)

# agent.run("今天日元汇率是多少？")
# → LLM 自动判断：需要搜索 → 调用 search_tool → 获取结果 → 回答
```

#### 3️⃣ 工具结果注入方式

```python
# 你的实现：手动插入 system 消息
search_system_msg = {
    "role": "system",
    "content": f"""【实时联网搜索到的事实资料】
{search_context}

【回答要求】
1. 必须严格按照上述"事实资料"回答。
2. 如果资料中没提到的信息，不要脑补。"""
}
messages.insert(last_user_idx, search_system_msg)
```

**LangChain 对应**：
```python
# LangChain 自动处理工具结果的注入
# Agent 内部自动将工具输出追加到消息历史中
# 开发者无需手动管理消息插入位置
```

---

## 🔍 逐功能对比

### 1. 工具注册与发现

| 能力 | 你的实现 | LangChain |
|------|---------|-----------|
| **注册工具** | 硬编码在 ai_worker.py | `Tool(name, func, description)` |
| **工具数量** | 1个（搜索） | 无限（可注册任意工具） |
| **工具描述** | 代码逻辑隐含 | 显式 description，LLM 可读 |
| **动态添加** | 需改代码重启 | 运行时动态添加 |

**你的方式**：
```python
# 工具是否使用 = 前端传参决定
if request.enable_search and searcher:  # 硬编码判断
    searcher.search(query)
```

**LangChain 方式**：
```python
# LLM 自己根据工具描述决定是否使用
tools = [
    Tool(name="search", description="搜索互联网", func=search),
    Tool(name="calculator", description="数学计算", func=calc),
    Tool(name="weather", description="查天气", func=get_weather),
]
agent = initialize_agent(tools, llm, ...)
agent.run("北京今天多少度？")
# → LLM 自动选择 weather 工具，不会调用 search 或 calculator
```

### 2. Agent 决策方式

| 能力 | 你的实现 | LangChain |
|------|---------|-----------|
| **决策者** | 前端参数（enable_search） | LLM 自己判断 |
| **决策逻辑** | 硬编码 if/else | ReAct / Function Calling |
| **多步推理** | ❌ 不支持 | ✅ 支持（Thought→Action→Observation 循环） |
| **工具选择** | 只有搜索1个 | 多个工具自动选择 |
| **失败重试** | 降级到下一个搜索引擎 | 可配置重试策略 |

**核心差异图解**：

```
【你的实现 - 硬编码决策】
用户 → 前端(enable_search=True) → 一定搜索 → 注入结果 → LLM回答
用户 → 前端(enable_search=False) → 不搜索 → 直接 LLM回答

【LangChain - LLM 自主决策】
用户 → Agent → LLM思考："这个问题需要搜索吗？"
                 ├→ 不需要 → 直接回答
                 └→ 需要 → 调用搜索工具 → 获取结果
                       └→ 结果够吗？
                            ├→ 够了 → 生成回答
                            └→ 不够 → 再搜索/换工具 → 继续推理
```

### 3. 搜索工具细节对比

| 功能 | 你的 WebSearcher | LangChain 搜索工具 |
|------|-----------------|-------------------|
| **多引擎** | ✅ SearXNG/Serper/DDG 三级降级 | ⚠️ 每个引擎一个工具 |
| **自动降级** | ✅ 内置逻辑 | ❌ 需自己实现 |
| **结果重排** | ✅ BM25 重排序 | ⚠️ 需额外集成 Cohere Reranker |
| **结果格式化** | ✅ format_for_llm() | ❌ 返回原始文本 |
| **查询优化** | ✅ AI 关键词优化 | ⚠️ 需自己加 Chain |

### 4. Query 优化（你项目的亮点）

这是你项目中**最接近 Agent 思维**的部分：

```python
# 你的实现：用 LLM 优化搜索关键词
if request.optimize_search and len(query_text) > 10:
    # 步骤1：让 LLM 提炼搜索关键词
    keyword_prompt = "先提取具体查询内容，提炼为关键搜索词..."
    keywords = summarizer.chat([{"role": "user", "content": keyword_prompt}])
    
    # 步骤2：用优化后的关键词搜索
    search_results = searcher.search(keywords)
```

**LangChain 对应**：
```python
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate

# 也是两步，但 LangChain 把它封装成了 Chain
query_optimizer = LLMChain(
    llm=llm,
    prompt=PromptTemplate(
        template="提炼搜索关键词: {query}",
        input_variables=["query"]
    )
)

optimized_query = query_optimizer.run(user_query)
search_results = search_tool.run(optimized_query)
```

### 5. 上下文管理

| 功能 | 你的实现 | LangChain |
|------|---------|-----------|
| **截断策略** | ✅ trim_messages() 保留 system + 最近 | ✅ 多种 Memory 类型 |
| **Token 估算** | ✅ estimate_tokens() 中英文分开算 | ✅ tiktoken 精确计算 |
| **消息位置** | ✅ 搜索结果插入到用户消息前 | ✅ Agent 自动管理 |

```python
# 你的实现：精细控制消息位置
last_user_idx = len(messages) - 1 - messages[::-1].index(last_user_msg)
messages.insert(last_user_idx, search_system_msg)  # 精确插入位置
```

---

## 🧠 架构差异总结

### 你的项目：**管道式架构（Pipeline）**

```
请求 → 截断 → [搜索优化 → 搜索 → 注入] → LLM生成 → 响应
       固定顺序，每步是否执行由参数控制
```

**特点**：
- ✅ 流程清晰，易于调试
- ✅ 性能可控，无额外开销
- ✅ 搜索优化是你的独创亮点
- ❌ 只能做搜索这一种工具调用
- ❌ 添加新工具需要改代码
- ❌ LLM 不能自主决定是否需要工具

### LangChain：**Agent 式架构（ReAct 循环）**

```
请求 → Agent → LLM思考 → 需要工具？→ 调用工具 → 观察结果 → 继续思考...
                  ↑                                        │
                  └────────── 循环直到得出最终答案 ───────────┘
```

**特点**：
- ✅ LLM 自主决策，灵活选择工具
- ✅ 支持多步推理（搜索→计算→再搜索）
- ✅ 添加新工具只需注册，不改核心逻辑
- ❌ 决策不可控（LLM 可能选错工具）
- ❌ 延迟更高（多轮 LLM 调用）
- ❌ Token 消耗更大（每步都要推理）
- ❌ 调试困难（决策过程是黑盒）

---

## 💡 如果用 LangChain 重写你的项目

### 当前流程（自研）
```python
# ai_worker.py - 硬编码管道
@app.post("/api/chat_stream")
async def api_chat_stream(request: ChatRequest):
    messages = trim_messages(request.messages)
    
    if request.enable_search:          # ← 前端决定
        if request.optimize_search:    # ← 前端决定
            keywords = llm.optimize(query)  # ← 固定两步
        results = searcher.search(keywords)
        messages = inject_search(messages, results)
    
    response = summarizer.chat_stream(messages)
    return StreamingResponse(response)
```

### LangChain 重写
```python
from langchain.agents import AgentExecutor, create_react_agent
from langchain.tools import Tool
from langchain_ollama import ChatOllama

# 1. 定义工具
tools = [
    Tool(name="web_search", 
         description="搜索互联网获取实时信息，如新闻、汇率、天气等",
         func=web_searcher.search_and_format),
    Tool(name="transcribe_audio",
         description="将音频/视频文件转录为文字",
         func=transcriber.transcribe),
    Tool(name="summarize_text",
         description="对长文本进行总结、翻译或润色",
         func=summarizer.process),
]

# 2. 创建 Agent
llm = ChatOllama(model="qwen2.5:7b")
agent = create_react_agent(llm, tools, prompt_template)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

# 3. 使用：LLM 自己决定调什么工具
result = agent_executor.invoke({
    "input": "帮我转录这个视频并总结要点"
})
# → LLM 自动：调用 transcribe_audio → 获取文字 → 调用 summarize_text → 返回总结
```

### 关键区别

| 对比项 | 自研管道 | LangChain Agent |
|--------|---------|-----------------|
| **工具选择** | 前端参数控制 | LLM 自主选择 |
| **添加新工具** | 改 ai_worker.py | 加一行 Tool() |
| **多工具组合** | 不支持 | 自动组合（先转录再总结） |
| **错误处理** | 手动 try/catch | Agent 自动重试/换工具 |
| **延迟** | 🟢 低（1次LLM调用） | 🔴 高（2-5次LLM调用） |
| **可控性** | 🟢 完全可控 | 🟡 LLM 可能误判 |

---

## 🎓 总结

### 你已经实现的（比 LangChain 更好的部分）

1. **🔍 三引擎自动降级** — LangChain 没有，每个搜索引擎是独立工具
2. **📊 BM25 重排序** — LangChain 需要额外集成 Cohere Reranker
3. **🧠 AI 关键词优化** — LangChain 需要自己加 Chain
4. **📍 精确消息注入位置** — LangChain Agent 是黑盒
5. **⚡ 低延迟** — 固定管道只调1次 LLM，Agent 要调多次

### LangChain 有但你没有的

1. **🤖 LLM 自主决策** — 不需要前端参数控制
2. **🔧 多工具注册** — 轻松添加任意工具
3. **🔄 多步推理循环** — 搜索→分析→再搜索
4. **🛡️ 工具失败重试** — Agent 自动换策略
5. **📝 工具描述标准化** — LLM 可理解每个工具的用途

### 建议

你的项目目前是**管道模式**（Pipeline），适合 ASR+文本处理的固定流程。
如果想升级为**Agent 模式**，不需要全面引入 LangChain，可以：

```python
# 最小改动：在现有管道上加一个"路由层"
# 让 LLM 决定走哪条管道
def route_request(user_query):
    """用 LLM 判断用户意图，选择处理管道"""
    intent = llm.classify(user_query)  # "聊天" / "搜索" / "转录" / "总结"
    
    if intent == "搜索":
        return chat_with_search(user_query)
    elif intent == "转录":
        return transcribe_pipeline(user_query)
    elif intent == "总结":
        return summarize_pipeline(user_query)
    else:
        return chat_directly(user_query)
```

这样既保留了管道模式的**高性能**，又获得了 Agent 模式的**灵活性**。
