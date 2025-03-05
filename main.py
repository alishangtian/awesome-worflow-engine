"""API主模块"""

import logging
import os
import json
import importlib
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, Union, AsyncGenerator
from fastapi import FastAPI, HTTPException, Request, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from sse_starlette.sse import EventSourceResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from src.core.engine import WorkflowEngine, NodeResult
from src.core.node_config import NodeConfigManager
from src.api.workflow_service import WorkflowService
from src.api.stream_manager import StreamManager
from src.api.events import (
    create_status_event, create_workflow_event, create_result_event,
    create_explanation_event, create_answer_event, create_complete_event,
    create_error_event
)
from src.api.llm_api import call_llm_api_stream

# 配置日志记录
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# 创建全局实例
engine = WorkflowEngine()
workflow_service = WorkflowService(engine)
stream_manager = StreamManager()

# 注册节点状态回调
def node_status_callback(workflow_id: str, node_id: str, result: NodeResult):
    """处理节点状态变化的回调函数"""
    return {
        "node_id": node_id,
        "success": result.success,
        "status": result.status.value,
        "data": result.data if result.success else None,
        "error": result.error if not result.success else None
    }

engine.register_node_callback(node_status_callback)

# 在启动时注册所有节点类型
def register_all_nodes():
    """注册所有可用的节点类型"""
    node_manager = NodeConfigManager()
    node_configs = node_manager.node_configs
    
    for class_name in node_configs.keys():
        # 获取节点配置中定义的type
        node_type = node_configs[class_name].get('type')
        if not node_type:
            logger.warning(f"节点 {class_name} 未配置type字段，跳过注册")
            continue
            
        # 从type生成模块名
        module_name = node_type
        
        try:
            # 动态导入节点模块
            module = importlib.import_module(f"src.nodes.{module_name}")
            node_class = getattr(module, class_name)
            # 使用配置的type注册节点类型
            engine.register_node_type(node_type, node_class)
            logger.info(f"成功注册节点类型: {node_type}")
        except Exception as e:
            logger.error(f"注册节点类型 {module_name} 失败: {str(e)}")
            raise

# 在应用启动时注册所有节点
register_all_nodes()

app = FastAPI(
    title="Workflow Engine API",
    description="""
    基于DAG的工作流执行引擎API
    
    ## 功能特点
    - 支持多种节点类型：文本处理、数学运算、LLM对话等
    - 支持节点间数据流转
    - 支持自然语言输入自动生成工作流
    
    ## 使用示例
    
    ### 1. 执行简单的数学运算工作流
    ```json
    {
        "workflow": {
            "nodes": [
                {
                    "id": "add1",
                    "type": "add",
                    "params": {"num1": 10, "num2": 20}
                },
                {
                    "id": "multiply1",
                    "type": "multiply",
                    "params": {
                        "num1": "$add1.result",
                        "num2": 2
                    }
                }
            ],
            "edges": [
                {"from": "add1", "to": "multiply1"}
            ]
        }
    }
    ```
    
    ### 2. 使用自然语言接口
    发送请求：`"计算(10+20)*2"`
    系统会自动生成并执行上述工作流
    """,
    version="1.0.0"
)

# 挂载静态文件目录
static_path = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_path), name="static")

# 创建模板引擎
templates = Jinja2Templates(directory=static_path)

class ApiResponse(BaseModel):
    """统一的API响应模型"""
    event: str = Field(..., description="事件类型")
    success: bool = Field(..., description="操作是否成功")
    data: Optional[Union[Dict[str, Any], str, list]] = Field(None, description="响应数据")
    error: Optional[str] = Field(None, description="错误信息")

class WorkflowRequest(BaseModel):
    workflow: Dict[str, Any] = Field(
        ...,
        description="工作流定义，包含nodes和edges",
        example={
            "nodes": [
                {
                    "id": "add1",
                    "type": "add",
                    "params": {"num1": 10, "num2": 20}
                }
            ],
            "edges": []
        }
    )
    global_params: Optional[Dict[str, Any]] = Field(
        None,
        description="全局参数，可在所有节点中访问"
    )

class NodeResultResponse(BaseModel):
    success: bool = Field(..., description="节点执行是否成功")
    data: Optional[Dict[str, Any]] = Field(None, description="节点执行结果数据")
    error: Optional[str] = Field(None, description="错误信息（如果执行失败）")

@app.get("/health", response_model=ApiResponse)
async def health_check():
    """健康检查接口"""
    logger.debug("收到健康检查请求")
    return ApiResponse(
        event="health_check",
        success=True,
        data={"status": "healthy"}
    )

@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    """返回交互页面"""
    return templates.TemplateResponse("index.html", {"request": request})

class NaturalLanguageRequest(BaseModel):
    text: str

class NaturalLanguageResponse(BaseModel):
    type: str  # "workflow" or "answer"
    content: Union[str, Dict[str, Any]]

@app.post("/chat")
async def create_chat(text: str = Body(..., embed=True)):
    """创建新的聊天会话
    
    Args:
        text: 用户输入的文本
        
    Returns:
        dict: 包含chat_id的响应
    """
    chat_id = f"chat-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    stream_manager.create_stream(chat_id)
    
    # 启动异步任务处理用户请求
    asyncio.create_task(process_request(chat_id, text))
    
    return {
        "success": True,
        "chat_id": chat_id
    }

@app.get("/stream/{chat_id}")
async def stream_request(chat_id: str):
    """建立SSE连接获取响应流
    
    Args:
        chat_id: 聊天会话ID
        
    Returns:
        EventSourceResponse: SSE响应
    """
    async def event_generator():
        try:
            async for message in stream_manager.get_messages(chat_id):
                yield message
        except ValueError as e:
            yield await create_error_event(f"Stream not found: {str(e)}")
            
    return EventSourceResponse(event_generator())

async def process_request(chat_id: str, text: str):
    """处理用户请求的异步函数
    
    Args:
        chat_id: 聊天会话ID
        text: 用户输入的文本
    """
    logger.info(f"[{chat_id}] 开始处理请求: {text[:100]}...")
    try:
        # 开始生成工作流
        logger.info(f"[{chat_id}] 开始生成工作流")
        await stream_manager.send_message(chat_id, await create_status_event("generating", "正在生成工作流..."))
        workflow = await workflow_service.generate_workflow(text, chat_id)
        
        if not workflow or not workflow.get("nodes"):
            # 如果没有生成工作流，直接返回普通回答
            logger.info(f"[{chat_id}] 无工作流生成，转为生成普通回答")
            await stream_manager.send_message(chat_id, await create_status_event("answering", "正在生成回答..."))
            try:
                messages = [
                    {"role": "system", "content": "请根据用户问题提供简洁准确的回答。"},
                    {"role": "user", "content": text}
                ]
                async for chunk in call_llm_api_stream(messages, chat_id):
                    await stream_manager.send_message(chat_id, await create_answer_event({
                        "event": "answer",
                        "success": True,
                        "data": chunk
                    }))
                await stream_manager.send_message(chat_id, await create_complete_event())
            except Exception as e:
                logger.error(f"[{chat_id}] 生成回答时发生错误: {str(e)}", exc_info=True)
                await stream_manager.send_message(chat_id, await create_error_event("生成回答失败，请稍后重试"))
            return
            
        # 发送工作流定义
        logger.info(f"[{chat_id}] 工作流生成成功，节点数: {len(workflow.get('nodes', []))}")
        await stream_manager.send_message(chat_id, await create_workflow_event(workflow))
        await asyncio.sleep(0.1)  # 添加小延迟使前端显示更流畅
        
        # 开始执行工作流
        await stream_manager.send_message(chat_id, await create_status_event("executing", "正在执行工作流..."))
        workflow_id = f"workflow-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        try:
            logger.info(f"[{chat_id}] 开始执行工作流: {workflow_id}")
            # 使用流式执行工作流
            # 执行工作流并处理结果流
            # 使用流式执行并实时发送结果
            async for node_id, result in engine.execute_workflow_stream(
                json.dumps(workflow),
                workflow_id,
                {}
            ):
                logger.info(f"[{chat_id}] 节点 {node_id} 执行状态: status={result.status} 执行结果：success={result.success}")
                # 将NodeResult对象转换为字典格式并立即发送
                result_dict = {
                    "node_id": node_id,
                    "success": result.success,
                    "status": result.status.value,
                    "data": result.data if result.success else None,
                    "error": result.error if not result.success else None
                }
                # 立即发送节点状态更新
                event = await create_result_event(node_id, result_dict)
                await stream_manager.send_message(chat_id, event)
                # 添加小延迟确保前端能够正确接收和处理事件
                await asyncio.sleep(0.01)
            
            # 获取工作流执行结果并生成说明
            logger.info(f"[{chat_id}] 开始生成执行说明")
            workflow_results = engine.get_workflow_progress(workflow_id)
            async for chunk in workflow_service.explain_workflow_result(text, workflow, workflow_results, chat_id):
                await stream_manager.send_message(chat_id, await create_explanation_event({
                    "event": "explanation",
                    "success": True,
                    "data": chunk
                }))
            await stream_manager.send_message(chat_id, await create_complete_event())
            logger.info(f"[{chat_id}] 工作流执行完成")
            
        except Exception as e:
            error_msg = f"执行工作流失败: {str(e)}"
            logger.error(f"[{chat_id}] {error_msg}", exc_info=True)
            await stream_manager.send_message(chat_id, await create_error_event(error_msg))
            
    except Exception as e:
        error_msg = f"处理请求失败: {str(e)}"
        logger.error(f"[{chat_id}] {error_msg}", exc_info=True)
        await stream_manager.send_message(chat_id, await create_error_event(error_msg))

@app.post("/execute_workflow", response_model=ApiResponse)
async def execute_workflow(request: WorkflowRequest):
    """
    执行工作流
    
    根据提供的工作流定义执行工作流，返回统一的事件格式
    
    Args:
        request: 包含工作流定义的请求
        
    Returns:
        ApiResponse: 包含工作流执行结果的统一响应
    """
    request_id = f"req-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    logger.info(f"[{request_id}] 收到执行工作流请求")
    try:
        workflow_id = f"workflow-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # 记录工作流定义
        workflow_json = json.dumps(request.workflow, indent=2)
        logger.info(f"[{request_id}] 工作流定义:\n{workflow_json}")
        
        # 发送工作流事件
        workflow_event = await create_workflow_event(request.workflow)
        
        # 使用流式执行工作流
        events = []
        async for node_id, result in engine.execute_workflow_stream(
            json.dumps(request.workflow),
            workflow_id,
            request.global_params or {}
        ):
            # 将NodeResult对象转换为字典格式
            result_dict = {
                "node_id": node_id,
                "success": result.success,
                "status": result.status.value,
                "data": result.data if result.success else None,
                "error": result.error if not result.success else None
            }
            node_event = await create_result_event(node_id, result_dict)
            events.append(node_event)
            
        # 生成完成事件
        complete_event = await create_complete_event()
        events.append(complete_event)
        
        logger.info(f"[{request_id}] 工作流执行完成")
        return ApiResponse(
            event="workflow_execution",
            success=True,
            data={
                "workflow": workflow_event["data"],
                "events": [event["data"] for event in events]
            }
        )
    except Exception as e:
        error_msg = f"执行工作流失败: {str(e)}"
        logger.error(f"[{request_id}] {error_msg}", exc_info=True)
        return ApiResponse(
            event="workflow_execution",
            success=False,
            error=error_msg
        )
