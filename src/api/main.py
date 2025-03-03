"""API主模块"""

import logging
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.openapi.utils import get_openapi
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from sse_starlette.sse import EventSourceResponse
from fastapi.templating import Jinja2Templates
import os
import asyncio
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, Union, List, AsyncGenerator, Any
import json

from src.core.engine import WorkflowEngine, NodeResult
import importlib
from src.core.node_config import NodeConfigManager
from src.api.config import API_CONFIG, retry_on_error
import aiohttp

# 配置日志记录
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# 创建全局WorkflowEngine实例
engine = WorkflowEngine()

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
static_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "static")
app.mount("/static", StaticFiles(directory=static_path), name="static")

# 创建模板引擎
templates = Jinja2Templates(directory=static_path)

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

@app.get("/health")
async def health_check():
    """健康检查接口"""
    logger.debug("收到健康检查请求")
    return {"status": "healthy"}

@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    """返回交互页面"""
    return templates.TemplateResponse("index.html", {"request": request})

class NaturalLanguageRequest(BaseModel):
    text: str

class NaturalLanguageResponse(BaseModel):
    type: str  # "workflow" or "answer"
    content: Union[str, Dict[str, Any]]

class ProcessResponse(BaseModel):
    workflow: Optional[Dict[str, Any]]
    results: Optional[Dict[str, Any]]
    explanation: Optional[str]
    answer: Optional[str]

async def call_llm_api_stream(messages: List[Dict[str, str]], request_id: str = None) -> AsyncGenerator[str, None]:
    """
    调用llm API服务(流式),支持自动重试
    
    Args:
        messages: 消息列表
        request_id: 请求ID,用于日志追踪
    
    Returns:
        异步生成器,生成流式响应内容
    """
    if request_id:
        logger.info(f"[{request_id}] 开始流式调用llm API")
        
    async with aiohttp.ClientSession() as session:
        headers = {
            "Authorization": f"Bearer {API_CONFIG['api_key']}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": API_CONFIG["model_name"],
            "messages": messages,
            "stream": True
        }
        
        try:
            async with session.post(
                f"{API_CONFIG['base_url']}/chat/completions",
                headers=headers,
                json=data,
                timeout=30
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    if request_id:
                        logger.error(f"[{request_id}] API调用失败: {error_text}")
                    raise ValueError(f"API调用失败: {error_text}")
                
                async for line in response.content:
                    if line:
                        try:
                            line = line.decode('utf-8').strip()
                            if line.startswith('data: ') and line != 'data: [DONE]':
                                json_str = line[6:]  # 去掉 "data: "
                                data = json.loads(json_str)
                                if len(data['choices']) > 0:
                                    delta = data['choices'][0].get('delta', {})
                                    if 'content' in delta:
                                        yield await create_explanation_event(delta['content'])
                        except Exception as e:
                            logger.error(f"[{request_id}] 处理流式响应出错: {str(e)}")
                
        except asyncio.TimeoutError:
            error_msg = "API调用超时"
            if request_id:
                logger.error(f"[{request_id}] {error_msg}")
            raise ValueError(error_msg)
        except Exception as e:
            if request_id:
                logger.error(f"[{request_id}] API调用异常: {str(e)}")
            raise
        
async def call_llm_api(
    messages: List[Dict[str, str]],
    request_id: str = None,
    stream: bool = False
) -> Union[str, AsyncGenerator[str, None]]:
    """
    调用llm API服务，支持自动重试
    
    Args:
        messages: 消息列表
        request_id: 请求ID,用于日志追踪
        stream: 是否使用流式响应,默认False
    
    Returns:
        如果stream=False,返回完整响应字符串
        如果stream=True,返回异步生成器,生成流式响应内容
    """
    if stream:
        return _call_llm_api_stream(messages, request_id)
    else:
        return await _call_llm_api_non_stream(messages, request_id)

async def _call_llm_api_stream(
    messages: List[Dict[str, str]],
    request_id: str = None
) -> AsyncGenerator[str, None]:
    """处理流式响应"""
    if request_id:
        logger.info(f"[{request_id}] 开始流式调用llm API")
        
    async for chunk in call_llm_api_stream(messages, request_id):
        yield await create_explanation_event(chunk)

async def _call_llm_api_non_stream(
    messages: List[Dict[str, str]],
    request_id: str = None
) -> str:
    """处理非流式响应"""
    if request_id:
        logger.info(f"[{request_id}] 开始调用llm API")
        
    async with aiohttp.ClientSession() as session:
        headers = {
            "Authorization": f"Bearer {API_CONFIG['api_key']}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": API_CONFIG["model_name"],
            "messages": messages,
            "stream": False
        }
        
        try:
            async with session.post(
                f"{API_CONFIG['base_url']}/chat/completions",
                headers=headers,
                json=data,
                timeout=30
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    if request_id:
                        logger.error(f"[{request_id}] API调用失败: {error_text}")
                    raise ValueError(f"API调用失败: {error_text}")
                
                result = await response.json()
                if request_id:
                    logger.info(f"[{request_id}] API调用成功")
                return result["choices"][0]["message"]["content"]
                
        except asyncio.TimeoutError:
            error_msg = "API调用超时"
            if request_id:
                logger.error(f"[{request_id}] {error_msg}")
            raise ValueError(error_msg)
        except Exception as e:
            if request_id:
                logger.error(f"[{request_id}] API调用异常: {str(e)}")
            raise

@retry_on_error(max_retries=3)
async def call_llm_api(messages: List[Dict[str, str]], request_id: str = None) -> str:
    """
    调用llm API服务，支持自动重试
    
    Args:
        messages: 消息列表
        request_id: 请求ID,用于日志追踪
    
    Returns:
        返回完整响应字符串
    """
    if request_id:
        logger.info(f"[{request_id}] 开始调用llm API")
        
    async with aiohttp.ClientSession() as session:
        headers = {
            "Authorization": f"Bearer {API_CONFIG['api_key']}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": API_CONFIG["model_name"],
            "messages": messages,
            "stream": False
        }
        
        try:
            async with session.post(
                f"{API_CONFIG['base_url']}/chat/completions",
                headers=headers,
                json=data,
                timeout=30
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    if request_id:
                        logger.error(f"[{request_id}] API调用失败: {error_text}")
                    raise ValueError(f"API调用失败: {error_text}")
                
                result = await response.json()
                if request_id:
                    logger.info(f"[{request_id}] API调用成功")
                return result["choices"][0]["message"]["content"]
                
        except asyncio.TimeoutError:
            error_msg = "API调用超时"
            if request_id:
                logger.error(f"[{request_id}] {error_msg}")
            raise ValueError(error_msg)
        except Exception as e:
            if request_id:
                logger.error(f"[{request_id}] API调用异常: {str(e)}")
            raise

async def generate_workflow(text: str, request_id: str = None) -> Dict:
    """生成工作流JSON"""
    from src.core.node_config import NodeConfigManager
    node_manager = NodeConfigManager()
    node_descriptions = node_manager.get_nodes_description()
    nodes_json_example = node_manager.get_nodes_json_example()
    system_prompt = f"""你是一个工作流设计专家。根据用户问题设计工作流程。
    如果不需要工作流回答问题，返回空即可。
    
    可用节点类型：
    {node_descriptions}

    注意：
    1. 节点ID必须唯一
    2. 使用edges定义数据流转
    3. 可用$node_id.result引用其他节点输出
    4. 注意数据类型匹配

    请输出JSON格式工作流：
    {nodes_json_example}
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": text}
    ]
    
    workflow_str = await call_llm_api(messages, request_id)
    try:
        if "```json" in workflow_str:
            workflow_str = workflow_str.split("```json")[1].split("```")[0]
        return json.loads(workflow_str)
    except:
        return {"nodes": [], "edges": []}

async def explain_workflow_result(
    original_text: str,
    workflow: Dict,
    results: Optional[Dict[str, NodeResult]],
    request_id: str = None
) -> AsyncGenerator[str, None]:
    """解释工作流执行结果（流式）"""
    workflow_desc = []
    
    if not results:
        yield "工作流执行失败，未能获取执行结果。"
        return
        
    for node in workflow["nodes"]:
        node_id = node["id"]
        node_type = node["type"]
        node_result = results.get(node_id)
        
        if node_result and node_result.success:
            result_data = node_result.data
            workflow_desc.append(f"- {node_type}({node_id}): 成功，输出={result_data}")
        else:
            error = node_result.error if node_result else "未执行"
            workflow_desc.append(f"- {node_type}({node_id}): 失败，错误={error}")
    
    workflow_status = "\n".join(workflow_desc)
    
    messages = [
        {"role": "system", "content": "分析工作流执行结果，简要说明执行过程和最终结果。"},
        {"role": "user", "content": f"用户输入: {original_text}\n执行情况:\n{workflow_status}"}
    ]
    
    async for chunk in call_llm_api_stream(messages, request_id):
        yield chunk

class ProcessRequest(BaseModel):
    text: str = Field(..., description="用户输入的文本")

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

async def create_result_event(node_id: str, result: Any) -> Dict:
    """创建节点结果事件"""
    return await create_event(EventType.NODE_RESULT, {
        **result,
        "node_id": node_id
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

@app.get("/stream")
async def stream_request(request: Request, text: str):
    """
    流式处理用户请求
    
    将自然语言输入转换为工作流执行或直接生成回答，以SSE方式流式返回结果
    
    Args:
        request: FastAPI请求对象
        text: 用户输入的文本
        
    Returns:
        EventSourceResponse: SSE响应
    """
    request_id = f"req-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    logger.info(f"[{request_id}] 收到流式处理请求: {text[:100]}...")
    
    async def event_generator():
        try:
            # 开始生成工作流
            logger.info(f"[{request_id}] 开始生成工作流")
            yield await create_status_event("generating", "正在生成工作流...")
            workflow = await generate_workflow(text, request_id)
            
            if not workflow or not workflow.get("nodes"):
                # 如果没有生成工作流，直接返回普通回答
                logger.info(f"[{request_id}] 无工作流生成，转为生成普通回答")
                yield await create_status_event("answering", "正在生成回答...")
                try:
                    messages = [
                        {"role": "system", "content": "请根据用户问题提供简洁准确的回答。"},
                        {"role": "user", "content": text}
                    ]
                    async for chunk in call_llm_api_stream(messages, request_id):
                        yield await create_answer_event(chunk)
                    yield await create_complete_event()
                except Exception as e:
                    logger.error(f"[{request_id}] 生成回答时发生错误: {str(e)}", exc_info=True)
                    yield await create_error_event("生成回答失败，请稍后重试")
                return
                
            # 发送工作流定义
            logger.info(f"[{request_id}] 工作流生成成功，节点数: {len(workflow.get('nodes', []))}")
            yield await create_workflow_event(workflow)
            await asyncio.sleep(0.1)  # 添加小延迟使前端显示更流畅
            
            # 开始执行工作流
            yield await create_status_event("executing", "正在执行工作流...")
            workflow_id = f"workflow-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            try:
                logger.info(f"[{request_id}] 开始执行工作流: {workflow_id}")
                # 使用流式执行工作流
                async for node_id, result in engine.execute_workflow_stream(
                    json.dumps(workflow),
                    workflow_id,
                    {}
                ):
                    logger.info(f"[{request_id}] 节点 {node_id} 执行完成: success={result.success}")
                    yield await create_result_event(
                        node_id,
                        {
                            "node_id": node_id,
                            "success": result.success,
                            "data": result.data if result.success else None,
                            "error": result.error if not result.success else None
                        }
                    )
                
                # 获取工作流执行结果并生成说明
                logger.info(f"[{request_id}] 开始生成执行说明")
                workflow_results = engine.get_workflow_progress(workflow_id)
                async for chunk in explain_workflow_result(text, workflow, workflow_results, request_id):
                    yield await create_explanation_event(chunk)
                yield await create_complete_event()
                logger.info(f"[{request_id}] 工作流执行完成")
                
            except Exception as e:
                error_msg = f"执行工作流失败: {str(e)}"
                logger.error(f"[{request_id}] {error_msg}", exc_info=True)
                yield await create_error_event(error_msg)
                
        except Exception as e:
            error_msg = f"处理请求失败: {str(e)}"
            logger.error(f"[{request_id}] {error_msg}", exc_info=True)
            yield await create_error_event(error_msg)
    
    return EventSourceResponse(event_generator())

@app.post("/execute_workflow")
async def execute_workflow(request: WorkflowRequest):
    """
    执行工作流
    
    根据提供的工作流定义执行工作流，返回统一的事件格式
    
    Args:
        request: 包含工作流定义的请求
        
    Returns:
        Dict: 包含工作流执行结果的事件
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
        
        # 执行工作流
        results = await engine.execute_workflow(
            json.dumps(request.workflow),
            workflow_id, 
            request.global_params or {}
        )
        
        # 转换结果格式并生成节点结果事件
        events = []
        for node_id, result in results.items():
            node_event = await create_result_event(
                node_id,
                {
                    "node_id": node_id,
                    "success": result.success,
                    "data": result.data if result.success else None,
                    "error": result.error if not result.success else None
                }
            )
            events.append(node_event)
        
        # 生成完成事件
        complete_event = await create_complete_event()
        events.append(complete_event)
        
        logger.info(f"[{request_id}] 工作流执行完成")
        return {
            "workflow": workflow_event["data"],
            "events": [event["data"] for event in events]
        }
    except Exception as e:
        logger.error(f"[{request_id}] 执行工作流时发生错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"执行工作流失败: {str(e)}")
