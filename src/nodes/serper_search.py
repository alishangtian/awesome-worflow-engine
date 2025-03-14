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
        api_key = os.getenv("SERPER_API_KEY", "")
        if not api_key:
            raise ValueError("未设置SERPER_API_KEY环境变量")

        # 获取可选参数
        country = str(params.get("country", "cn"))
        language = str(params.get("language", "zh"))
        maxResults = int(params.get("max_results", 10))

        try:
            async with aiohttp.ClientSession() as session:
                # 准备请求数据
                headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
                payload = {"q": query, "gl": country, "hl": language, "num": maxResults}

                # 发送请求
                async with session.post(
                    "https://google.serper.dev/search", headers=headers, json=payload
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        # 处理搜索结果
                        results = []

                        # 处理answerBox
                        answer_box = data.get("answerBox")
                        if answer_box:
                            results.append(
                                {
                                    "title": answer_box.get("title", ""),
                                    "link": "",  # answerBox通常没有链接
                                    "snippet": answer_box.get("answer", ""),
                                    "is_answer_box": True,
                                }
                            )

                        # 处理organic结果
                        organic_results = data.get("organic", [])
                        for result in organic_results:
                            results.append(
                                {
                                    "title": result.get("title", ""),
                                    "link": result.get("link", ""),
                                    "snippet": result.get("snippet", ""),
                                }
                            )

                        return {
                            "success": True,
                            "error": None,
                            "results": results,
                            "count": len(results),
                        }
                    else:
                        error_text = await response.text()
                        return {
                            "success": False,
                            "error": f"API请求失败: {error_text}",
                            "results": [],
                            "count": 0,
                        }

        except Exception as e:
            return {"success": False, "error": str(e), "results": [], "count": 0}

    async def agent_execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行节点并将结果转换为统一格式

        将搜索结果转换为易读的文本格式，包括查询信息和搜索结果列表。

        Args:
            params: 节点参数

        Returns:
            Dict[str, Any]: 执行结果，包含纯文本格式的'result'键
        """
        try:
            execute_result = await self.execute(params)
            result_text = "搜索结果列表："
            # 组织搜索结果信息
            if not execute_result["success"]:
                result_text += f"Error: {execute_result['error']}"
                return {"result": result_text, **execute_result}

            # 添加搜索结果
            for i, result in enumerate(execute_result["results"], 1):
                result_text += f"{i}. "
                if result.get("is_answer_box"):
                    result_text += "[Answer Box] "
                result_text += f"标题：{result['title']} "

                if result["link"]:
                    result_text += f"网址：{result['link']} "

                if result["snippet"]:
                    result_text += f"摘要：{result['snippet']}；"

            return {"result": result_text}
        except Exception as e:
            return {"result": f"Error: {str(e)}", "error": str(e)}