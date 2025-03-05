"""事件生成模块"""

import json
from typing import Any, Dict

class EventType:
    """事件类型枚举"""
    STATUS = "status"
    WORKFLOW = "workflow" 
    NODE_RESULT = "node_result"
    EXPLANATION = "explanation"
    ANSWER = "answer"
    COMPLETE = "complete"
    ERROR = "error"

async def create_event(event_type: str, data: Any) -> Dict:
    """统一的事件创建函数
    
    Args:
        event_type: 事件类型
        data: 事件数据
        
    Returns:
        Dict: 包含event和data的事件字典
    """
    # 如果data已经是字符串，不需要额外处理
    if isinstance(data, str):
        return {
            "event": event_type,
            "data": data
        }
    # 如果data是字典或其他类型，转换为JSON字符串
    return {
        "event": event_type,
        "data": json.dumps(data, ensure_ascii=False)
    }

async def create_status_event(status: str, message: str) -> Dict:
    """创建状态事件"""
    return await create_event(EventType.STATUS, message)

async def create_workflow_event(workflow: Dict) -> Dict:
    """创建工作流事件"""
    return await create_event(EventType.WORKFLOW, workflow)

async def create_result_event(node_id: str, result: Dict[str, Any]) -> Dict:
    """创建节点结果事件
    
    Args:
        node_id: 节点ID
        result: 节点执行结果字典，包含success、status、data、error等字段
        
    Returns:
        Dict: 事件字典
    """
    # 确保result是字典类型
    if not isinstance(result, dict):
        raise TypeError("Result must be a dictionary")
        
    return await create_event(EventType.NODE_RESULT, {
        **result,
        "node_id": node_id  # 确保node_id存在于结果中
    })

async def create_explanation_event(content: str) -> Dict:
    """创建解释说明事件"""
    return await create_event(EventType.EXPLANATION, content)

async def create_answer_event(content: str) -> Dict:
    """创建回答事件"""
    return await create_event(EventType.ANSWER, content)

async def create_complete_event() -> Dict:
    """创建完成事件"""
    return await create_event(EventType.COMPLETE, "执行完成")

async def create_error_event(error_message: str) -> Dict:
    """创建错误事件"""
    return await create_event(EventType.ERROR, error_message)
