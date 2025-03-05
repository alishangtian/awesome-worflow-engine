"""工作流服务模块"""

import json
import logging
from typing import Dict, Optional, AsyncGenerator
from ..core.engine import WorkflowEngine, NodeResult
from ..core.node_config import NodeConfigManager
from .llm_api import call_llm_api, call_llm_api_stream

# 配置日志记录
logger = logging.getLogger(__name__)

class WorkflowService:
    def __init__(self, engine: WorkflowEngine):
        self.engine = engine
        
    async def generate_workflow(self, text: str, request_id: str = None) -> Dict:
        """生成工作流JSON
        
        Args:
            text: 用户输入文本
            request_id: 请求ID用于日志追踪
            
        Returns:
            Dict: 工作流定义
        """
        node_manager = NodeConfigManager()
        node_descriptions = node_manager.get_nodes_description()
        nodes_json_example = node_manager.get_nodes_json_example()
        system_prompt = f"""你是一个工作流设计专家。根据用户问题设计工作流程。
        如果不需要工作流回答问题，返回空即可。
        
        可用节点类型：
        {node_descriptions}

        注意：
        1. 节点ID必须唯一
        2. 使用edges定义节点关系
        3. 可用 '$node_id.results' 方式引用其他节点输出结果的某些字段
        4. 注意数据类型匹配

        请输出JSON格式工作流，参考格式如下：
        
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
        self,
        original_text: str,
        workflow: Dict,
        results: Optional[Dict[str, NodeResult]],
        request_id: str = None
    ) -> AsyncGenerator[str, None]:
        """解释工作流执行结果（流式）
        
        Args:
            original_text: 用户原始输入
            workflow: 工作流定义
            results: 工作流执行结果
            request_id: 请求ID用于日志追踪
            
        Yields:
            str: 解释内容片段
        """
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
