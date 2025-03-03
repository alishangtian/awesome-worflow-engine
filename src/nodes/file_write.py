"""文件写入节点"""

import os
from typing import Dict, Any
from .base import BaseNode

class FileWriteNode(BaseNode):
    """文件写入节点"""
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        # 参数结构验证
        if not isinstance(params.get("path"), dict):
            raise ValueError("path参数必须为字典类型，包含完整路径信息")
            
        file_info = params["path"]
        content_data = params["content"]
        
        # 解析路径参数
        file_path = os.path.join(
            str(file_info.get("base_path", "")),
            str(file_info["filename"])
        )
        
        # 解析内容参数
        if isinstance(content_data, dict):
            content = str(content_data.get("data", ""))
            encoding = str(content_data.get("encoding", "utf-8"))
        else:
            content = str(content_data)
            encoding = "utf-8"
            
        # 处理写入模式
        mode = str(params.get("mode", {"type": "overwrite"}).get("type", "w"))
        
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
