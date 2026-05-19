"""
联网搜索模块 - 支持 Serper.dev (Google) 和 DuckDuckGo 双引擎自动降级
"""
import requests
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class SearchResult:
    """搜索结果数据结构"""
    title: str
    snippet: str
    url: str
    source: str  # "serper" 或 "duckduckgo"


class WebSearcher:
    """联网搜索器 - 自动降级双引擎"""
    
    def __init__(self, serper_api_key: Optional[str] = None, searxng_url: Optional[str] = None):
        self.serper_api_key = serper_api_key
        self.searxng_url = searxng_url
        self.serper_quota_exceeded = False  # 标记 Serper 配额是否用完
        self.serper_url = "https://google.serper.dev/search"
        
    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """
        执行搜索 - 优先使用私有 SearXNG，其次 Serper，最后降级到 DuckDuckGo。
        并在获取到候选结果后，使用轻量级本地 CPU Reranker 进行重排，保留关联度最高的前 N 条结果。
        """
        # 为了给重排器提供更丰富的候选池，在拉取阶段调大召回数量（例如拉取 max_results * 2 条）
        candidate_limit = max(8, max_results * 2)
        results = []

        # 1. 优先使用私有 SearXNG 节点
        if self.searxng_url:
            try:
                results = self._search_searxng(query, candidate_limit)
                if results:
                    logger.info(f"🌐 [SearXNG] 召回成功: '{query}' → {len(results)} 条候选结果")
            except Exception as e:
                logger.warning(f"⚠️ SearXNG 搜索失败: {e}，尝试备用引擎")

        # 2. 如果 SearXNG 失败或没有结果，尝试 Serper
        if not results and self.serper_api_key and not self.serper_quota_exceeded:
            try:
                results = self._search_serper(query, candidate_limit)
                if results:
                    logger.info(f"🌐 [Serper] 召回成功: '{query}' → {len(results)} 条候选结果")
            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg or "quota" in error_msg.lower():
                    logger.warning("⚠️ Serper 配额已用完，自动切换到 DuckDuckGo")
                    self.serper_quota_exceeded = True
                else:
                    logger.warning(f"⚠️ Serper 搜索失败: {e}，尝试 DuckDuckGo")
        
        # 3. 最后降级到 DuckDuckGo
        if not results:
            try:
                results = self._search_duckduckgo(query, candidate_limit)
                if results:
                    logger.info(f"🌐 [DuckDuckGo] 召回成功: '{query}' → {len(results)} 条候选结果")
            except Exception as e:
                logger.error(f"❌ 所有搜索引擎均失败: {e}")

        # 4. 如果没有候选结果，直接返回空
        if not results:
            return []

        # 5. 核心：在 CPU 上对召回的结果进行轻量级 BM25 重排
        reranked_results = self.rerank(query, results, top_k=max_results)
        return reranked_results

    def rerank(self, query: str, results: List[SearchResult], top_k: int = 3) -> List[SearchResult]:
        """
        使用轻量级纯 Python BM25 文本相关度算法对搜索结果进行智能重排。
        100% 运行在 CPU 上，不需要加载任何深度学习大模型，0 显存成本，延迟 < 1ms。
        """
        if not results or not query:
            return results

        import re
        import math

        # 1. 对查询词进行轻量级分词（支持中英文）
        def tokenize(text: str) -> List[str]:
            text = text.lower()
            # 匹配中文字符、英文字母和数字
            words = re.findall(r'[\u4e00-\u9fff]|[a-zA-Z0-9]+', text)
            return [w for w in words if w.strip()]

        query_tokens = tokenize(query)
        if not query_tokens:
            return results[:top_k]

        # 2. 构建文档库（每个搜索结果的 title + snippet 作为一篇文档）
        documents = []
        for r in results:
            doc_text = f"{r.title} {r.snippet}"
            doc_tokens = tokenize(doc_text)
            documents.append((r, doc_tokens))

        # 3. 计算 TF-IDF/BM25 相似度打分
        N = len(documents)
        
        df = {}
        for _, doc_tokens in documents:
            unique_tokens = set(doc_tokens)
            for token in unique_tokens:
                df[token] = df.get(token, 0) + 1

        # idf 计算
        idf = {}
        for token, freq in df.items():
            idf[token] = math.log((N - freq + 0.5) / (freq + 0.5) + 1.0)

        # 4. 对每个文档打分
        # BM25 参数
        k1 = 1.5
        b = 0.75
        avg_dl = sum(len(doc_tokens) for _, doc_tokens in documents) / N if N > 0 else 1

        scored_results = []
        for r, doc_tokens in documents:
            score = 0.0
            doc_len = len(doc_tokens)
            tf = {}
            for token in doc_tokens:
                tf[token] = tf.get(token, 0) + 1

            for token in query_tokens:
                if token in tf:
                    tf_val = tf[token]
                    token_idf = idf.get(token, 0.5)
                    score += token_idf * ((tf_val * (k1 + 1)) / (tf_val + k1 * (1 - b + b * (doc_len / avg_dl))))
                
                # 标题匹配加成（标题匹配核心词给予 1.5 倍加成分数）
                if token in tokenize(r.title):
                    score += 1.5

            scored_results.append((r, score))

        # 5. 排序并返回前 top_k 个结果
        scored_results.sort(key=lambda x: x[1], reverse=True)
        
        # 记录重排日志
        logger.info(f"📊 [Reranker] 搜索重排完成. 候选 {N} 条 -> 保留 {min(top_k, N)} 条. 最优相似度评分: {scored_results[0][1]:.2f}")
        
        return [item[0] for item in scored_results[:top_k]]

    def _search_searxng(self, query: str, max_results: int) -> List[SearchResult]:
        """私有 SearXNG 节点搜索 - 深度加固版"""
        if not self.searxng_url:
            return []
            
        url = f"{self.searxng_url}/search"
        params = {
            "q": query,
            "format": "json",
            "engines": "google,bing,baidu,duckduckgo",
            "language": "zh-CN"
        }
        
        # 深度加固：使用独立 Session 并彻底禁用系统环境变量中的代理配置
        session = requests.Session()
        session.trust_env = False  # 关键：强制不读取系统代理环境变量
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        try:
            # 增加超时时间到 30 秒，显式传空代理
            response = session.get(url, params=params, timeout=30, headers=headers, proxies={"http": None, "https": None})
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            logger.error(f"❌ SearXNG 访问异常 (URL: {url}): {e}")
            raise e
        
        results = []
        # 解析 results 数组
        search_results = data.get("results", [])
        for item in search_results[:max_results]:
            results.append(SearchResult(
                title=item.get("title", ""),
                snippet=item.get("content", ""),
                url=item.get("url", ""),
                source=item.get("engine", "searxng")
            ))
        
        return results
    
    def _search_serper(self, query: str, max_results: int) -> List[SearchResult]:
        """Serper.dev API (Google 搜索)"""
        if not self.serper_api_key:
            raise ValueError("Serper API Key 未配置")
            
        headers = {
            "X-API-KEY": self.serper_api_key,
            "Content-Type": "application/json"
        }
        payload = {
            "q": query,
            "gl": "cn",  # 地区设置为中国
            "hl": "zh-cn"  # 语言设置为中文
        }
        
        response = requests.post(
            self.serper_url, 
            headers=headers, 
            json=payload,
            timeout=10
        )
        
        if response.status_code == 429:
            raise Exception("429 Quota Exceeded")
        
        response.raise_for_status()
        data = response.json()
        
        results = []
        # 解析 organic 结果（自然搜索结果）
        organic = data.get("organic", [])
        for item in organic[:max_results]:
            results.append(SearchResult(
                title=item.get("title", ""),
                snippet=item.get("snippet", ""),
                url=item.get("link", ""),
                source="serper"
            ))
        
        return results
    
    def _search_duckduckgo(self, query: str, max_results: int) -> List[SearchResult]:
        """
        DuckDuckGo 搜索 (通过 duckduckgo-search 库)
        需要安装: pip install duckduckgo-search
        """
        try:
            from ddgs import DDGS
        except ImportError:
            logger.error("请先安装 ddgs: pip install ddgs")
            return []
        
        results = []
        with DDGS() as ddgs:
            # 使用 text 搜索（不指定 region，默认全球搜索）
            search_gen = ddgs.text(
                query,
                max_results=max_results
            )
            
            if search_gen:
                for item in search_gen:
                    results.append(SearchResult(
                        title=item.get("title", ""),
                        snippet=item.get("body", ""),
                        url=item.get("href", ""),
                        source="duckduckgo"
                    ))
        
        return results
    
    def format_for_llm(self, results: List[SearchResult]) -> str:
        """
        将搜索结果格式化为 LLM 可理解的上下文文本
        
        Args:
            results: 搜索结果列表
            
        Returns:
            格式化的文本
        """
        if not results:
            return ""
        
        text = "【联网搜索结果】\n"
        text += "以下是从网上搜索到的相关信息，请参考这些内容回答问题：\n\n"
        
        for i, r in enumerate(results, 1):
            text += f"[{i}] {r.title}\n"
            text += f"    摘要: {r.snippet}\n"
            text += f"    来源: {r.url}\n\n"
        
        text += "请基于以上搜索结果，结合你的知识回答用户问题。如果搜索结果不相关，请如实告知。\n"
        
        return text


# 全局单例
_searcher: Optional[WebSearcher] = None

def get_searcher(serper_api_key: Optional[str] = None, searxng_url: Optional[str] = None) -> WebSearcher:
    """获取全局搜索器实例"""
    global _searcher
    if _searcher is None:
        _searcher = WebSearcher(serper_api_key, searxng_url)
    return _searcher

def reset_searcher():
    """重置搜索器（用于配置更新后）"""
    global _searcher
    _searcher = None
