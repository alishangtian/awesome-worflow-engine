"""终端命令执行节点"""

import subprocess
from typing import Dict, Any
from .base import BaseNode

class TerminalNode(BaseNode):
    """终端命令执行节点"""
    
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        command = str(params["command"])
        shell = params.get("shell", True)
        
        try:
            # 执行shell命令
            process = subprocess.run(
                command,
                shell=shell,
                capture_output=True,
                text=True
            )
            
            return {
                "stdout": process.stdout,
                "stderr": process.stderr,
                "return_code": process.returncode,
                "success": process.returncode == 0
            }
        except Exception as e:
            return {
                "stdout": "",
                "stderr": str(e),
                "return_code": -1,
                "success": False
            }
