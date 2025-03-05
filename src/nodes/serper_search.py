"""Serper搜索节点 - 返回搜索结果"""

from typing import Dict, Any
import aiohttp
from .base import BaseNode
from ..api.config import API_CONFIG
import os

class SerperSearchNode(BaseNode):
    """Serper搜索节点 - 返回搜索结果"""
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        # 获取搜索关键词
        query = str(params.get("query", ""))
        if not query:
            raise ValueError("query参数不能为空")
        
        # 获取API密钥
        api_key = API_CONFIG.get("serper_api_key")
        if not api_key:
            raise ValueError("未设置SERPER_API_KEY环境变量")
            
        # 获取可选参数
        country = str(params.get("country", "cn"))
        language = str(params.get("language", "zh"))
        
        try:
            async with aiohttp.ClientSession() as session:
                # 准备请求数据
                headers = {
                    "X-API-KEY": api_key,
                    "Content-Type": "application/json"
                }
                payload = {
                    "q": query,
                    "gl": country,
                    "hl": language
                }
                
                # 发送请求
                async with session.post(
                    "https://google.serper.dev/search",
                    headers=headers,
                    json=payload
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        # 处理搜索结果
                        results = []
                        
                        # 处理answerBox
                        answer_box = data.get("answerBox")
                        if answer_box:
                            results.append({
                                "title": answer_box.get("title", ""),
                                "link": "",  # answerBox通常没有链接
                                "snippet": answer_box.get("answer", ""),
                                "is_answer_box": True
                            })
                        
                        # 处理organic结果
                        organic_results = data.get("organic", [])
                        for result in organic_results:
                            results.append({
                                "title": result.get("title", ""),
                                "link": result.get("link", ""),
                                "snippet": result.get("snippet", "")
                            })
                        
                        return {
                            "success": True,
                            "error": None,
                            "results": results,
                            "count": len(results)
                        }
                    else:
                        error_text = await response.text()
                        return {
                            "success": False,
                            "error": f"API请求失败: {error_text}",
                            "results": [],
                            "count": 0
                        }
                        
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "results": [],
                "count": 0
            }
