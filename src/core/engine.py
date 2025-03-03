"""工作流引擎核心实现"""

import json
import asyncio
import concurrent.futures
from typing import Dict, Any, Optional, Type, Set, List, Callable
from dataclasses import dataclass
from enum import Enum
import networkx as nx
from concurrent.futures import ThreadPoolExecutor

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
    
    def __init__(self, max_workers: int = 4):
        self._node_types: Dict[str, Type[BaseNode]] = {}
        self._running_workflows: Dict[str, asyncio.Task] = {}
        self._workflow_status: Dict[str, WorkflowStatus] = {}
        self._workflow_progress: Dict[str, Dict[str, NodeResult]] = {}
        self._thread_pool = ThreadPoolExecutor(max_workers=max_workers)
        self._node_callbacks: List[Callable[[str, str, NodeResult], None]] = []
        
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
            
    def register_node_callback(self, callback: Callable[[str, str, NodeResult], None]):
        """注册节点执行回调函数
        
        Args:
            callback: 回调函数，参数为(workflow_id, node_id, node_result)
        """
        self._node_callbacks.append(callback)

    def _notify_node_completion(self, workflow_id: str, node_id: str, result: NodeResult):
        """通知节点执行完成
        
        Args:
            workflow_id: 工作流ID
            node_id: 节点ID
            result: 节点执行结果
        """
        for callback in self._node_callbacks:
            try:
                callback(workflow_id, node_id, result)
            except Exception as e:
                print(f"回调函数执行失败: {str(e)}")

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
            
            # 使用线程池执行节点
            loop = asyncio.get_event_loop()
            if asyncio.iscoroutinefunction(node_instance.execute):
                # 如果是异步方法，在线程池中等待其完成
                result = await loop.run_in_executor(
                    self._thread_pool,
                    lambda: asyncio.run(node_instance.execute(processed_params))
                )
            else:
                # 如果是同步方法，直接在线程池中执行
                result = await loop.run_in_executor(
                    self._thread_pool,
                    lambda: node_instance.execute(processed_params)
                )
            
            end_time = time.time()
            node_result = NodeResult(
                success=True,
                data=result,
                start_time=start_time,
                end_time=end_time
            )
            # 创建执行结果
            duration = end_time - start_time
            # 通知节点执行完成
            self._notify_node_completion(workflow_id, node["id"], node_result)
            return node_result
        except Exception as e:
            end_time = time.time()
            node_result = NodeResult(
                success=False,
                error=str(e),
                start_time=start_time,
                end_time=end_time
            )
            # 创建错误结果
            duration = end_time - start_time
            # 通知节点执行完成
            self._notify_node_completion(workflow_id, node["id"], node_result)
            return node_result
            
    async def _check_workflow_status(self, workflow_id: str) -> bool:
        """检查工作流状态
        
        Args:
            workflow_id: 工作流ID
            
        Returns:
            bool: 是否可以继续执行
        """
        while self._workflow_status[workflow_id] == WorkflowStatus.PAUSED:
            await asyncio.sleep(1)
            
        return self._workflow_status[workflow_id] != WorkflowStatus.CANCELLED

    def _check_dependencies(
        self,
        node_id: str,
        dependencies: Dict[str, Set[str]],
        results: Dict[str, NodeResult],
        workflow_id: str
    ) -> bool:
        """检查节点依赖是否满足
        
        Args:
            node_id: 节点ID
            dependencies: 依赖关系图
            results: 已有的执行结果
            workflow_id: 工作流ID
            
        Returns:
            bool: 依赖是否满足
        """
        for dep_id in dependencies[node_id]:
            if dep_id not in results or not results[dep_id].success:
                results[node_id] = NodeResult(
                    success=False,
                    error="依赖节点执行失败"
                )
                self._workflow_progress[workflow_id] = results.copy()
                return False
        return True

    def _process_params(
        self,
        params: Dict[str, Any],
        results: Dict[str, NodeResult]
    ) -> Dict[str, Any]:
        """处理节点参数
        
        Args:
            params: 原始参数
            results: 已有的执行结果
            
        Returns:
            Dict[str, Any]: 处理后的参数
        """
        processed_params = {}
        for key, value in params.items():
            if isinstance(value, str) and value.startswith("$"):
                ref_parts = value[1:].split(".")
                ref_node = ref_parts[0]
                ref_key = ref_parts[1]
                processed_params[key] = results[ref_node].data[ref_key]
            else:
                processed_params[key] = value
        return processed_params

    def _get_downstream_nodes(
        self,
        node_id: str,
        nodes: List[Dict],
        dependencies: Dict[str, Set[str]],
        results: Dict[str, NodeResult]
    ) -> List[Dict]:
        """获取可执行的下游节点
        
        Args:
            node_id: 当前节点ID
            nodes: 所有节点列表
            dependencies: 依赖关系图
            results: 已有的执行结果
            
        Returns:
            List[Dict]: 可执行的下游节点列表
        """
        return [
            n for n in nodes
            if node_id in dependencies[n["id"]]
            and all(
                dep in results and results[dep].success
                for dep in dependencies[n["id"]]
            )
        ]

    async def _process_node(
        self,
        node: Dict,
        workflow_id: str,
        dependencies: Dict[str, Set[str]],
        nodes: List[Dict],
        results: Dict[str, NodeResult]
    ):
        """处理单个节点
        
        Args:
            node: 节点定义
            workflow_id: 工作流ID
            dependencies: 依赖关系图
            nodes: 所有节点列表
            results: 执行结果字典
        """
        node_id = node["id"]
        
        # 检查工作流状态
        if self._workflow_status[workflow_id] == WorkflowStatus.CANCELLED:
            return
            
        # 检查依赖
        if not self._check_dependencies(node_id, dependencies, results, workflow_id):
            return
            
        # 处理参数
        processed_params = self._process_params(node["params"], results)
            
        # 执行节点
        result = await self.execute_node(node, processed_params, workflow_id)
        results[node_id] = result
        
        # 更新工作流进度
        self._workflow_progress[workflow_id] = results.copy()
        
        # 处理下游节点
        if result.success:
            downstream_nodes = self._get_downstream_nodes(
                node_id, nodes, dependencies, results
            )
            
            # 创建下游节点的任务
            tasks = []
            for n in downstream_nodes:
                task = asyncio.create_task(
                    self._process_node(n, workflow_id, dependencies, nodes, results)
                )
                tasks.append(task)
            
            # 等待所有下游节点完成
            if tasks:
                await asyncio.gather(*tasks)

    async def execute_workflow_stream(
        self,
        workflow_json: str,
        workflow_id: str,
        global_params: Optional[Dict[str, Any]] = None
    ):
        """流式执行工作流
        
        Args:
            workflow_json: 工作流JSON定义
            workflow_id: 工作流ID
            global_params: 全局参数
            
        Yields:
            Tuple[str, NodeResult]: 节点ID和执行结果的元组
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
        results: Dict[str, NodeResult] = {}
        
        try:
            # 获取没有依赖的起始节点和孤立节点
            start_nodes = []
            for node in nodes:
                node_id = node["id"]
                if not dependencies[node_id] or not any(
                    edge["from"] == node_id or edge["to"] == node_id 
                    for edge in edges
                ):
                    start_nodes.append(node)
            
            # 串行执行节点以支持流式输出
            for node in start_nodes:
                async for node_id, node_result in self._process_node_stream(node, workflow_id, dependencies, nodes, results):
                    yield node_id, node_result
            
            # 更新工作流状态
            if all(result.success for result in results.values()):
                self._workflow_status[workflow_id] = WorkflowStatus.COMPLETED
            else:
                self._workflow_status[workflow_id] = WorkflowStatus.FAILED
                
        except Exception as e:
            self._workflow_status[workflow_id] = WorkflowStatus.FAILED
            raise

    async def _process_node_stream(
        self,
        node: Dict,
        workflow_id: str,
        dependencies: Dict[str, Set[str]],
        nodes: List[Dict],
        results: Dict[str, NodeResult]
    ):
        """流式处理单个节点
        
        Args:
            node: 节点定义
            workflow_id: 工作流ID
            dependencies: 依赖关系图
            nodes: 所有节点列表
            results: 执行结果字典
            
        Yields:
            Tuple[str, NodeResult]: 节点ID和执行结果的元组
        """
        node_id = node["id"]
        
        # 检查工作流状态
        if self._workflow_status[workflow_id] == WorkflowStatus.CANCELLED:
            return
            
        # 检查依赖
        if not self._check_dependencies(node_id, dependencies, results, workflow_id):
            return
            
        # 处理参数
        processed_params = self._process_params(node["params"], results)
            
        # 执行节点
        result = await self.execute_node(node, processed_params, workflow_id)
        results[node_id] = result
        # 更新工作流进度
        self._workflow_progress[workflow_id] = results.copy()
        yield node_id, result
        
        # 处理下游节点
        if result.success:
            downstream_nodes = self._get_downstream_nodes(
                node_id, nodes, dependencies, results
            )
            for n in downstream_nodes:
                async for downstream_id, downstream_result in self._process_node_stream(
                    n, workflow_id, dependencies, nodes, results
                ):
                    yield downstream_id, downstream_result

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
        results: Dict[str, NodeResult] = {}
        
        try:
            # 获取没有依赖的起始节点和孤立节点
            start_nodes = []
            for node in nodes:
                node_id = node["id"]
                if not dependencies[node_id] or not any(
                    edge["from"] == node_id or edge["to"] == node_id 
                    for edge in edges
                ):
                    start_nodes.append(node)
            
            # 并行执行起始节点
            await asyncio.gather(
                *(self._process_node(node, workflow_id, dependencies, nodes, results)
                  for node in start_nodes)
            )
            
            # 更新工作流状态
            if all(result.success for result in results.values()):
                self._workflow_status[workflow_id] = WorkflowStatus.COMPLETED
            else:
                self._workflow_status[workflow_id] = WorkflowStatus.FAILED
                
            return results
            
        except Exception as e:
            self._workflow_status[workflow_id] = WorkflowStatus.FAILED
            raise
