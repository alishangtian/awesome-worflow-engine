"""事件生成模块"""

import json
import time
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
    ACTION_START = "action_start"
    ACTION_END = "action_end"
    ACTION_ERROR = "action_error"
    ACTION_COMPLETE = "action_complete"
    TOOL_PROGRESS = "tool_progress"  # 工具执行进度事件
    TOOL_RETRY = "tool_retry"  # 工具重试事件
    AGENT_START = "agent_start"  # agent开始执行事件
    AGENT_COMPLETE = "agent_complete"  # agent执行完成事件
    AGENT_ERROR = "agent_error"  # agent执行错误事件
    AGENT_THINKING = "agent_thinking"  # agent思考事件

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

async def create_action_start_event(action: str, action_input: Any) -> Dict:
    """创建动作开始事件"""
    return await create_event(EventType.ACTION_START, {
        "action": action,
        "input": action_input,
        "timestamp": time.time()
    })

async def create_action_complete_event(action: str, result: Any) -> Dict:
    """创建动作完成事件"""
    return await create_event(EventType.ACTION_COMPLETE, {
        "action": action,
        "result": result,
        "timestamp": time.time()
    })

async def create_tool_progress_event(tool: str, status: str, result: Any) -> Dict:
    """创建工具进度事件"""
    return await create_event(EventType.TOOL_PROGRESS, {
        "tool": tool,
        "status": status,
        "result": str(result),
        "timestamp": time.time()
    })

async def create_tool_retry_event(tool: str, attempt: int, max_retries: int, error: str) -> Dict:
    """创建工具重试事件"""
    return await create_event(EventType.TOOL_RETRY, {
        "tool": tool,
        "attempt": attempt,
        "max_retries": max_retries,
        "error": error,
        "timestamp": time.time()
    })

async def create_agent_start_event(query: str) -> Dict:
    """创建agent开始事件"""
    return await create_event(EventType.AGENT_START, {
        "query": query,
        "timestamp": time.time()
    })

async def create_agent_complete_event(result: str) -> Dict:
    """创建agent完成事件"""
    return await create_event(EventType.AGENT_COMPLETE, {
        "result": result,
        "timestamp": time.time()
    })

async def create_agent_error_event(error: str) -> Dict:
    """创建agent错误事件"""
    return await create_event(EventType.AGENT_ERROR, {
        "error": error,
        "timestamp": time.time()
    })

async def create_agent_thinking_event(thought: str) -> Dict:
    """创建agent思考事件"""
    return await create_event(EventType.AGENT_THINKING, {
        "thought": thought,
        "timestamp": time.time()
    })
