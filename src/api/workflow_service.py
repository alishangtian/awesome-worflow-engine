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
        inference_format = '${node_id.results}'
        
        # 系统角色定义
        system_prompt = f"""# 角色定义
你是一个专业的工作流设计专家，擅长：
1. 分析用户需求并将其转化为结构化的工作流程
2. 设计高效且可维护的工作流节点关系
3. 确保工作流的正确性和数据流转的合理性

# 技术要求
1. 节点ID必须唯一，建议使用描述性ID（如 extract_keywords, analyze_sentiment）
2. 使用edges数组准确定义节点间的连接关系
3. 使用 '{inference_format}' 格式引用上游节点的输出字段
4. 仔细检查每个节点的输入输出数据类型是否匹配
5. 确保工作流是一个有向无环图（DAG）

# 可用节点类型和说明
{node_descriptions}"""

        # 用户任务指导
        user_prompt = f"""请根据我的问题设计一个工作流程。如果问题不需要工作流处理，请返回空的nodes和edges数组。

# 设计步骤
1. 理解需求：
   - 分析我的问题的核心目标
   - 确定是否需要工作流来处理

2. 工作流设计（如果需要）：
   - 将问题拆分为具体的处理步骤
   - 为每个步骤选择合适的节点类型
   - 设计节点之间的数据流转
   - 配置每个节点的具体参数

# 输出格式
请使用以下JSON格式输出工作流定义：

{nodes_json_example}"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt + "\n\n问题：" + text}
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
            {"role": "system", "content": f"你是一位专业的全面的问题专家。请参考context回答用户问题，切记：回答内容不要提及你参考了什么信息 \n\n context：\n {workflow_status}"},
            {"role": "user", "content": f"{original_text}"}
        ]
        
        async for chunk in call_llm_api_stream(messages, request_id):
            yield chunk
