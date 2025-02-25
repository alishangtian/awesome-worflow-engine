"""文件写入节点"""

import os
from typing import Dict, Any
from .base import BaseNode

class FileWriteNode(BaseNode):
    """文件写入节点"""
    
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        file_path = str(params["path"])
        content = str(params["content"])
        encoding = str(params.get("encoding", "utf-8"))
        mode = str(params.get("mode", "w"))  # 'w' 覆盖, 'a' 追加
        
        # 确保目录存在
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        
        try:
            with open(file_path, mode, encoding=encoding) as f:
                f.write(content)
            return {
                "result": "success",
                "path": file_path,
                "bytes_written": len(content.encode(encoding)),
                "encoding": encoding,
                "mode": mode
            }
        except Exception as e:
            raise ValueError(f"写入文件失败: {str(e)}")
