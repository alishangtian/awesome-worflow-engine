"""文本连接节点"""

from typing import Dict, Any
from .base import BaseNode

class TextConcatNode(BaseNode):
    """文本连接节点"""
    
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        text1 = str(params["text1"])
        text2 = str(params["text2"])
        separator = str(params.get("separator", ""))
        
        result = separator.join([text1, text2])
        return {"result": result}
