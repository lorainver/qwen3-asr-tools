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
    
    def __init__(self, serper_api_key: Optional[str] = None):
        self.serper_api_key = serper_api_key
        self.serper_quota_exceeded = False  # 标记 Serper 配额是否用完
        self.serper_url = "https://google.serper.dev/search"
        
    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """
        执行搜索 - 优先 Serper，失败自动降级到 DuckDuckGo
        
        Args:
            query: 搜索关键词
            max_results: 最大返回结果数
            
        Returns:
            搜索结果列表
        """
        # 1. 如果 Serper 配额未用完，优先使用
        if self.serper_api_key and not self.serper_quota_exceeded:
            try:
                results = self._search_serper(query, max_results)
                if results:
                    logger.info(f"🌐 [Serper] 搜索成功: '{query}' → {len(results)} 条结果")
                    return results
            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg or "quota" in error_msg.lower():
                    logger.warning("⚠️ Serper 配额已用完，自动切换到 DuckDuckGo")
                    self.serper_quota_exceeded = True
                else:
                    logger.warning(f"⚠️ Serper 搜索失败: {e}，尝试 DuckDuckGo")
        
        # 2. 降级到 DuckDuckGo
        try:
            results = self._search_duckduckgo(query, max_results)
            if results:
                logger.info(f"🌐 [DuckDuckGo] 搜索成功: '{query}' → {len(results)} 条结果")
                return results
        except Exception as e:
            logger.error(f"❌ DuckDuckGo 搜索也失败: {e}")
            
        return []
    
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
            from duckduckgo_search import DDGS
        except ImportError:
            logger.error("请先安装 duckduckgo-search: pip install duckduckgo-search")
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

def get_searcher(serper_api_key: Optional[str] = None) -> WebSearcher:
    """获取全局搜索器实例"""
    global _searcher
    if _searcher is None:
        _searcher = WebSearcher(serper_api_key)
    return _searcher

def reset_searcher():
    """重置搜索器（用于配置更新后）"""
    global _searcher
    _searcher = None
