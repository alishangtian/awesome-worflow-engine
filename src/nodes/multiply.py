"""乘法节点"""

from typing import Dict, Any
from .base import BaseNode

class MultiplyNode(BaseNode):
    """乘法节点"""
    
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        num1 = float(params["num1"])
        num2 = float(params["num2"])
        
        result = num1 * num2
        return {"result": result}
