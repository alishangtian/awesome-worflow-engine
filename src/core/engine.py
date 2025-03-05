import json
import asyncio
import concurrent.futures
from typing import Dict, Any, Optional, Type, Set, List, Callable, AsyncGenerator, Tuple
from dataclasses import dataclass
from enum import Enum
import networkx as nx
from concurrent.futures import ThreadPoolExecutor

from ..nodes.base import BaseNode

class NodeStatus(Enum):
    """节点状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

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
    status: NodeStatus
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

    def _notify_node_completion(self, workflow_id: str, node_id: str, result: NodeResult) -> Dict[str, Any]:
        """通知节点执行完成
        
        Args:
            workflow_id: 工作流ID
            node_id: 节点ID
            result: 节点执行结果
            
        Returns:
            Dict[str, Any]: 回调函数返回的结果
        """
        # 先尝试执行回调函数
        for callback in self._node_callbacks:
            try:
                callback_result = callback(workflow_id, node_id, result)
                if callback_result:
                    return callback_result
            except Exception as e:
                print(f"回调函数执行失败: {str(e)}")
        
        # 如果没有回调函数或都失败了，返回默认结果
        return {
            "node_id": node_id,  # node_id来自方法参数
            "success": result.success,
            "status": result.status.value,
            "data": result.data if result.success else None,
            "error": result.error if not result.success else None
        }

    async def execute_node(
        self,
        node: Dict,
        processed_params: Dict[str, Any],
        workflow_id: str
    ) -> AsyncGenerator[NodeResult, None]:
        """执行单个节点，支持流式返回结果"""
        import time
        
        start_time = time.time()
        # 创建初始结果并通知状态为运行中
        initial_result = NodeResult(
            success=True,
            status=NodeStatus.RUNNING,
            start_time=start_time
        )
        yield initial_result

        try:
            node_class = self._node_types[node["type"]]
            node_instance = node_class()
            
            # 使用线程池执行节点
            loop = asyncio.get_event_loop()
            if asyncio.iscoroutinefunction(node_instance.execute):
                # 如果是异步生成器方法，直接获取结果流
                if hasattr(node_instance.execute, '__aiter__'):
                    async for intermediate_result in node_instance.execute(processed_params):
                        # 创建中间结果
                        running_result = NodeResult(
                            success=True,
                            status=NodeStatus.RUNNING,
                            data=intermediate_result,
                            start_time=start_time
                        )
                        yield running_result
                        result = intermediate_result
                else:
                    # 如果是普通异步方法，在线程池中等待其完成
                    result = await node_instance.execute(processed_params)
            else:
                # 如果是同步方法，检查是否是生成器
                if hasattr(node_instance.execute, '__iter__'):
                    # 同步生成器方法
                    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                    try:
                        for intermediate_result in await loop.run_in_executor(
                            executor,
                            lambda: list(node_instance.execute(processed_params))
                        ):
                            # 创建中间结果
                            running_result = NodeResult(
                                success=True,
                                status=NodeStatus.RUNNING,
                                data=intermediate_result,
                                start_time=start_time
                            )
                            yield running_result
                            result = intermediate_result
                    finally:
                        executor.shutdown(wait=False)
                else:
                    # 普通同步方法
                    result = await loop.run_in_executor(
                        self._thread_pool,
                        node_instance.execute,
                        processed_params
                    )
            
            end_time = time.time()
            final_result = NodeResult(
                success=True,
                status=NodeStatus.COMPLETED,
                data=result if 'result' in locals() else None,
                start_time=start_time,
                end_time=end_time
            )
            yield final_result

        except Exception as e:
            end_time = time.time()
            error_result = NodeResult(
                success=False,
                status=NodeStatus.FAILED,
                error=str(e),
                start_time=start_time,
                end_time=end_time
            )
            yield error_result
            
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
                    status=NodeStatus.FAILED,
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
        """处理节点参数，支持嵌套参数和表达式替换
        
        Args:
            params: 原始参数
            results: 已有的执行结果
            
        Returns:
            Dict[str, Any]: 处理后的参数
            
        Examples:
            >>> params = {
            ...     "text": "Search for $node1.query about $node2.topic",
            ...     "config": {
            ...         "source": "$node3.data_source",
            ...         "filters": ["$node4.filter1", "$node4.filter2"]
            ...     }
            ... }
        """
        import re
        
        def replace_expression(value: str) -> str:
            """替换字符串中的所有参数表达式"""
            pattern = r'\$([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)'
            
            def replace(match):
                node_id = match.group(1)
                param_key = match.group(2)
                if node_id not in results:
                    raise ValueError(f"引用了未执行的节点: {node_id}")
                if not results[node_id].data:
                    raise ValueError(f"节点 {node_id} 没有返回数据")
                if param_key not in results[node_id].data:
                    raise ValueError(f"节点 {node_id} 的结果中不存在参数: {param_key}")
                return str(results[node_id].data[param_key])
                
            return re.sub(pattern, replace, value)
            
        def process_value(value: Any) -> Any:
            """递归处理参数值"""
            if isinstance(value, str):
                # 处理完整的参数引用 (如 "$node1.param")
                if value.startswith("$") and "." in value and not " " in value:
                    ref_parts = value[1:].split(".")
                    ref_node = ref_parts[0]
                    ref_key = ref_parts[1]
                    if ref_node not in results:
                        raise ValueError(f"引用了未执行的节点: {ref_node}")
                    if not results[ref_node].data:
                        raise ValueError(f"节点 {ref_node} 没有返回数据")
                    if ref_key not in results[ref_node].data:
                        raise ValueError(f"节点 {ref_node} 的结果中不存在参数: {ref_key}")
                    return results[ref_node].data[ref_key]
                # 处理包含参数表达式的字符串
                elif "$" in value:
                    return replace_expression(value)
                return value
            elif isinstance(value, dict):
                return {k: process_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [process_value(item) for item in value]
            return value
            
        return {key: process_value(value) for key, value in params.items()}

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
            
        # 执行节点并处理中间结果
        final_result = None
        async for result in self.execute_node(node, processed_params, workflow_id):
            # 更新最新结果
            results[node_id] = result
            # 更新工作流进度
            self._workflow_progress[workflow_id] = results.copy()
            # 通知节点状态更新
            self._notify_node_completion(workflow_id, node_id, result)
            # 保存最终结果
            if result.status in [NodeStatus.COMPLETED, NodeStatus.FAILED]:
                final_result = result
        
        # 处理下游节点
        if final_result and final_result.success:
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

    async def _process_node_stream(
        self,
        node: Dict,
        workflow_id: str,
        dependencies: Dict[str, Set[str]],
        nodes: List[Dict],
        results: Dict[str, NodeResult]
    ) -> AsyncGenerator[Tuple[str, NodeResult], None]:
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
            
        # 执行节点并处理中间结果
        running_status_sent = False
        async for result in self.execute_node(node, processed_params, workflow_id):
            # 更新最新结果
            if result.status == NodeStatus.RUNNING:
                if not running_status_sent:
                    running_status_sent = True
                    results[node_id] = result
                    # 更新工作流进度
                    self._workflow_progress[workflow_id] = results.copy()
                    # 通知节点状态更新并返回结果
                    self._notify_node_completion(workflow_id, node_id, result)
                    yield node_id, result
                # 如果已经发送过 RUNNING 状态，只更新数据
                elif result.data:
                    results[node_id].data = result.data
            else:
                # 对于非 RUNNING 状态（COMPLETED/FAILED），正常处理
                results[node_id] = result
                # 更新工作流进度
                self._workflow_progress[workflow_id] = results.copy()
                # 通知节点状态更新并返回结果
                self._notify_node_completion(workflow_id, node_id, result)
                yield node_id, result
                
            # 如果节点执行完成且成功，处理下游节点
            if result.status == NodeStatus.COMPLETED and result.success:
                downstream_nodes = self._get_downstream_nodes(
                    node_id, nodes, dependencies, results
                )
                
                # 直接处理下游节点
                for n in downstream_nodes:
                    async for node_result in self._process_node_stream(
                        n, workflow_id, dependencies, nodes, results
                    ):
                        yield node_result

    async def execute_workflow_stream(
        self,
        workflow_json: str,
        workflow_id: str,
        global_params: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[Tuple[str, NodeResult], None]:
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
        self._workflow_progress[workflow_id] = {}
        results: Dict[str, NodeResult] = {}
        
        try:
            # 获取入口节点（没有入度的节点）
            entry_nodes = [
                node for node in nodes
                if not dependencies[node["id"]]
            ]
            
            # 处理入口节点
            for node in entry_nodes:
                # 创建异步生成器任务
                async for node_result in self._process_node_stream(
                    node,
                    workflow_id,
                    dependencies,
                    nodes,
                    results
                ):
                    yield node_result
                    
            # 检查是否所有节点都执行成功
            all_success = all(
                node["id"] in results and results[node["id"]].success
                for node in nodes
            )
            
            # 更新工作流最终状态
            self._workflow_status[workflow_id] = (
                WorkflowStatus.COMPLETED if all_success
                else WorkflowStatus.FAILED
            )
            
        except asyncio.CancelledError:
            self._workflow_status[workflow_id] = WorkflowStatus.CANCELLED
            raise
        except Exception as e:
            self._workflow_status[workflow_id] = WorkflowStatus.FAILED
            raise
        finally:
            if workflow_id in self._running_workflows:
                del self._running_workflows[workflow_id]

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
            Dict[str, NodeResult]: 所有节点的执行结果
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
        
        try:
            # 获取入口节点（没有入度的节点）
            entry_nodes = [
                node for node in nodes
                if not dependencies[node["id"]]
            ]
            
            # 创建入口节点的任务
            tasks = []
            for node in entry_nodes:
                task = asyncio.create_task(
                    self._process_node(
                        node,
                        workflow_id,
                        dependencies,
                        nodes,
                        results
                    )
                )
                tasks.append(task)
                
            # 等待所有任务完成
            await asyncio.gather(*tasks)
            
            # 检查是否所有节点都执行成功
            all_success = all(
                node_id in results and results[node_id].success
                for node in nodes
            )
            
            # 更新工作流最终状态
            self._workflow_status[workflow_id] = (
                WorkflowStatus.COMPLETED if all_success
                else WorkflowStatus.FAILED
            )
            
            return results
            
        except asyncio.CancelledError:
            self._workflow_status[workflow_id] = WorkflowStatus.CANCELLED
            raise
        except Exception as e:
            self._workflow_status[workflow_id] = WorkflowStatus.FAILED
            raise
        finally:
            if workflow_id in self._running_workflows:
                del self._running_workflows[workflow_id]
