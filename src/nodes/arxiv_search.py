"""arxiv论文搜索节点"""

import arxiv
from typing import Dict, Any
from .base import BaseNode

class ArxivSearchNode(BaseNode):
    """Arxiv论文搜索节点"""
    
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行论文搜索
        
        Args:
            params: 包含搜索关键词的参数字典
            
        Returns:
            Dict[str, Any]: 搜索结果，包含前5篇最相关论文的信息
        """
        query = params.get("query")
        if not query:
            return {
                "success": False,
                "error": "Missing required parameter: query",
                "results": []
            }
            
        try:
            # 创建搜索客户端
            client = arxiv.Client()
            
            # 构建搜索查询
            search = arxiv.Search(
                query=query,
                max_results=5,
                sort_by=arxiv.SortCriterion.Relevance
            )
            
            # 执行搜索
            results = []
            for paper in client.results(search):
                results.append({ 
                    "title": paper.title,
                    "authors": [author.name for author in paper.authors],
                    "summary": paper.summary,
                    "published": paper.published.strftime("%Y-%m-%d"),
                    "pdf_url": paper.pdf_url,
                    "entry_id": paper.entry_id,
                    "primary_category": paper.primary_category
                })
             
            return {
                "success": True,
                "results": results,
                "count": len(results)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "results": []
            }
