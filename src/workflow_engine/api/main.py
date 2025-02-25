"""API主模块"""

import logging
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, Union, List
import json

from ..core.engine import WorkflowEngine, NodeResult
import importlib
from ..core.node_config import NodeConfigManager
from .config import API_CONFIG, retry_on_error
import aiohttp

# 配置日志记录
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

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

@app.post("/execute", response_model=Dict[str, NodeResultResponse])
async def execute_workflow(request: WorkflowRequest):
    """
    执行工作流
    
    Args:
        request: 包含工作流定义和全局参数的请求体
        
    Returns:
        Dict[str, NodeResultResponse]: 工作流执行结果
    """
    logger.info(f"收到工作流执行请求: {len(request.workflow.get('nodes', []))} 个节点")
    try:
        start_time = datetime.now()
        logger.info("开始创建工作流引擎实例")
        engine = WorkflowEngine()
        
        # 从配置中获取并注册节点类型
        node_manager = NodeConfigManager()
        node_configs = node_manager.node_configs
        
        # 动态导入并注册节点
        for class_name in node_configs.keys():
            # 获取节点配置中定义的type
            node_type = node_configs[class_name].get('type')
            if not node_type:
                logger.warning(f"节点 {class_name} 未配置type字段，跳过注册")
                continue
                
            # 从type生成模块名，例如：text_concat -> text_concat
            module_name = node_type
            
            try:
                # 动态导入节点模块
                module = importlib.import_module(f"..nodes.{module_name}", package="workflow_engine.api")
                node_class = getattr(module, class_name)
                # 使用配置的type注册节点类型
                engine.register_node_type(node_type, node_class)
                logger.info(f"成功注册节点类型: {node_type}")
            except Exception as e:
                logger.error(f"注册节点类型 {module_name} 失败: {str(e)}")
                raise
        
        # 执行工作流
        logger.info("开始执行工作流")
        workflow_json = json.dumps(request.workflow, indent=2)
        logger.info(f"工作流内容:\n{workflow_json}")
        results = await engine.execute_workflow(
            workflow_json,
            global_params=request.global_params
        )
        logger.info(f"工作流执行结果:\n{json.dumps(results, indent=2, default=str)}")
        execution_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"工作流执行完成，耗时: {execution_time:.2f}秒")
        
        # 转换结果为API响应格式
        response = {}
        for node_id, result in results.items():
            response[node_id] = NodeResultResponse(
                success=result.success,
                data=result.data if result.success else None,
                error=result.error if not result.success else None
            )
            
        return response
        
    except Exception as e:
        logger.error(f"工作流执行失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"工作流执行失败: {str(e)}"
        )

@app.get("/health")
async def health_check():
    """健康检查接口"""
    logger.debug("收到健康检查请求")
    return {"status": "healthy"}

class NaturalLanguageRequest(BaseModel):
    text: str

class NaturalLanguageResponse(BaseModel):
    type: str  # "workflow" or "answer"
    content: Union[str, Dict[str, Any]]

@retry_on_error(max_retries=3)
async def call_360_api(messages: List[Dict[str, str]]) -> str:
    """调用360 API服务"""
    logger.info("准备调用360 API")
    logger.info(f"请求消息:\n{json.dumps(messages, indent=2, ensure_ascii=False)}")
    async with aiohttp.ClientSession() as session:
        headers = {
            "Authorization": f"Bearer {API_CONFIG['api_key']}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": API_CONFIG["model_name"],
            "messages": messages
        }
        
        async with session.post(
            f"{API_CONFIG['base_url']}/chat/completions",
            headers=headers,
            json=data
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                logger.error(f"360 API调用失败: 状态码={response.status}, 错误信息={error_text}")
                raise ValueError(f"API调用失败 (状态码: {response.status}): {error_text}")
            
            logger.info("360 API调用成功")
            
            result = await response.json()
            return result["choices"][0]["message"]["content"]

@retry_on_error(max_retries=3)
async def generate_workflow(text: str) -> Dict:
    """生成工作流JSON"""
    logger.info(f"开始生成工作流，输入文本: {text[:100]}...")
    # 获取节点描述
    from ..core.node_config import NodeConfigManager
    node_manager = NodeConfigManager()
    node_descriptions = node_manager.get_nodes_description()
    nodes_json_example = node_manager.get_nodes_json_example()
    system_prompt = f"""你是一个专业的工作流设计专家。你需要根据用户的问题，
                        设计出最合适的工作流程，如果不需要工作流来回答用户问题，请返回空即可。

                        可用的节点类型：

                        {node_descriptions}

                        注意事项：
                        1. 每个节点必须有唯一的id
                        2. 使用edges定义节点间的数据流转
                        3. 可以使用$node_id.result引用其他节点的输出
                        4. 设计工作流时要考虑数据类型的匹配

                        请输出标准的JSON格式工作流，不需要其他任何信息：
                        如下就是一个合格的工作流json数据：
                        {nodes_json_example}
                        """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": text}
    ]
    workflow_str = await call_360_api(messages)
    # 提取JSON字符串（可能包含在```json ```中）
    if "```json" in workflow_str:
        workflow_str = workflow_str.split("```json")[1].split("```")[0]
    return json.loads(workflow_str)

@retry_on_error(max_retries=3)
async def explain_workflow_result(
    original_text: str,
    workflow: Dict,
    results: Dict[str, NodeResult]
) -> str:
    """解释工作流执行结果"""
    # 构建工作流执行情况的描述
    workflow_desc = []
    for node in workflow["nodes"]:
        node_id = node["id"]
        node_type = node["type"]
        node_result = results.get(node_id)
        
        if node_result and node_result.success:
            result_data = node_result.data.get("result", "无输出") if node_result.data else "无输出"
            workflow_desc.append(f"- {node_type}节点({node_id})执行成功，输出: {result_data}")
        else:
            error = node_result.error if node_result else "未执行"
            workflow_desc.append(f"- {node_type}节点({node_id})执行失败: {error}")
    
    workflow_status = "\n".join(workflow_desc)
    
    messages = [
        {"role": "system", "content": """你是一个工作流执行结果分析专家。
请按照以下格式输出工作流执行情况：

执行步骤：
1. [步骤1描述及结果]
2. [步骤2描述及结果]
...

最终结果：[输出最终的执行结果]

如果执行过程中出现错误，请在相应步骤中标注。"""},
        {"role": "user", "content": f"""
用户输入: {original_text}

工作流执行情况:
{workflow_status}

请解释这个工作流的执行过程和结果。"""}
    ]
    return await call_360_api(messages)

@retry_on_error(max_retries=3)
async def generate_answer(text: str) -> str:
    """生成普通回答"""
    messages = [
        {"role": "system", "content": """你是一个专业的AI助手。
请根据用户的问题提供准确、有帮助的回答。
如果问题涉及到复杂的计算或多步骤处理，建议使用工作流来处理。"""},
        {"role": "user", "content": text}
    ]
    return await call_360_api(messages)

@app.post("/natural_language", response_model=NaturalLanguageResponse)
async def process_natural_language(request: NaturalLanguageRequest):
    """
    处理自然语言输入
    
    将自然语言输入转换为工作流执行或直接生成回答
    
    Args:
        request: 包含自然语言文本的请求
        
    Returns:
        NaturalLanguageResponse: 包含执行结果的响应
        
    Examples:
        计算示例：
        ```
        POST /natural_language
        {
            "text": "计算(10+20)*2"
        }
        ```
        
        文本处理示例：
        ```
        POST /natural_language
        {
            "text": "将文本'Hello'和'World'用空格连接，然后把'World'替换成'Python'"
        }
        ```
        
        对话示例：
        ```
        POST /natural_language
        {
            "text": "用更专业的语言重写这句话：AI很有用"
        }
        ```
    """
    logger.info(f"收到自然语言处理请求: {request.text[:100]}...")
    try:
        start_time = datetime.now()
        # 生成工作流
        workflow = await generate_workflow(request.text)
        logger.info(f"工作流生成完成，包含 {len(workflow.get('nodes', []))} 个节点")
        # 如果生成的工作流包含节点，说明需要工作流处理
        if workflow and workflow.get("nodes") and len(workflow["nodes"]) > 0:
            engine = WorkflowEngine()
            
            # 从配置中获取并注册节点类型
            node_manager = NodeConfigManager()
            node_configs = node_manager.node_configs
            
            # 动态导入并注册节点
            for class_name in node_configs.keys():
                # 获取节点配置中定义的type
                node_type = node_configs[class_name].get('type')
                if not node_type:
                    logger.warning(f"节点 {class_name} 未配置type字段，跳过注册")
                    continue
                    
                # 从type生成模块名，例如：text_concat -> text_concat
                module_name = node_type
                
                try:
                    # 动态导入节点模块
                    module = importlib.import_module(f"..nodes.{module_name}", package="workflow_engine.api")
                    node_class = getattr(module, class_name)
                    # 使用配置的type注册节点类型
                    engine.register_node_type(node_type, node_class)
                    logger.info(f"成功注册节点类型: {node_type}")
                except Exception as e:
                    logger.error(f"注册节点类型 {module_name} 失败: {str(e)}")
                    raise
            
            # 执行工作流
            logger.info("开始执行自然语言生成的工作流")
            workflow_json = json.dumps(workflow, indent=2)
            logger.info(f"生成的工作流内容:\n{workflow_json}")
            workflow_id = f"workflow-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            results = await engine.execute_workflow(
                workflow_json,workflow_id=workflow_id
            )
            logger.info(f"工作流执行结果:\n{json.dumps(results, indent=2, default=str)}")
            logger.info("工作流执行完成")
            
            # 生成工作流执行结果的解释
            explanation = await explain_workflow_result(
                request.text,
                workflow,
                results
            )
            
            return NaturalLanguageResponse(
                type="workflow",
                content=explanation
            )
        else:
            # 生成普通回答
            answer = await generate_answer(request.text)
            return NaturalLanguageResponse(
                type="answer",
                content=answer
            )
    except Exception as e:
        logger.error(f"自然语言处理失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"处理失败: {str(e)}"
        )
    finally:
        execution_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"自然语言处理完成，总耗时: {execution_time:.2f}秒")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
