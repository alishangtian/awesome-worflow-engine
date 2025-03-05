"""LlamaIndex 索引构建节点"""

from typing import Dict, Any
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
from llama_index.core.settings import Settings
from llama_index.embeddings.ollama  import OllamaEmbedding
from llama_index.core.node_parser import SentenceSplitter 
import shutil
import os
from .base import BaseNode
from ..api.config import API_CONFIG

class IndexBuildNode(BaseNode):
    """索引构建节点 - 负责文档加载和索引创建"""
    
    def __init__(self):
        # 初始化默认配置
        Settings.embed_model = OllamaEmbedding(
                                model_name="bge-large",
                                base_url="http://10.234.20.35:11434",
                                ollama_additional_kwargs={"mirostat": 0},
                            )
        Settings.node_parser = SentenceSplitter(chunk_size=1024, chunk_overlap=200)

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        doc_dir = API_CONFIG["doc_dir"]
        index_dir = API_CONFIG["index_dir"]
        clear_existing = False

        if not os.path.exists(doc_dir):
            raise ValueError(f"文档目录不存在: {doc_dir}")

        try:
            # 清理已有索引
            if clear_existing and os.path.exists(index_dir):
                shutil.rmtree(index_dir)

            # 加载文档
            documents = SimpleDirectoryReader(doc_dir).load_data()
            
            # 构建索引
            index = VectorStoreIndex.from_documents(
                documents,
                show_progress=True
            )
            
            # 持久化存储
            index.storage_context.persist(persist_dir=index_dir)
            
            return {
                "result": "success",
                "doc_count": len(documents),
                "index_dir": index_dir,
                "index_stats": {
                    "nodes": len(index.docstore.docs),
                    "embeddings": index.vector_store.client.count()
                }
            }
            
        except Exception as e:
            if os.path.exists(index_dir):
                shutil.rmtree(index_dir)
            raise ValueError(f"索引构建失败: {str(e)}")