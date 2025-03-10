"""arxiv论文搜索节点"""

import arxiv
import requests
import tempfile
import os
import logging
from PyPDF2 import PdfReader
from typing import Dict, Any
from .base import BaseNode

logger = logging.getLogger()

class ArxivSearchNode(BaseNode):
    """Arxiv论文搜索节点"""
    
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行论文搜索
        
        Args:
            params: 包含搜索关键词的参数字典
            
        Returns:
            Dict[str, Any]: 搜索结果，包含前5篇最相关论文的信息
，包括PDF全文内容
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
                paper_info = { 
                    "title": paper.title,
                    "authors": [author.name for author in paper.authors],
                    "summary": paper.summary,
                    "published": paper.published.strftime("%Y-%m-%d"),
                    "pdf_url": paper.pdf_url,
                    "entry_id": paper.entry_id,
                    "primary_category": paper.primary_category
,
                    "content": ""
                }
                
                # 下载并提取PDF内容
                try:
                    # 下载PDF文件
                    pdf_response = requests.get(paper.pdf_url, timeout=30)
                    if pdf_response.status_code == 200:
                        # 创建临时文件保存PDF
                        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
                            temp_file.write(pdf_response.content)
                            temp_path = temp_file.name
                        
                        try:
                            # 读取PDF内容
                            reader = PdfReader(temp_path)
                            text_content = []
                            for page in reader.pages:
                                text_content.append(page.extract_text())
                            paper_info["content"] = "\n".join(text_content)
                        except Exception as e:
                            logger.error(f"Error extracting PDF content: {str(e)}")
                            paper_info["content"] = f"Error extracting PDF content: {str(e)}"
                        finally:
                            os.unlink(temp_path)
                    else:
                        logger.error(f"Failed to download PDF, status code: {pdf_response.status_code}")
                        paper_info["content"] = f"Failed to download PDF, status code: {pdf_response.status_code}"
                
                except Exception as e:
                    logger.error(f"Error downloading PDF: {str(e)}")
                    paper_info["content"] = f"Error downloading PDF: {str(e)}"
                results.append(paper_info)
             
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
