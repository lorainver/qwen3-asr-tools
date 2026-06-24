# 方案 C 实施记录 — 消息级索引 + Chunk 上下文

**日期**：2026-06-24

## 概述

为 qwen3-asr 知识库（RAG）实现了消息级精准检索方案，解决原始 chunk 级检索粒度太粗的问题。

## 实现内容

### 1. `knowledge_store.py` 改动

**VectorStore 双集合架构**：
- `knowledge_base`（主集合）：保留 chunk 级存储，用于生成回答时的上下文
- `knowledge_base_messages`（消息集合）：新增消息级存储，用于精准检索
- 初始化时同时创建两个集合，分别打印数量

**新增方法**：
- `add_messages(messages, embeddings)`：批量添加消息级索引
- `search_messages(query_embedding, top_k, where)`：消息集合检索
- `get_chunk_by_id(chunk_id)`：从主集合按 ID 获取 chunk 全文
- `get_stats()`：返回含 total_messages 的完整统计
- `delete_by_filename()`：同步清理两个集合
- `msg_count()`：消息集合总数

**WeChatChunker.extract_messages(md_path, chunk_results)**：
- 从微信 Markdown 文件解析单条消息
- 为每条消息找到所属 chunk（通过字符串包含匹配）
- 过滤掉图片/链接等无意义消息
- 返回含 id/text/metadata（sender, time, chunk_id, filename）的消息列表
- 消息 ID：`msg_{doc_md5}_{msg_idx}`（基于文件 MD5 + 序号，避免碰撞）

**RAGChain._retrieve()** 重构为双路径：
- 消息集合非空 → `_retrieve_via_messages()`（方案 C）
- 消息集合为空 → 回退传统 chunk 级检索
- `_retrieve_via_messages()` 流程：
  1. 搜消息集合（top_k * 3，≥20）
  2. 按 chunk_id 去重，保留最高分消息
  3. 取父 chunk 完整文本 + 消息级元数据
  4. 返回 enriched SearchHit（含 `_matched_sender`, `_matched_time`, `_matched_text`）

**index_document()** 修改：
- 微信聊天记录在索引 chunks 后，额外调用 `extract_messages()` 创建消息级索引

### 2. `knowledge_api.py` 改动

- 添加 `import re`
- `KBStatsResponse` 新增 `total_messages` 字段
- `list_kb_docs()` 显示每条文档的消息数
- `/api/kb/reindex_messages`：新增重建端点，清空旧消息集合后重新索引
- `kb_stats()` 返回 `total_messages`

## 测试验证

- 重建消息索引：1626 条消息（源自 9 个群聊、301 chunks、3822 条原始消息）
- 过滤后 1626 条：排除了图片/链接/空消息
- 每条消息含：chunk_id, sender, time, filename
- `/api/kb/stats` 正常显示：301 chunks, 1626 messages, 9 docs

## 架构示意图

```
用户提问
  │
  ▼
问题向量化 (nomic-embed-text, CPU)
  │
  ├──▶ 消息集合检索 (knowledge_base_messages)
  │     top_k*3 条 → 按 chunk_id 去重 → 取 top_k chunk
  │
  ├──▶ 无消息时回退 Chunk 检索
  │
  ▼
搜索命中（含完整 chunk 上下文 + 消息级元数据）
  │
  ▼
LLM 生成回答 (Ollama)
```

## 已知限制

- 消息级重建需要从源文件重新解析，依赖源文件在 documents/ 目录下存在
- 非微信聊天记录（纯文本/PDF 等）不支持消息级索引，自动回退 chunk 检索
- AI 回答生成速度受 Ollama 模型性能影响
