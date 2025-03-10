"""LLM对话节点"""

from typing import Dict, Any
from .base import BaseNode
from ..api.llm_api import call_llm_api

class ChatNode(BaseNode):
    """LLM对话节点"""
    
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        input_text = str(params["input"])
        temperature = float(params.get("temperature", 0.7))

        messages = [
            {"role": "user", "content": input_text}
        ]

        try:
            response = await call_llm_api(messages, temperature=temperature)
            return {"response": response}
        except Exception as e:
            raise ValueError(f"LLM API调用失败: {str(e)}")
