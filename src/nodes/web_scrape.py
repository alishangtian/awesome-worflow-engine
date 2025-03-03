"""网页爬取节点"""

from typing import Dict, Any
from .base import BaseNode
from crawl4ai import AsyncWebCrawler
import os
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class WebScrapeNode(BaseNode):
    """网页爬取节点，使用crawl4ai获取页面内容"""
    
    def __init__(self):
        super().__init__()
        
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        url = str(params["url"])
        output_dir = str(params.get("output_dir", "output"))
        
        try:
            # 确保输出目录存在
            os.makedirs(output_dir, exist_ok=True)
            
            # 使用AsyncWebCrawler爬取内容
            async with AsyncWebCrawler() as crawler:
                result = await crawler.arun(url=url)
                
                # 保存markdown内容到文件
                output_file = os.path.join(output_dir, "output.md")
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(result.markdown)
                
                return {
                    "result": "success",
                    "url": url,
                    "output_file": output_file,
                    "content_length": len(result.markdown),
                    "error": None
                }
                
        except Exception as e:
            error_msg = f"网页爬取失败: {str(e)}"
            logger.error(error_msg)
            return {
                "result": "failure",
                "url": url,
                "output_file": None,
                "content_length": 0,
                "error": error_msg
            }
