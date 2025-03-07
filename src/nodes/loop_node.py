from typing import List, Dict, Any, Union
from .base import BaseNode
from ..core.models import NodeResult
import json

class LoopNode(BaseNode):
    def __init__(self):
        super().__init__()
        self._engine = None
        
    def init_engine(self, engine: Any):
        """初始化执行引擎,但不注册loop节点"""
        self._engine = engine
        
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        array = params.get("array", [])
        workflow_json = params.get("workflow_json")
        
        # 支持字符串、数字、对象或数组类型
        if not isinstance(array, list):
            if isinstance(array, (str, int, float, dict)):
                array = [array]
            else:
                raise ValueError("参数 'array' 必须是字符串、数字、对象或数组类型")
            
        if not isinstance(workflow_json, dict):
            raise ValueError("参数 'workflow_json' 必须是字典类型")
                
        results = []
        for index, item in enumerate(array):
            if index > 5:
                break
            # 创建循环项上下文，支持更丰富的引用方式
            loop_context = {
                "index": index,          # 当前索引，可通过 $index 引用
                "item": item,            # 当前项，可通过 $item 引用（如果是对象可以用 $item.field_name）
                "length": len(array),    # 总长度，可通过 $length 引用
                "first": index == 0,     # 是否第一项，可通过 $first 引用
                "last": index == len(array) - 1  # 是否最后一项，可通过 $last 引用
            }
            
            # 创建一个新的工作流ID
            workflow_id = f"loop_workflow_{id(item)}"
            
            # 合并全局上下文和循环项上下文
            workflow_context = {
                **loop_context
            }
            # 使用WorkflowEngine执行工作流，传递合并后的上下文
            result = await self._execute_workflow(
                workflow_json=workflow_json,
                workflow_id=workflow_id,
                context=workflow_context
            )
            # 将整个结果对象转换为JSON字符串
            for key, value in result.items():
                if isinstance (value, NodeResult):
                    results.append(value.to_data())
        return {
            "results": results,  # 包含所有JSON格式的结果
            "total": len(array),  # 保持数字类型
            "success": True  # 使用布尔类型
        }

    async def _execute_workflow(
        self,
        workflow_json: Dict[str, Any], 
        workflow_id: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        # 延迟导入 WorkflowEngine 以避免循环导入
        from ..core.engine import WorkflowEngine
        """
        执行工作流
        
        Args:
            workflow_json: 工作流定义
            workflow_id: 工作流ID
            context: 循环上下文变量
        """
        if not self._engine:
            raise ValueError("LoopNode未初始化执行引擎")
            
        # 创建一个新的执行引擎实例,复制原引擎的节点类型(除了loop节点)
        sub_engine = WorkflowEngine()
        for type_name, node_class in self._engine._node_types.items():
            if not isinstance(self, node_class):  # 不注册loop节点类型
                sub_engine.register_node_type(type_name, node_class)
                
        # 传递循环上下文，但不预处理workflow_json中的参数
        workflow_results = await sub_engine.execute_workflow(
            workflow_json=json.dumps(workflow_json),
            workflow_id=workflow_id,
            context=context
        )
        return workflow_results
