"""LLM API调用模块"""

import logging
import json
import asyncio
import aiohttp
from typing import List, Dict, Union, AsyncGenerator
from .config import API_CONFIG, retry_on_error

# 配置日志记录
logger = logging.getLogger(__name__)

async def call_llm_api_stream(messages: List[Dict[str, str]], request_id: str = None) -> AsyncGenerator[str, None]:
    """
    调用llm API服务(流式),支持自动重试
    
    Args:
        messages: 消息列表
        request_id: 请求ID,用于日志追踪
    
    Returns:
        异步生成器,生成流式响应内容
    """
    if request_id:
        logger.info(f"[{request_id}] 开始流式调用llm API")
        
    async with aiohttp.ClientSession() as session:
        headers = {
            "Authorization": f"Bearer {API_CONFIG['api_key']}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": API_CONFIG["model_name"],
            "messages": messages,
            "stream": True
        }
        
        try:
            async with session.post(
                f"{API_CONFIG['base_url']}/chat/completions",
                headers=headers,
                json=data,
                timeout=30
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    if request_id:
                        logger.error(f"[{request_id}] API调用失败: {error_text}")
                    raise ValueError(f"API调用失败: {error_text}")
                
                async for line in response.content:
                    if line:
                        try:
                            line = line.decode('utf-8').strip()
                            if line.startswith('data: ') and line != 'data: [DONE]':
                                json_str = line[6:]  # 去掉 "data: "
                                data = json.loads(json_str)
                                if len(data['choices']) > 0:
                                    delta = data['choices'][0].get('delta', {})
                                    if 'content' in delta:
                                        yield delta['content']
                        except Exception as e:
                            logger.error(f"[{request_id}] 处理流式响应出错: {str(e)}")
                
        except asyncio.TimeoutError:
            error_msg = "API调用超时"
            if request_id:
                logger.error(f"[{request_id}] {error_msg}")
            raise ValueError(error_msg)
        except Exception as e:
            if request_id:
                logger.error(f"[{request_id}] API调用异常: {str(e)}")
            raise

@retry_on_error(max_retries=3)
async def call_llm_api(messages: List[Dict[str, str]], request_id: str = None) -> str:
    """
    调用llm API服务，支持自动重试
    
    Args:
        messages: 消息列表
        request_id: 请求ID,用于日志追踪
    
    Returns:
        返回完整响应字符串
    """
    if request_id:
        logger.info(f"[{request_id}] 开始调用llm API")
        
    async with aiohttp.ClientSession() as session:
        headers = {
            "Authorization": f"Bearer {API_CONFIG['api_key']}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": API_CONFIG["model_name"],
            "messages": messages,
            "stream": False
        }
        
        try:
            async with session.post(
                f"{API_CONFIG['base_url']}/chat/completions",
                headers=headers,
                json=data,
                timeout=30
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    if request_id:
                        logger.error(f"[{request_id}] API调用失败: {error_text}")
                    raise ValueError(f"API调用失败: {error_text}")
                
                result = await response.json()
                if request_id:
                    logger.info(f"[{request_id}] API调用成功")
                return result["choices"][0]["message"]["content"]
                
        except asyncio.TimeoutError:
            error_msg = "API调用超时"
            if request_id:
                logger.error(f"[{request_id}] {error_msg}")
            raise ValueError(error_msg)
        except Exception as e:
            if request_id:
                logger.error(f"[{request_id}] API调用异常: {str(e)}")
            raise
