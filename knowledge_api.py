"""
knowledge_api.py - 知识库 API（挂载到 ai_worker.py）

API 端点：
    POST /api/kb/upload          - 上传并索引文档
    POST /api/kb/index           - 从目录批量索引
    GET  /api/kb/search          - 语义搜索
    POST /api/kb/chat            - RAG 对话
    GET  /api/kb/docs            - 列出文档
    DELETE /api/kb/doc/{doc_id}  - 删除文档
    GET  /api/kb/stats            - 统计信息
    DELETE /api/kb/clear         - 清空知识库
"""

import os
import sys
import shutil
import logging
import tempfile
from pathlib import Path
from typing import Optional, List
from fastapi import APIRouter, UploadFile, File, Query, HTTPException, Form
from pydantic import BaseModel

# 添加项目根目录到 path
BASE_DIR = Path(__file__).parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from knowledge_store import (
    init_knowledge_base,
    index_document,
    get_loader,
    get_vectorstore,
    get_embedder,
    get_rag_chain,
    is_initialized,
    KB_ROOT,
    DOCS_PATH
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/kb", tags=["knowledge_base"])

# ========== 数据模型 ==========

class KBSearchRequest(BaseModel):
    query: str
    top_k: int = 5
    filter_category: Optional[str] = None


class KBChatRequest(BaseModel):
    question: str
    top_k: int = 5
    filter_category: Optional[str] = None
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
    total_docs: int
    categories: List[str]


class KBDocResponse(BaseModel):
    docs: List[dict]
    count: int


class KBSourceItem(BaseModel):
    filename: str
    text: str
    score: float


# ========== API 端点 ==========

@router.post("/init")
async def init_kb(
    chunk_size: int = Query(default=500, ge=100, le=2000, description="分块大小（字符数）"),
    overlap: int = Query(default=50, ge=0, le=500, description="重叠字符数"),
    embed_provider: str = Query(default="ollama", description="Embedding 提供者 (ollama/huggingface)"),
    embed_model: str = Query(default="nomic-embed-text", description="Embedding 模型名称")
):
    """初始化知识库模块"""
    from summarizer import LongTextSummarizer

    summarizer = LongTextSummarizer()

    success = init_knowledge_base(
        summarizer=summarizer,
        chunk_size=chunk_size,
        overlap=overlap,
        embed_provider=embed_provider,
        embed_model=embed_model
    )

    if success:
        vs = get_vectorstore()
        return {
            "status": "ok",
            "message": "知识库初始化成功",
            "stats": {
                "total_chunks": vs.count(),
                "total_docs": len(vs.get_all_docs())
            }
        }
    else:
        raise HTTPException(status_code=500, detail="知识库初始化失败")


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    category: str = Form(default="默认", description="文档分类")
):
    """上传并索引文档"""
    if not is_initialized():
        raise HTTPException(status_code=500, detail="知识库未初始化，请先调用 /api/kb/init")

    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名为空")

    # 检查格式
    ext = Path(file.filename).suffix.lower()
    supported = get_loader().SUPPORTED_EXTENSIONS
    if ext not in supported:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的格式: {ext}，支持的格式: {', '.join(supported)}"
        )

    # 保存到临时文件
    suffix = ext
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # 索引文档
        result = index_document(tmp_path, category=category)

        return {
            "status": "ok",
            "message": f"文档 '{file.filename}' 索引成功",
            "doc_id": result["doc_id"],
            "filename": result["filename"],
            "chunk_count": result["chunk_count"],
            "category": category
        }
    except Exception as e:
        logger.error(f"文档索引失败: {e}")
        raise HTTPException(status_code=500, detail=f"索引失败: {str(e)}")
    finally:
        # 删除临时文件
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


@router.post("/index")
async def index_directory(
    directory: str = Query(..., description="目录路径"),
    category: str = Query(default="默认", description="分类标签"),
    recursive: bool = Query(default=True, description="是否递归扫描子目录")
):
    """从目录批量索引文档"""
    if not is_initialized():
        raise HTTPException(status_code=500, detail="知识库未初始化，请先调用 /api/kb/init")

    dir_path = Path(directory)
    if not dir_path.exists():
        raise HTTPException(status_code=400, detail=f"目录不存在: {directory}")

    if not dir_path.is_dir():
        raise HTTPException(status_code=400, detail=f"不是有效目录: {directory}")

    loader = get_loader()
    supported = loader.SUPPORTED_EXTENSIONS

    # 收集文件
    files = []
    pattern = "**/*" if recursive else "*"
    for f in dir_path.glob(pattern):
        if f.is_file() and f.suffix.lower() in supported:
            files.append(f)

    if not files:
        return {
            "status": "ok",
            "message": "未找到可索引的文档",
            "indexed": 0
        }

    # 批量索引
    results = []
    errors = []

    for f in files:
        try:
            result = index_document(str(f), category=category)
            results.append(result)
        except Exception as e:
            errors.append({"file": str(f), "error": str(e)})
            logger.error(f"索引失败 {f}: {e}")

    return {
        "status": "ok",
        "message": f"批量索引完成",
        "total_files": len(files),
        "indexed": len(results),
        "failed": len(errors),
        "results": results,
        "errors": errors
    }


@router.get("/search")
async def search_knowledge(
    q: str = Query(..., description="搜索查询", min_length=1),
    top_k: int = Query(default=5, ge=1, le=20),
    category: Optional[str] = Query(default=None)
):
    """语义搜索知识库"""
    if not is_initialized():
        raise HTTPException(status_code=500, detail="知识库未初始化，请先调用 /api/kb/init")

    try:
        embedder = get_embedder()
        vectorstore = get_vectorstore()

        # 向量化查询
        query_embedding = embedder.embed_query(q)

        # 检索
        where = {"category": category} if category else None
        hits = vectorstore.search(
            query_embedding=query_embedding,
            top_k=top_k,
            where=where
        )

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


@router.post("/chat", response_model=KBChatResponse)
async def rag_chat(request: KBChatRequest):
    """RAG 对话：检索 + 生成"""
    if not is_initialized():
        raise HTTPException(status_code=500, detail="知识库未初始化，请先调用 /api/kb/init")

    try:
        rag_chain = get_rag_chain()
        answer, hits = rag_chain.query(
            question=request.question,
            top_k=request.top_k,
            filter_category=request.filter_category
        )

        sources = []
        for hit in hits:
            text_preview = hit.text[:200] + "..." if len(hit.text) > 200 else hit.text
            sources.append({
                "filename": hit.metadata.get('filename', ''),
                "category": hit.metadata.get('category', ''),
                "text": text_preview,
                "score": round(hit.score, 4)
            })

        return KBChatResponse(
            answer=answer,
            sources=sources
        )

    except Exception as e:
        logger.error(f"RAG 对话失败: {e}")
        raise HTTPException(status_code=500, detail=f"对话失败: {str(e)}")


@router.get("/docs", response_model=KBDocResponse)
async def list_docs():
    """列出所有已索引的文档"""
    if not is_initialized():
        raise HTTPException(status_code=500, detail="知识库未初始化，请先调用 /api/kb/init")

    try:
        vectorstore = get_vectorstore()
        docs = vectorstore.get_all_docs()
        return KBDocResponse(docs=docs, count=len(docs))
    except Exception as e:
        logger.error(f"获取文档列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/doc/{doc_id}")
async def delete_document(doc_id: str):
    """删除文档（从向量库中移除）"""
    if not is_initialized():
        raise HTTPException(status_code=500, detail="知识库未初始化，请先调用 /api/kb/init")

    try:
        vectorstore = get_vectorstore()
        vectorstore.delete_by_doc_id(doc_id)

        # 同时从原始文件目录删除（如果存在）
        docs = vectorstore.get_all_docs()
        # 重新检查是否真的删除了

        return {
            "status": "ok",
            "message": f"文档 {doc_id} 已删除",
            "doc_id": doc_id
        }
    except Exception as e:
        logger.error(f"删除文档失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=KBStatsResponse)
async def get_stats():
    """获取知识库统计信息"""
    if not is_initialized():
        # 返回默认状态
        return KBStatsResponse(
            total_chunks=0,
            total_docs=0,
            categories=[]
        )

    try:
        vectorstore = get_vectorstore()
        docs = vectorstore.get_all_docs()

        # 统计分类
        categories = list(set(d.get('category', '默认') for d in docs))

        return KBStatsResponse(
            total_chunks=vectorstore.count(),
            total_docs=len(docs),
            categories=categories
        )
    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/clear")
async def clear_knowledge_base():
    """清空知识库（危险操作）"""
    if not is_initialized():
        raise HTTPException(status_code=500, detail="知识库未初始化，请先调用 /api/kb/init")

    try:
        vectorstore = get_vectorstore()
        chunk_count = vectorstore.count()
        vectorstore.clear_all()

        return {
            "status": "ok",
            "message": f"已清空知识库，删除了 {chunk_count} 个文本块"
        }
    except Exception as e:
        logger.error(f"清空知识库失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_status():
    """获取知识库状态"""
    initialized = is_initialized()
    stats = {"total_chunks": 0, "total_docs": 0, "categories": []}

    if initialized:
        try:
            vectorstore = get_vectorstore()
            docs = vectorstore.get_all_docs()
            stats = {
                "total_chunks": vectorstore.count(),
                "total_docs": len(docs),
                "categories": list(set(d.get('category', '默认') for d in docs))
            }
        except Exception:
            pass

    return {
        "initialized": initialized,
        "stats": stats
    }
