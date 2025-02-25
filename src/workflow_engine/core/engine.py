"""工作流引擎核心实现"""

import json
from typing import Dict, Any, Optional, Type
from dataclasses import dataclass

from ..nodes.base import BaseNode

@dataclass
class NodeResult:
    """节点执行结果"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class WorkflowEngine:
    """工作流执行引擎"""
    
    def __init__(self):
        self._node_types: Dict[str, Type[BaseNode]] = {}
        
    def register_node_type(self, type_name: str, node_class: Type[BaseNode]):
        """注册节点类型"""
        self._node_types[type_name] = node_class
        
    async def execute_workflow(
        self,
        workflow_json: str,
        global_params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, NodeResult]:
        """执行工作流
        
        Args:
            workflow_json: 工作流JSON定义
            global_params: 全局参数
            
        Returns:
            Dict[str, NodeResult]: 节点执行结果
        """
        workflow = json.loads(workflow_json)
        nodes = workflow["nodes"]
        edges = workflow["edges"]
        
        # 构建节点依赖图
        dependencies = {node["id"]: [] for node in nodes}
        for edge in edges:
            dependencies[edge["to"]].append(edge["from"])
            
        # 存储节点执行结果
        results: Dict[str, NodeResult] = {}
        
        # 执行节点
        for node in nodes:
            node_id = node["id"]
            node_type = node["type"]
            params = node["params"]
            
            # 检查依赖节点是否执行成功
            deps_ok = True
            for dep_id in dependencies[node_id]:
                if dep_id not in results or not results[dep_id].success:
                    deps_ok = False
                    break
                    
            if not deps_ok:
                results[node_id] = NodeResult(
                    success=False,
                    error="依赖节点执行失败"
                )
                continue
                
            # 替换参数中的引用
            processed_params = {}
            for key, value in params.items():
                if isinstance(value, str) and value.startswith("$"):
                    # 格式: $node_id.result
                    ref_parts = value[1:].split(".")
                    ref_node = ref_parts[0]
                    ref_key = ref_parts[1]
                    processed_params[key] = results[ref_node].data[ref_key]
                else:
                    processed_params[key] = value
                    
            # 创建并执行节点
            try:
                node_class = self._node_types[node_type]
                node_instance = node_class()
                result = await node_instance.execute(processed_params)
                results[node_id] = NodeResult(
                    success=True,
                    data=result
                )
            except Exception as e:
                results[node_id] = NodeResult(
                    success=False,
                    error=str(e)
                )
                
        return results
