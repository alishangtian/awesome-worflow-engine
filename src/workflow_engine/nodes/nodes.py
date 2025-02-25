"""节点类型实现"""

from typing import Dict, Any
from .base import BaseNode
from ..api.config import API_CONFIG
import aiohttp

class TextConcatNode(BaseNode):
    """文本连接节点"""
    
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        text1 = str(params["text1"])
        text2 = str(params["text2"])
        separator = str(params.get("separator", ""))
        
        result = separator.join([text1, text2])
        return {"result": result}

class TextReplaceNode(BaseNode):
    """文本替换节点"""
    
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        text = str(params["text"])
        old_str = str(params["old_str"])
        new_str = str(params["new_str"])
        
        result = text.replace(old_str, new_str)
        return {"result": result}

class AddNode(BaseNode):
    """加法节点"""
    
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        num1 = float(params["num1"])
        num2 = float(params["num2"])
        
        result = num1 + num2
        return {"result": result}

class MultiplyNode(BaseNode):
    """乘法节点"""
    
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        num1 = float(params["num1"])
        num2 = float(params["num2"])
        
        result = num1 * num2
        return {"result": result}

class ChatNode(BaseNode):
    """LLM对话节点"""
    
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        input_text = str(params["input"])
        model = str(params.get("model", "gpt-3.5-turbo"))
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
                return {"result": result["choices"][0]["message"]["content"]}
