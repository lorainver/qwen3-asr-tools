"""
knowledge_store.py - 知识库核心模块

支持：文档加载 → 分块 → Embedding → 向量存储 → RAG 检索

依赖：
    pip install chromadb pymupdf python-docx beautifulsoup4 lxml

Embedding 模型（通过 Ollama）：
    ollama pull nomic-embed-text
"""

import os
import uuid
import logging
import hashlib
import json
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)

# ========== 配置 ==========
KB_ROOT = Path("D:/qwen3-asr/knowledge_base")
KB_ROOT.mkdir(exist_ok=True)
CHROMA_PATH = KB_ROOT / "chroma_db"
DOCS_PATH = KB_ROOT / "documents"
INDEX_FILE = KB_ROOT / "index.json"


# ========== 数据结构 ==========

@dataclass
class Document:
    """文档数据结构"""
    doc_id: str
    filename: str
    content: str
    metadata: Dict = field(default_factory=dict)
    chunk_count: int = 0


@dataclass
class Chunk:
    """文本块数据结构"""
    chunk_id: str
    doc_id: str
    text: str
    chunk_index: int
    metadata: Dict = field(default_factory=dict)


@dataclass
class SearchHit:
    """检索结果"""
    chunk_id: str
    text: str
    metadata: Dict
    distance: float
    score: float


# ========== 1. 文档加载器 ==========

class DocumentLoader:
    """支持多格式的文档加载器"""

    SUPPORTED_EXTENSIONS = {'.txt', '.md', '.pdf', '.docx', '.html', '.pptx', '.xlsx'}

    def load(self, file_path: str) -> Document:
        """加载文档"""
        ext = Path(file_path).suffix.lower()

        if ext == '.txt' or ext == '.md':
            return self._load_text(file_path)
        elif ext == '.pdf':
            return self._load_pdf(file_path)
        elif ext == '.docx':
            return self._load_docx(file_path)
        elif ext == '.html':
            return self._load_html(file_path)
        else:
            raise ValueError(f"不支持的文档格式: {ext}")

    def _load_text(self, path: str) -> Document:
        """加载纯文本/Markdown"""
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        return self._make_doc(path, content)

    def _load_pdf(self, path: str) -> Document:
        """加载 PDF（使用 PyMuPDF）"""
        import fitz  # pymupdf
        text_parts = []
        with fitz.open(path) as doc:
            for page in doc:
                page_text = page.get_text()
                if page_text.strip():
                    text_parts.append(f"[第{page.number + 1}页]\n{page_text}")
        content = "\n\n".join(text_parts)
        return self._make_doc(path, content)

    def _load_docx(self, path: str) -> Document:
        """加载 Word 文档"""
        from docx import Document as DocxDocument
        doc = DocxDocument(path)
        paragraphs = []
        for para in doc.paragraphs:
            text = para.text.strip()
            if text:
                paragraphs.append(text)
        content = "\n\n".join(paragraphs)
        return self._make_doc(path, content)

    def _load_html(self, path: str) -> Document:
        """加载 HTML（提取正文）"""
        from bs4 import BeautifulSoup
        with open(path, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f.read(), 'html.parser')
        # 移除脚本和样式
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            tag.decompose()
        # 获取文本
        content = soup.get_text(separator="\n\n", strip=True)
        # 清理多余空行
        content = re.sub(r'\n{3,}', '\n\n', content)
        return self._make_doc(path, content)

    def _make_doc(self, path: str, content: str) -> Document:
        """构建 Document 对象"""
        p = Path(path)
        # 生成唯一 ID
        doc_id = hashlib.md5(f"{p}{p.stat().st_size}".encode()).hexdigest()[:12]
        return Document(
            doc_id=doc_id,
            filename=p.name,
            content=content,
            metadata={
                "source": str(p.absolute()),
                "filename": p.name,
                "extension": p.suffix,
                "size_bytes": p.stat().st_size,
                "loaded_at": datetime.now().isoformat()
            }
        )


# ========== 2. 文本分块器 ==========

class TextChunker:
    """
    智能文本分块器

    策略：
    1. 优先按段落分块（保持语义完整）
    2. 单段落过长时按句子分块
    3. 相邻块之间有重叠（overlap），保证检索连续性
    """

    def __init__(self, chunk_size: int = 500, overlap: int = 50):
        """
        Args:
            chunk_size: 每块最大字符数
            overlap: 相邻块之间的重叠字符数
        """
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, doc: Document) -> List[Chunk]:
        """将文档分块"""
        chunks = []
        content = doc.content

        # 1. 先按段落分割
        paragraphs = re.split(r'\n\s*\n', content)
        paragraphs = [p.strip() for p in paragraphs if p.strip()]

        current_block = ""
        chunk_index = 0

        for para in paragraphs:
            # 如果单个段落就超过 chunk_size，按句子分割
            if len(para) > self.chunk_size:
                # 先保存当前块
                if current_block:
                    chunks.append(self._make_chunk(doc, current_block, chunk_index))
                    chunk_index += 1
                    current_block = ""

                # 处理超长段落：按句子分割
                sentences = self._split_sentences(para)
                for sent in sentences:
                    if len(current_block) + len(sent) + 1 <= self.chunk_size:
                        current_block = (current_block + "\n" + sent).strip()
                    else:
                        if current_block:
                            chunks.append(self._make_chunk(doc, current_block, chunk_index))
                            chunk_index += 1
                            # overlap：保留上一个块的最后 overlap 字符作为开头
                            current_block = current_block[-self.overlap:] + "\n" + sent if len(current_block) > self.overlap else sent
                        else:
                            current_block = sent
            else:
                # 普通段落：尝试加入当前块
                if len(current_block) + len(para) + 2 <= self.chunk_size:
                    current_block = (current_block + "\n\n" + para).strip()
                else:
                    # 当前块已满，保存并开始新块（带 overlap）
                    if current_block:
                        chunks.append(self._make_chunk(doc, current_block, chunk_index))
                        chunk_index += 1
                        # 应用 overlap
                        current_block = current_block[-self.overlap:] + "\n\n" + para if len(current_block) > self.overlap else para
                    else:
                        current_block = para

        # 保存最后一块
        if current_block.strip():
            chunks.append(self._make_chunk(doc, current_block, chunk_index))

        return chunks

    def _split_sentences(self, text: str) -> List[str]:
        """按句子分割（支持中英文）"""
        # 中文句号/问号/感叹号，英文 .?!（排除缩写）
        sentences = re.split(r'(?<=[。！？.?!])\s*', text)
        return [s.strip() for s in sentences if s.strip()]

    def _make_chunk(self, doc: Document, text: str, idx: int) -> Chunk:
        """构建 Chunk 对象"""
        return Chunk(
            chunk_id=f"{doc.doc_id}_c{idx}",
            doc_id=doc.doc_id,
            text=text,
            chunk_index=idx,
            metadata={
                **doc.metadata,
                "chunk_index": idx,
                "char_count": len(text)
            }
        )


# ========== 3. Embedding 模型封装 ==========

class Embedder:
    """
    Embedding 模型封装

    支持：
    1. Ollama 本地模型（nomic-embed-text）- 首选
    2. HuggingFace 本地模型（text2vec-base-chinese 等）- 备选
    """

    def __init__(self, provider: str = "ollama", model: str = "nomic-embed-text"):
        self.provider = provider
        self.model = model
        self._session = None
        self._hf_model = None
        self._base_url = "http://127.0.0.1:11434"

    def _get_session(self):
        """获取 HTTP Session"""
        if self._session is None:
            import requests
            self._session = requests.Session()
        return self._session

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """将多个文本向量化"""
        if self.provider == "ollama":
            return self._embed_ollama_batch(texts)
        elif self.provider == "huggingface":
            return self._embed_huggingface(texts)
        else:
            raise ValueError(f"不支持的 provider: {self.provider}")

    def _embed_ollama_batch(self, texts: List[str]) -> List[List[float]]:
        """通过 Ollama API 批量获取 embeddings"""
        session = self._get_session()
        embeddings = []

        for text in texts:
            try:
                response = session.post(
                    f"{self._base_url}/api/embeddings",
                    json={"model": self.model, "prompt": text},
                    timeout=60,
                    proxies={'http': None, 'https': None}
                )
                if response.status_code != 200:
                    logger.error(f"Ollama embedding 失败: {response.status_code} - {response.text}")
                    # 返回零向量作为降级
                    embeddings.append([0.0] * 768)
                    continue
                data = response.json()
                embedding = data.get('embedding', [])
                if not embedding:
                    embeddings.append([0.0] * 768)
                else:
                    embeddings.append(embedding)
            except Exception as e:
                logger.error(f"Ollama embedding 请求异常: {e}")
                embeddings.append([0.0] * 768)

        return embeddings

    def _embed_huggingface(self, texts: List[str]) -> List[List[float]]:
        """使用 HuggingFace 本地模型"""
        if self._hf_model is None:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info("正在加载 HuggingFace Embedding 模型...")
                self._hf_model = SentenceTransformer('shenglOL/text2vec-base-chinese')
            except ImportError:
                raise ImportError("请先安装 sentence-transformers: pip install sentence-transformers")

        embeddings = self._hf_model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()

    def embed_query(self, query: str) -> List[float]:
        """向量化单个查询"""
        return self.embed_texts([query])[0]


# ========== 4. ChromaDB 向量存储 ==========

class VectorStore:
    """ChromaDB 向量存储封装"""

    def __init__(self, collection_name: str = "knowledge_base"):
        import chromadb
        from chromadb.config import Settings

        # 确保路径存在
        CHROMA_PATH.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=str(CHROMA_PATH),
            settings=Settings(anonymized_telemetry=False)
        )
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "qwen3-asr 知识库"}
        )
        logger.info(f"✅ ChromaDB 初始化完成，Collection: {collection_name}, 当前块数: {self.collection.count()}")

    def add_chunks(self, chunks: List[Chunk], embeddings: List[List[float]]):
        """批量添加文本块"""
        if not chunks:
            return

        ids = [c.chunk_id for c in chunks]
        texts = [c.text for c in chunks]
        metadatas = [c.metadata for c in chunks]

        # 批量添加，每批 100 个
        batch_size = 100
        for i in range(0, len(chunks), batch_size):
            batch_ids = ids[i:i + batch_size]
            batch_texts = texts[i:i + batch_size]
            batch_metas = metadatas[i:i + batch_size]
            batch_embs = embeddings[i:i + batch_size]

            self.collection.add(
                ids=batch_ids,
                embeddings=batch_embs,
                documents=batch_texts,
                metadatas=batch_metas
            )

        logger.info(f"📦 已添加 {len(chunks)} 个文本块到向量库")

    def search(self, query_embedding: List[float], top_k: int = 5,
               where: Optional[Dict] = None) -> List[SearchHit]:
        """
        语义检索

        Args:
            query_embedding: 查询向量
            top_k: 返回前 N 条
            where: 元数据过滤条件

        Returns:
            检索结果列表
        """
        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where,
                include=["documents", "metadatas", "distances"]
            )

            hits = []
            if results and results['ids'] and len(results['ids']) > 0:
                for i in range(len(results['ids'][0])):
                    dist = results['distances'][0][i]
                    hits.append(SearchHit(
                        chunk_id=results['ids'][0][i],
                        text=results['documents'][0][i],
                        metadata=results['metadatas'][0][i],
                        distance=dist,
                        score=max(0.0, 1.0 - dist)  # 余弦距离转相似度
                    ))

            return hits

        except Exception as e:
            logger.error(f"向量检索失败: {e}")
            return []

    def delete_by_doc_id(self, doc_id: str):
        """删除某个文档的所有块"""
        try:
            results = self.collection.get(where={"doc_id": doc_id})
            if results and results['ids']:
                self.collection.delete(ids=results['ids'])
                logger.info(f"🗑️ 已删除文档 {doc_id} 的 {len(results['ids'])} 个块")
        except Exception as e:
            logger.error(f"删除文档块失败: {e}")

    def count(self) -> int:
        """向量库中的总块数"""
        return self.collection.count()

    def get_all_docs(self) -> List[Dict]:
        """获取所有文档的元数据"""
        try:
            results = self.collection.get(include=["metadatas"])
            if not results or not results['metadatas']:
                return []

            # 按 doc_id 分组
            docs_map = {}
            for meta in results['metadatas']:
                doc_id = meta.get('doc_id', '')
                if doc_id and doc_id not in docs_map:
                    docs_map[doc_id] = {
                        "doc_id": doc_id,
                        "filename": meta.get('filename', ''),
                        "source": meta.get('source', ''),
                        "category": meta.get('category', '默认'),
                        "loaded_at": meta.get('loaded_at', ''),
                        "chunk_count": 0
                    }
                if doc_id:
                    docs_map[doc_id]['chunk_count'] += 1

            return list(docs_map.values())
        except Exception as e:
            logger.error(f"获取文档列表失败: {e}")
            return []

    def clear_all(self):
        """清空所有数据（谨慎使用）"""
        try:
            self.client.delete_collection(name=self.collection.name)
            self.collection = self.client.get_or_create_collection(
                name=self.collection.name,
                metadata={"description": "qwen3-asr 知识库"}
            )
            logger.info("🗑️ 已清空知识库")
        except Exception as e:
            logger.error(f"清空知识库失败: {e}")


# ========== 5. RAG 检索链 ==========

class RAGChain:
    """
    RAG (Retrieval Augmented Generation) 检索链

    流程：
    1. 接收用户问题
    2. 向量化问题（Embedding）
    3. 从向量库检索相关块（top_k）
    4. 将检索结果注入提示词
    5. 调用 LLM 生成回答
    """

    def __init__(self, embedder: Embedder, vectorstore: VectorStore, summarizer: Any):
        self.embedder = embedder
        self.vectorstore = vectorstore
        self.summarizer = summarizer  # LongTextSummarizer 实例

    def query(self, question: str, top_k: int = 5,
              filter_category: Optional[str] = None) -> Tuple[str, List[SearchHit]]:
        """
        执行 RAG 查询

        Returns:
            (回答文本, 检索到的相关片段列表)
        """
        # 1. 向量化问题
        try:
            query_embedding = self.embedder.embed_query(question)
        except Exception as e:
            logger.error(f"问题向量化失败: {e}")
            return f"抱歉，检索过程中出现错误：{str(e)}", []

        # 2. 语义检索
        where = None
        if filter_category:
            where = {"category": filter_category}

        hits = self.vectorstore.search(
            query_embedding=query_embedding,
            top_k=top_k,
            where=where
        )

        if not hits:
            return "抱歉，知识库中没有找到与您问题相关的内容。", []

        # 3. 构建提示词并调用 LLM
        context = self._build_context(hits)
        prompt = self._build_prompt(question, context)

        system_prompt = """你是一个知识库问答助手。你的任务是根据提供的参考资料回答用户的问题。

规则：
1. 必须严格按照提供的参考资料回答，不要编造信息
2. 如果参考资料中有相关内容，引用时注明来源（文件名）
3. 如果参考资料中没有相关信息，明确告知用户
4. 回答要准确、完整、简洁
5. 优先使用参考资料中的原文表述，必要时进行总结"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]

        try:
            answer = self.summarizer.chat(messages, max_new_tokens=2048)
        except Exception as e:
            logger.error(f"LLM 生成失败: {e}")
            answer = f"抱歉，生成回答时出现错误：{str(e)}"

        return answer, hits

    def _build_context(self, hits: List[SearchHit]) -> str:
        """将检索结果构建为上下文"""
        context_parts = []
        for i, hit in enumerate(hits, 1):
            filename = hit.metadata.get('filename', '未知来源')
            source = hit.metadata.get('source', '')
            context_parts.append(
                f"【参考资料 {i}】（来源：{filename}）\n{hit.text}"
            )
        return "\n\n---\n\n".join(context_parts)

    def _build_prompt(self, question: str, context: str) -> str:
        """构建用户提示词"""
        return f"""【用户问题】
{question}

【参考资料】
以下是从知识库中检索到的相关资料，请仔细阅读后回答：

{context}

请根据以上参考资料回答用户问题。如果资料中有明确答案，给出准确回答并注明参考来源。"""


# ========== 6. 全局单例与管理 ==========

# 全局实例
_loader: Optional[DocumentLoader] = None
_chunker: Optional[TextChunker] = None
_embedder: Optional[Embedder] = None
_vectorstore: Optional[VectorStore] = None
_rag_chain: Optional[RAGChain] = None
_summarizer_ref: Any = None


def init_knowledge_base(summarizer: Any,
                        chunk_size: int = 500,
                        overlap: int = 50,
                        embed_provider: str = "ollama",
                        embed_model: str = "nomic-embed-text") -> bool:
    """
    初始化知识库模块

    Args:
        summarizer: LongTextSummarizer 实例
        chunk_size: 分块大小（字符数）
        overlap: 重叠字符数
        embed_provider: Embedding 提供者 ("ollama" 或 "huggingface")
        embed_model: Embedding 模型名称

    Returns:
        是否初始化成功
    """
    global _loader, _chunker, _embedder, _vectorstore, _rag_chain, _summarizer_ref, _last_init_error

    try:
        logger.info("🔧 正在初始化知识库模块...")
        logger.info(f"   - 分块大小: {chunk_size} 字符, 重叠: {overlap} 字符")
        logger.info(f"   - Embedding: {embed_provider} / {embed_model}")

        _summarizer_ref = summarizer
        _loader = DocumentLoader()
        _chunker = TextChunker(chunk_size=chunk_size, overlap=overlap)
        _embedder = Embedder(provider=embed_provider, model=embed_model)
        _vectorstore = VectorStore(collection_name="knowledge_base")
        _rag_chain = RAGChain(_embedder, _vectorstore, summarizer)

        logger.info("✅ 知识库模块初始化完成")
        return True

    except Exception as e:
        logger.error(f"❌ 知识库初始化失败: {e}")
        # 记录详细堆栈到 stderr，方便排查
        import traceback
        traceback.print_exc()
        # 把错误存到全局变量，让 API 层可以读取
        global _last_init_error
        _last_init_error = str(e)
        return False


def get_last_init_error() -> str:
    """获取最后一次初始化失败的具体错误"""
    global _last_init_error
    return _last_init_error or "未知错误"


def get_loader() -> DocumentLoader:
    if _loader is None:
        raise RuntimeError("知识库未初始化，请先调用 init_knowledge_base()")
    return _loader


def get_chunker() -> TextChunker:
    if _chunker is None:
        raise RuntimeError("知识库未初始化，请先调用 init_knowledge_base()")
    return _chunker


def get_embedder() -> Embedder:
    if _embedder is None:
        raise RuntimeError("知识库未初始化，请先调用 init_knowledge_base()")
    return _embedder


def get_vectorstore() -> VectorStore:
    if _vectorstore is None:
        raise RuntimeError("知识库未初始化，请先调用 init_knowledge_base()")
    return _vectorstore


def get_rag_chain() -> RAGChain:
    if _rag_chain is None:
        raise RuntimeError("知识库未初始化，请先调用 init_knowledge_base()")
    return _rag_chain


def is_initialized() -> bool:
    """检查知识库是否已初始化"""
    return _rag_chain is not None


# ========== 辅助函数 ==========

def index_document(file_path: str, category: str = "默认") -> Dict:
    """
    一键索引文档（加载 → 分块 → 向量化 → 存储）

    Args:
        file_path: 文档路径
        category: 分类标签

    Returns:
        索引结果信息
    """
    loader = get_loader()
    chunker = get_chunker()
    embedder = get_embedder()
    vectorstore = get_vectorstore()

    # 1. 加载文档
    doc = loader.load(file_path)
    doc.metadata['category'] = category

    # 保存原始文件到知识库目录
    dest_dir = DOCS_PATH / category.replace("/", "_")
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / doc.filename

    # 复制文件
    import shutil
    shutil.copy2(file_path, dest_path)
    doc.metadata['stored_path'] = str(dest_path)

    # 2. 分块
    chunks = chunker.chunk(doc)
    doc.chunk_count = len(chunks)
    logger.info(f"📄 文档 '{doc.filename}' 已分块: {len(chunks)} 个块")

    # 3. 向量化
    texts = [c.text for c in chunks]
    embeddings = embedder.embed_texts(texts)

    # 4. 存入向量库
    vectorstore.add_chunks(chunks, embeddings)

    # 5. 更新索引文件
    _update_index_file(doc)

    return {
        "doc_id": doc.doc_id,
        "filename": doc.filename,
        "chunk_count": len(chunks),
        "category": category
    }


def _update_index_file(doc: Document):
    """更新文档索引文件"""
    index_file = KB_ROOT / "index.json"
    index = {}

    if index_file.exists():
        try:
            index = json.loads(index_file.read_text(encoding='utf-8'))
        except Exception:
            index = {}

    index[doc.doc_id] = {
        "filename": doc.filename,
        "metadata": doc.metadata,
        "chunk_count": doc.chunk_count,
        "indexed_at": doc.metadata.get('loaded_at', '')
    }

    index_file.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding='utf-8')
    logger.info(f"📋 索引文件已更新: {index_file}")
