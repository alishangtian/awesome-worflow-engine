"""工作流引擎核心实现"""

import json
import asyncio
from typing import Dict, Any, Optional, Type, Set, List
from dataclasses import dataclass
from enum import Enum
import networkx as nx

from ..nodes.base import BaseNode

class WorkflowStatus(Enum):
    """工作流状态"""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class NodeResult:
    """节点执行结果"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None

class WorkflowEngine:
    """工作流执行引擎"""
    
    def __init__(self):
        self._node_types: Dict[str, Type[BaseNode]] = {}
        self._running_workflows: Dict[str, asyncio.Task] = {}
        self._workflow_status: Dict[str, WorkflowStatus] = {}
        self._workflow_progress: Dict[str, Dict[str, NodeResult]] = {}
        
    def register_node_type(self, type_name: str, node_class: Type[BaseNode]):
        """注册节点类型"""
        self._node_types[type_name] = node_class

    def validate_workflow(self, workflow: Dict) -> bool:
        """验证工作流的DAG结构
        
        Args:
            workflow: 工作流定义
            
        Returns:
            bool: 是否合法
            
        Raises:
            ValueError: DAG验证失败时抛出，包含具体原因
        """
        nodes = workflow["nodes"]
        edges = workflow["edges"]
        
        # 检查节点ID唯一性
        node_ids = [node["id"] for node in nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("存在重复的节点ID")
            
        # 检查节点类型是否已注册
        for node in nodes:
            if node["type"] not in self._node_types:
                raise ValueError(f"未注册的节点类型: {node['type']}")
                
        # 构建图并检查是否有环
        G = nx.DiGraph()
        for node in nodes:
            G.add_node(node["id"])
        for edge in edges:
            G.add_edge(edge["from"], edge["to"])
            
        try:
            cycle = nx.find_cycle(G)
            raise ValueError(f"工作流中存在环: {cycle}")
        except nx.NetworkXNoCycle:
            pass
            
        return True
        
    def get_workflow_status(self, workflow_id: str) -> Optional[WorkflowStatus]:
        """获取工作流状态"""
        return self._workflow_status.get(workflow_id)
        
    def get_workflow_progress(self, workflow_id: str) -> Optional[Dict[str, NodeResult]]:
        """获取工作流进度"""
        return self._workflow_progress.get(workflow_id)
        
    async def pause_workflow(self, workflow_id: str):
        """暂停工作流"""
        if workflow_id in self._running_workflows:
            self._workflow_status[workflow_id] = WorkflowStatus.PAUSED
            # 注意：实际任务仍在运行，但新节点不会开始执行
            
    async def resume_workflow(self, workflow_id: str):
        """恢复工作流"""
        if workflow_id in self._workflow_status:
            if self._workflow_status[workflow_id] == WorkflowStatus.PAUSED:
                self._workflow_status[workflow_id] = WorkflowStatus.RUNNING
                
    async def cancel_workflow(self, workflow_id: str):
        """取消工作流"""
        if workflow_id in self._running_workflows:
            self._running_workflows[workflow_id].cancel()
            self._workflow_status[workflow_id] = WorkflowStatus.CANCELLED
            
    async def execute_node(
        self,
        node: Dict,
        processed_params: Dict[str, Any],
        workflow_id: str
    ) -> NodeResult:
        """执行单个节点"""
        import time
        
        start_time = time.time()
        try:
            node_class = self._node_types[node["type"]]
            node_instance = node_class()
            result = await node_instance.execute(processed_params)
            end_time = time.time()
            node_result = NodeResult(
                success=True,
                data=result,
                start_time=start_time,
                end_time=end_time
            )
            # 打印节点执行结果
            duration = end_time - start_time
            print(f"\n节点执行结果:")
            print(f"节点类型: {node['type']}")
            print(f"执行状态: 成功")
            print(f"执行时间: {duration:.2f}秒")
            print(f"输出数据: {result}")
            return node_result
        except Exception as e:
            end_time = time.time()
            node_result = NodeResult(
                success=False,
                error=str(e),
                start_time=start_time,
                end_time=end_time
            )
            # 打印节点执行结果
            duration = end_time - start_time
            print(f"\n节点执行结果:")
            print(f"节点类型: {node['type']}")
            print(f"执行状态: 失败")
            print(f"执行时间: {duration:.2f}秒")
            print(f"错误信息: {str(e)}")
            return node_result
            
    async def execute_workflow(
        self,
        workflow_json: str,
        workflow_id: str,
        global_params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, NodeResult]:
        """执行工作流
        
        Args:
            workflow_json: 工作流JSON定义
            workflow_id: 工作流ID
            global_params: 全局参数
            
        Returns:
            Dict[str, NodeResult]: 节点执行结果
        """
        workflow = json.loads(workflow_json)
        
        # 验证工作流
        self.validate_workflow(workflow)
        
        nodes = workflow["nodes"]
        edges = workflow["edges"]
        
        # 构建节点依赖图
        dependencies: Dict[str, Set[str]] = {node["id"]: set() for node in nodes}
        for edge in edges:
            dependencies[edge["to"]].add(edge["from"])
            
        # 初始化工作流状态
        self._workflow_status[workflow_id] = WorkflowStatus.RUNNING
        self._workflow_progress[workflow_id] = {}
        results: Dict[str, NodeResult] = {}
        
        # 获取没有依赖的起始节点和孤立节点
        start_nodes = []
        for node in nodes:
            node_id = node["id"]
            # 如果节点没有依赖，或者是孤立节点（既没有入边也没有出边）
            if not dependencies[node_id] or not any(
                edge["from"] == node_id or edge["to"] == node_id 
                for edge in edges
            ):
                start_nodes.append(node)
        
        async def process_node(node):
            """处理单个节点"""
            node_id = node["id"]
            
            # 检查工作流是否被暂停
            while self._workflow_status[workflow_id] == WorkflowStatus.PAUSED:
                await asyncio.sleep(1)
                
            # 检查工作流是否被取消
            if self._workflow_status[workflow_id] == WorkflowStatus.CANCELLED:
                return
                
            # 检查依赖节点是否执行成功
            for dep_id in dependencies[node_id]:
                if dep_id not in results or not results[dep_id].success:
                    results[node_id] = NodeResult(
                        success=False,
                        error="依赖节点执行失败"
                    )
                    self._workflow_progress[workflow_id] = results.copy()
                    return
                    
            # 处理参数引用
            processed_params = {}
            for key, value in node["params"].items():
                if isinstance(value, str) and value.startswith("$"):
                    ref_parts = value[1:].split(".")
                    ref_node = ref_parts[0]
                    ref_key = ref_parts[1]
                    processed_params[key] = results[ref_node].data[ref_key]
                else:
                    processed_params[key] = value
                    
            # 执行节点
            result = await self.execute_node(node, processed_params, workflow_id)
            results[node_id] = result
            self._workflow_progress[workflow_id] = results.copy()
            
            # 如果节点执行成功，触发依赖此节点的下游节点
            if result.success:
                downstream_nodes = [
                    n for n in nodes
                    if node_id in dependencies[n["id"]]
                    and all(
                        dep in results and results[dep].success
                        for dep in dependencies[n["id"]]
                    )
                ]
                await asyncio.gather(
                    *(process_node(n) for n in downstream_nodes)
                )
                
        # 并行执行起始节点
        await asyncio.gather(
            *(process_node(node) for node in start_nodes)
        )
        
        # 更新工作流状态
        if all(result.success for result in results.values()):
            self._workflow_status[workflow_id] = WorkflowStatus.COMPLETED
        else:
            self._workflow_status[workflow_id] = WorkflowStatus.FAILED
            
        return results
