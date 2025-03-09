"""LLM对话节点"""

from typing import Dict, Any
import aiohttp
from .base import BaseNode
from ..api.config import API_CONFIG

class ChatNode(BaseNode):
    """LLM对话节点"""
    
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        input_text = str(params["input"])
        model = str(params.get("model", "deepseek-chat"))
        temperature = float(params.get("temperature", 0.7))
        
        messages = [
            {"role": "user", "content": input_text}
        ]
        
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {API_CONFIG['api_key']}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": model,
                "messages": messages,
                "temperature": temperature
            }
            
            async with session.post(
                f"{API_CONFIG['base_url']}/chat/completions",
                headers=headers,
                json=data
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise ValueError(f"API调用失败 (状态码: {response.status}): {error_text}")
                
                result = await response.json()
                return {"response": result["choices"][0]["message"]["content"]}
