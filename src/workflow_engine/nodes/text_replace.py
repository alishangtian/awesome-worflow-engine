"""文本替换节点"""

from typing import Dict, Any
from .base import BaseNode

class TextReplaceNode(BaseNode):
    """文本替换节点"""
    
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        text = str(params["text"])
        old_str = str(params["old_str"])
        new_str = str(params["new_str"])
        
        result = text.replace(old_str, new_str)
        return {"result": result}
