from typing import Dict, Any
import os
import logging
import time
import requests
from .base import BaseNode

logger = logging.getLogger(__name__)


class SerperWebCrawlerNode(BaseNode):
    """网络爬虫节点 - 使用 Serper API 接收 URL 并返回网页正文内容的节点

    参数:
        url (str): 需要抓取的网页URL

    返回:
        dict: 包含执行状态、错误信息和提取的正文内容
    """

    def __init__(self):
        super().__init__()
        self.api_key = os.getenv("SERPER_API_KEY", "")
        self.api_url = "https://scrape.serper.dev"

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        start_time = time.time()
        url = str(params.get("url", "")).strip()
        if not url:
            raise ValueError("url参数不能为空")

        logger.info(f"开始爬取: {url}")

        try:
            # 准备请求头和数据
            headers = {"X-API-KEY": self.api_key, "Content-Type": "application/json"}
            data = {"url": url}

            # 发送请求
            response = requests.post(
                self.api_url, headers=headers, json=data, timeout=120
            )
            response.raise_for_status()

            # 获取响应内容
            result = response.json()
            text = result.get("text", "")
            
            # 去除空行
            text = "\n".join(line for line in text.splitlines() if line.strip())

            end_time = time.time()
            execution_time = end_time - start_time
            content_length = len(text)
            logger.info(
                f"爬取成功: {url}, 内容长度: {content_length} 字符, 耗时: {execution_time:.2f} 秒"
            )

            return {"success": True, "error": None, "content": text}

        except requests.Timeout:
            end_time = time.time()
            execution_time = end_time - start_time
            error_msg = f"请求超时: {url}"
            logger.error(f"{error_msg}, 耗时: {execution_time:.2f} 秒")
            return {"success": False, "error": error_msg, "content": ""}

        except requests.RequestException as e:
            end_time = time.time()
            execution_time = end_time - start_time
            error_msg = f"请求错误: {str(e)}"
            logger.error(f"{error_msg}, URL: {url}, 耗时: {execution_time:.2f} 秒")
            return {"success": False, "error": error_msg, "content": ""}

        except Exception as e:
            end_time = time.time()
            execution_time = end_time - start_time
            error_msg = f"未知错误: {str(e)}"
            logger.error(f"{error_msg}, URL: {url}, 耗时: {execution_time:.2f} 秒")
            return {"success": False, "error": error_msg, "content": ""}

    async def agent_execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        execution_result = await self.execute(params)
        return {"result": execution_result.get("content", "")}
