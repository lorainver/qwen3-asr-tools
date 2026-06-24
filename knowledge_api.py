"""
Knowledge Base API — Qwen3-ASR 知识库
提供知识库的文档管理、语义搜索、RAG对话等 API
"""

import json
import os
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form
from pydantic import BaseModel
import logging

from knowledge_store import (
    get_embedder, get_vectorstore, get_rag_chain, is_initialized,
    index_document, delete_by_filename
)

logger = logging.getLogger(__name__)

# ==================== 数据模型 ====================

class KBSearchRequest(BaseModel):
    query: str
    top_k: int = 5
    filter_category: Optional[str] = None
    filter_filename: Optional[str] = None


class KBChatRequest(BaseModel):
    question: str
    top_k: int = 5
    filter_category: Optional[str] = None
    filter_filename: Optional[str] = None
    model_id: Optional[str] = None


class KBSearchResponse(BaseModel):
    query: str
    total: int
    results: List[dict]


class KBChatResponse(BaseModel):
    answer: str
    sources: List[dict]


class KBStatsResponse(BaseModel):
    total_chunks: int
    total_messages: int
    total_docs: int
    categories: List[str]


class KBDocResponse(BaseModel):
    docs: List[dict]
    count: int


# ==================== 路由 ====================

router = APIRouter(prefix="/api/kb", tags=["知识库"])


def _filter_hits_by_filename(hits, filename_substr: str, top_k: int):
    """Python 后置过滤：按文件名子串匹配（ChromaDB $contains 不支持中文）"""
    if not filename_substr or not hits:
        return hits
    filtered = [h for h in hits if filename_substr in h.metadata.get('filename', '')]
    return filtered[:top_k]


def _extract_mention(text: str) -> Tuple[str, str]:
    """
    从问题文本中提取 @群名 语法。
    
    例如 "@信竞群 最近主要讨论了什么" → ("信竞群", "最近主要讨论了什么")
    如果没有 @群名，返回 (None, 原文本)
    
    Returns:
        (群名子串, 清理后的提问文本)
    """
    import re
    # 匹配 @后跟中文/英文/数字，直到遇到空格或标点
    m = re.search(r'@([^\s，。！？,。!?]+)', text)
    if m:
        group = m.group(1).strip()
        cleaned = text[:m.start()] + text[m.end():]
        cleaned = cleaned.strip()
        return group, cleaned
    return None, text


_external_summarizer = None


def set_summarizer(summarizer):
    """由 ai_worker.py 调用，注入全局 summarizer 实例"""
    global _external_summarizer
    _external_summarizer = summarizer


def _build_source_list(hits) -> List[dict]:
    """将 hit 列表转换为 sources 列表（按文件名去重）"""
    seen_filenames = set()
    sources = []
    for hit in hits:
        filename = hit.metadata.get('filename', '')
        if filename in seen_filenames:
            continue
        seen_filenames.add(filename)
        text_preview = hit.text[:200] + "..." if len(hit.text) > 200 else hit.text
        sources.append({
            "filename": filename,
            "category": hit.metadata.get('category', ''),
            "text": text_preview,
            "score": round(hit.score, 4)
        })
    return sources


# ==================== 初始化 ====================

@router.post("/init")
async def init_knowledge_base():
    """初始化知识库（重建 Embedding 模型和 VectorStore 连接）"""
    try:
        from knowledge_store import initialize_knowledge_base
        result = initialize_knowledge_base()
        return {"status": "ok", "message": "知识库初始化成功", "result": result}
    except Exception as e:
        logger.error(f"知识库初始化失败: {e}")
        raise HTTPException(status_code=500, detail=f"初始化失败: {str(e)}")


# ==================== 文档管理 ====================

@router.post("/upload", response_model=dict)
async def upload_document(
    file: UploadFile = File(...),
    category: str = Form(default="default")
):
    """上传并索引文档"""
    if not is_initialized():
        raise HTTPException(status_code=500, detail="知识库未初始化，请先调用 /api/kb/init")

    try:
        docs_root = Path("D:/qwen3-asr/knowledge_base/documents")
        docs_root.mkdir(parents=True, exist_ok=True)

        file_path = docs_root / file.filename
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        result = index_document(str(file_path), category=category)
        return {"status": "ok", "message": f"文档 {file.filename} 上传并索引成功", "result": result}
    except Exception as e:
        logger.error(f"文档上传失败: {e}")
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")


@router.get("/docs", response_model=KBDocResponse)
async def list_kb_docs():
    """列出知识库中的所有文档"""
    if not is_initialized():
        raise HTTPException(status_code=500, detail="知识库未初始化")

    try:
        from knowledge_store import get_vectorstore
        store = get_vectorstore()

        # 获取 chunks 统计
        all_chunks = store.collection.get(include=["metadatas"])
        # 获取消息级统计
        all_msgs = store.msg_collection.get(include=["metadatas"])

        # 按文件名聚合 chunk 统计
        file_map = {}
        for meta in all_chunks.get("metadatas", []):
            filename = meta.get("filename", "unknown")
            if filename not in file_map:
                file_map[filename] = {
                    "filename": filename,
                    "category": meta.get("category", ""),
                    "chunks": 0,
                    "messages": 0
                }
            file_map[filename]["chunks"] += 1

        # 按文件名聚合消息统计
        if all_msgs and all_msgs.get("metadatas"):
            for meta in all_msgs["metadatas"]:
                filename = meta.get("filename", "unknown")
                if filename in file_map:
                    file_map[filename]["messages"] += 1

        docs = list(file_map.values())
        return KBDocResponse(docs=docs, count=len(docs))
    except Exception as e:
        logger.error(f"列出文档失败: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"列出文档失败: {str(e)}")


@router.post("/reindex_messages")
async def reindex_messages():
    """重建消息级索引（从已有 chunks 重建）"""
    if not is_initialized():
        raise HTTPException(status_code=500, detail="知识库未初始化")

    try:
        from knowledge_store import get_vectorstore, get_embedder, WeChatChunker, CHROMA_PATH
        import hashlib
        from pathlib import Path

        store = get_vectorstore()
        embedder = get_embedder()

        # 清空旧的消息集合
        old_msg = store.msg_collection.get(include=["metadatas"])
        if old_msg and old_msg['ids']:
            store.msg_collection.delete(ids=old_msg['ids'])
            logger.info(f"🗑️ 已清空 {len(old_msg['ids'])} 条旧消息索引")

        # 获取所有 chunks
        all_chunks = store.collection.get(include=["documents", "metadatas"])
        if not all_chunks or not all_chunks['ids']:
            return {"status": "ok", "message": "知识库为空，无需重建", "total_messages": 0}

        # 按文件名分组 chunks
        file_chunks = {}
        for i, chunk_id in enumerate(all_chunks['ids']):
            meta = all_chunks['metadatas'][i]
            fn = meta.get('filename', 'unknown')
            if fn not in file_chunks:
                file_chunks[fn] = {'chunks': [], 'category': meta.get('category', '默认')}
            # 重建简单的 chunk 对象
            from knowledge_store import Chunk
            file_chunks[fn]['chunks'].append(Chunk(
                chunk_id=chunk_id,
                doc_id=meta.get('doc_id', ''),
                text=all_chunks['documents'][i],
                chunk_index=meta.get('chunk_index', 0),
                metadata=meta
            ))

        # 找到对应的源文件路径
        total_messages = 0
        for fn, data in file_chunks.items():
            # 尝试在 DOCS_PATH 下找源文件
            found_path = None
            for root, dirs, files in os.walk(str(CHROMA_PATH.parent / "documents")):
                if fn in files:
                    found_path = os.path.join(root, fn)
                    break
            if not found_path:
                logger.warning(f"⚠️ 找不到源文件 '{fn}'，跳过消息重建")
                continue

            # 检查是否为微信聊天记录
            with open(found_path, 'r', encoding='utf-8') as f:
                sample = f.read()[:1000]
            if not re.search(r'\*\*.+?\*\* \(.+?\):', sample):
                continue

            wc = WeChatChunker(chunk_size=800, overlap=50, time_window_minutes=10)
            messages = wc.extract_messages(found_path, data['chunks'])
            if not messages:
                continue

            for m in messages:
                m['metadata']['category'] = data['category']

            msg_texts = [m['text'] for m in messages]
            msg_embeddings = embedder.embed_texts(msg_texts)
            store.add_messages(messages, msg_embeddings)
            total_messages += len(messages)
            logger.info(f"📋 '{fn}' 消息重建完成: {len(messages)} 条")

        return {
            "status": "ok",
            "message": f"消息级索引重建完成，共 {total_messages} 条消息",
            "total_messages": total_messages
        }
    except Exception as e:
        logger.error(f"消息索引重建失败: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"消息索引重建失败: {str(e)}")


@router.delete("/docs/{doc_id}")
async def delete_kb_doc(doc_id: str):
    """删除文档"""
    if not is_initialized():
        raise HTTPException(status_code=500, detail="知识库未初始化")

    try:
        return {"status": "ok", "message": f"文档 {doc_id} 删除功能暂不可用"}
    except Exception as e:
        logger.error(f"删除文档失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


# ==================== 搜索 ====================

@router.get("/search")
async def search_knowledge(
    q: str = Query(..., description="搜索查询", min_length=1),
    top_k: int = Query(default=5, ge=1, le=20),
    category: Optional[str] = Query(default=None),
    filename: Optional[str] = Query(default=None, description="按文件名/群名过滤")
):
    """语义搜索知识库"""
    if not is_initialized():
        raise HTTPException(status_code=500, detail="知识库未初始化，请先调用 /api/kb/init")

    try:
        embedder = get_embedder()
        vectorstore = get_vectorstore()

        # 向量化查询
        query_embedding = embedder.embed_query(q)

        # 检索（ChromaDB 过滤 + Python 后置过滤）
        retrieve_k = top_k * 3 if filename else top_k
        where = {"category": category} if category else None
        hits = vectorstore.search(
            query_embedding=query_embedding,
            top_k=retrieve_k,
            where=where
        )

        # Python 后置过滤：按文件名子串匹配（ChromaDB $contains 不支持中文）
        if filename:
            hits = [h for h in hits if filename in h.metadata.get('filename', '')]
            hits = hits[:top_k]

        results = []
        for hit in hits:
            results.append({
                "id": hit.chunk_id,
                "filename": hit.metadata.get('filename', ''),
                "category": hit.metadata.get('category', ''),
                "text": hit.text,
                "chunk_index": hit.metadata.get('chunk_index', 0),
                "score": round(hit.score, 4),
                "distance": round(hit.distance, 4)
            })

        return KBSearchResponse(
            query=q,
            total=len(results),
            results=results
        )

    except Exception as e:
        logger.error(f"知识库搜索失败: {e}")
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")


# ==================== RAG 对话 ====================

@router.post("/chat", response_model=KBChatResponse)
async def rag_chat(request: KBChatRequest):
    """RAG 对话：检索 + 生成"""
    if not is_initialized():
        raise HTTPException(status_code=500, detail="知识库未初始化，请先调用 /api/kb/init")

    try:
        rag_chain = get_rag_chain()

        # ---- 解析 @群名 语法 ----
        mention_group, clean_question = _extract_mention(request.question)
        effective_filter = None
        if mention_group:
            effective_filter = mention_group
        elif request.filter_filename:
            effective_filter = request.filter_filename

        logger.info(f"RAG 对话: question='{clean_question[:50]}...' filter='{effective_filter}' mention='{mention_group}'")

        # 检索（多取一些供 Python 后置过滤）
        retrieve_k = request.top_k * 3 if effective_filter else request.top_k
        where = {"category": request.filter_category} if request.filter_category else None
        hits = rag_chain._retrieve(
            question=clean_question,
            top_k=retrieve_k,
            where=where
        )

        # Python 后置过滤
        if effective_filter:
            hits = [h for h in hits if effective_filter in h.metadata.get('filename', '')]
            hits = hits[:request.top_k]

        if not hits:
            return KBChatResponse(
                answer="抱歉，知识库中没有找到与您问题相关的内容。",
                sources=[]
            )

        # 生成回答
        answer = rag_chain._generate(
            question=clean_question,
            hits=hits,
            model_id=request.model_id
        )

        # 构建 sources（按文件名去重）
        sources = _build_source_list(hits)

        return KBChatResponse(answer=answer, sources=sources)

    except Exception as e:
        logger.error(f"RAG 对话失败: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"RAG 对话失败: {str(e)}")


# ==================== 统计 ====================

@router.get("/stats", response_model=KBStatsResponse)
async def kb_stats():
    """获取知识库统计信息"""
    if not is_initialized():
        raise HTTPException(status_code=500, detail="知识库未初始化")

    try:
        vectorstore = get_vectorstore()
        stats = vectorstore.get_stats()
        return KBStatsResponse(
            total_chunks=stats.get("total_chunks", 0),
            total_messages=stats.get("total_messages", 0),
            total_docs=stats.get("total_docs", 0),
            categories=stats.get("categories", [])
        )
    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取统计失败: {str(e)}")
