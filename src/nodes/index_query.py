"""LlamaIndex 索引查询节点"""

from typing import Dict, Any
from llama_index.core import VectorStoreIndex, StorageContext
from llama_index.core.settings import Settings
from llama_index.llms.openai import OpenAI
import os
from .base import BaseNode
from ..api.config import API_CONFIG

class IndexQueryNode(BaseNode):
    """索引查询节点 - 负责执行语义搜索和问答"""
    
    def __init__(self):
        Settings.llm = OpenAI(model=API_CONFIG["model_name"], 
                              api_key=API_CONFIG["api_key"], 
                              base_url=API_CONFIG["base_url"])

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        参数要求：
        {
            "query_str": "问题内容",    # 必填，查询内容
            "similarity_top_k": 5,     # 可选，返回结果数量
            "response_mode": "compact" # 可选，响应模式
        }
        """
        index_dir = API_CONFIG["index_dir"]
        query_str = str(params["query_str"])
        top_k = int(params.get("similarity_top_k", 3))
        response_mode = str(params.get("response_mode", "compact"))

        if not os.path.exists(index_dir):
            raise ValueError(f"索引目录不存在: {index_dir}")

        try:
            # 加载索引
            storage_context = StorageContext.from_defaults(
                persist_dir=index_dir
            )
            index = VectorStoreIndex.load(
                storage_context=storage_context,
                embed_model=Settings.embed_model
            )
            
            # 执行查询
            query_engine = index.as_query_engine(
                similarity_top_k=top_k,
                response_mode=response_mode
            )
            response = query_engine.query(query_str)
            
            # 格式化结果
            return self._format_response(response, query_str)
            
        except Exception as e:
            raise ValueError(f"查询执行失败: {str(e)}")

    def _format_response(self, response, query_str) -> Dict[str, Any]:
        sources = []
        for node in response.source_nodes:
            source_info = {
                "text": node.node.get_content(),
                "score": float(node.score),
                "metadata": dict(node.node.metadata),
                "node_id": node.node.node_id
            }
            if 'file_path' in node.node.metadata:
                source_info["file_name"] = os.path.basename(
                    node.node.metadata['file_path']
                )
            sources.append(source_info)

        return {
            "result": "success",
            "query": query_str,
            "answer": str(response).strip(),
            "sources": sources,
            "generation_info": dict(response.metadata)
        }