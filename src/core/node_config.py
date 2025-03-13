"""节点配置管理模块"""
 
import yaml
import os
import json
import logging
from typing import Dict, Optional, List, Type
from ..agent.agent import Tool
from ..nodes.base import BaseNode
from ..core.engine import WorkflowEngine

logger = logging.getLogger(__name__)

class NodeConfigManager:
    """节点配置管理类"""
    
    def __init__(self, config_path: str = None, engine: WorkflowEngine = None):
        """
        初始化节点配置管理器
        
        Args:
            config_path: 配置文件路径，如果为None则使用默认路径
        """
        if config_path is None:
            # 使用默认配置文件路径
            current_dir = os.path.dirname(os.path.abspath(__file__))
            # 首先尝试从nodes目录加载配置
            nodes_config_path = os.path.join(current_dir, "../nodes/node_config.yaml")
            if os.path.exists(nodes_config_path):
                config_path = nodes_config_path
            else:
                # 如果nodes目录下没有配置文件，则使用原来的配置路径
                config_path = os.path.join(current_dir, "../config/node_config.yaml")
        
        self.config_path = config_path
        self.node_configs = self._load_config()
        self._node_types: Dict[str, Type[BaseNode]] = {}
        self.engine = engine
    
    def _load_config(self) -> Dict:
        """加载节点配置"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f)
            return {}
        except Exception as e:
            print(f"加载节点配置失败: {str(e)}")
            return {}
    
    def get_node_info(self, node_type: str) -> Optional[Dict]:
        """
        获取节点配置信息
        
        Args:
            node_type: 节点类型
            
        Returns:
            节点配置信息，如果节点不存在则返回None
        """
        # 遍历配置查找匹配的节点类型
        for config in self.node_configs.values():
            if isinstance(config, dict) and config.get("type") == node_type:
                return config
        return None
 
    def get_all_nodes(self) -> List[Dict]:
        """
        获取所有节点的配置信息
        
        Returns:
            所有节点的配置信息列表
        """
        nodes = []
        for class_name, config in self.node_configs.items():
            # 确保配置是字典类型
            if not isinstance(config, dict):
                print(f"警告: 节点 {class_name} 的配置无效")
                continue
            # 直接使用配置中的type字段
            nodes.append(config)
        return nodes
        
    def register_node_type(self, type_name: str, node_class):
        """注册节点类型
        
        Args:
            type_name: 节点类型名称
            node_class: 节点类
        """
        self._node_types[type_name] = node_class

    def get_tools(self) -> List[Tool]:
        """
        将现有节点转换为Agent可用的工具列表
        
        Returns:
            List[Tool]: Tool对象列表，每个Tool包含name、description、parameters、outputs和run方法
        """
        tools = []
        nodes = self.get_all_nodes()
        
        for node_info in nodes:
            node_type = node_info.get("type")
            description = node_info.get("description", "No description available")
            
            # 获取参数信息
            params = node_info.get("params", {})
            param_descriptions = []
            for param_name, param_info in params.items():
                if isinstance(param_info, dict):
                    param_type = param_info.get("type", "unknown")
                    required = param_info.get("required", False)
                    default = param_info.get("default", None)
                    param_desc = param_info.get("description", "No description")
                    
                    param_str = f"- {param_name} ({param_type})"
                    if required:
                        param_str += " [Required]"
                    else:
                        param_str += f" [Optional, Default: {default}]"
                    param_str += f": {param_desc}"
                    param_descriptions.append(param_str)
            
            # 获取输出信息
            outputs = node_info.get("output", {})
            output_descriptions = []
            for output_name, output_desc in outputs.items():
                output_descriptions.append(f"- {output_name}: {output_desc}")
            
            # 组合完整描述
            full_description = description + "\n\n"
            if param_descriptions:
                full_description += "Parameters:\n" + "\n".join(param_descriptions) + "\n\n"
            if output_descriptions:
                full_description += "Outputs:\n" + "\n".join(output_descriptions)
            
            # 获取节点类
            node_class = self._node_types.get(node_type)
            if not node_class:
                continue
            if node_type == "loop_node":
                node_class.init_engine(node_class, self.engine)
            # 创建一个闭包来保存node_class和node_info
            def create_tool_runner(node_class, node_info):
                async def run(input_text: str) -> str:
                    try:
                        node_instance = node_class()
                        result = await node_instance.execute(input_text)
                        return result
                    except Exception as e:
                        return f"Error executing node: {str(e)}"
                return run
            
            # 获取参数和输出定义
            params = node_info.get("params", {})
            outputs = node_info.get("output", {})

            tool = Tool(
                name=node_type, # 使用节点类型作为工具名称
                description=description,  # 只使用基本描述
                run=create_tool_runner(node_class, node_info),
                is_async=True,
                params=params,  # 直接传递参数定义
                outputs=outputs  # 直接传递输出定义
            )
            tools.append(tool)
        return tools
    
    def get_nodes_description(self) -> str:
        """
        获取所有节点的描述信息，以清晰、结构化的方式展示每个节点的功能和配置

        Returns:
            str: 格式化的节点描述字符串
        """
        try:
            node_descriptions = []
            for node in self.get_all_nodes():
                try:
                    node_type = node.get("type", "unknown")
                    name = node.get("name", node_type)
                    description = node.get("description", "No description available")
                    params = node.get("params", {})
                    output = node.get("output", {})
                    config = node.get("config", {})
                    
                    # 构建节点基本信息
                    node_desc = [
                        f"Node: {name}",
                        f"Type: {node_type}",
                        "-" * 50,
                        "Description:",
                        f"  {description}",
                        ""
                    ]

                    # 构建配置信息（如果有）
                    if config:
                        node_desc.extend([
                            "Configuration:",
                            *[f"  {key}: {value}" for key, value in config.items()],
                            ""
                        ])

                    # 构建输入参数描述
                    param_desc = []
                    for param_name, param_info in params.items():
                        if not isinstance(param_info, dict):
                            continue
                        
                        param_type = param_info.get("type", "unknown")
                        required = param_info.get("required", False)
                        default = param_info.get("default", None)
                        param_description = param_info.get("description", "No description")
                        
                        # 构建格式化的参数描述
                        param_str = [
                            f"  {param_name}:",
                            f"    Type: {param_type}"
                        ]
                        
                        # 添加必填/可选状态
                        if not required:
                            param_str.append(f"    Optional: Yes (Default: {default})")
                        else:
                            param_str.append("    Required: Yes")
                        
                        # 添加参数描述（支持多行）
                        desc_lines = param_description.split('\n')
                        param_str.append("    Description:")
                        param_str.extend([f"      {line.strip()}" for line in desc_lines])
                        
                        param_desc.extend(param_str)
                    
                    # 添加输入参数部分
                    if param_desc:
                        node_desc.extend([
                            "Input Parameters:",
                            *param_desc,
                            ""
                        ])
                    
                    # 添加输出参数部分
                    if output:
                        node_desc.extend([
                            "Output Parameters:",
                            *[f"  {key}:\n    Description: {value}" for key, value in output.items()],
                            ""
                        ])
                    
                    # 添加分隔线
                    node_desc.append("=" * 80 + "\n")
                    
                    node_descriptions.append("\n".join(node_desc))
                except Exception as e:
                    print(f"处理节点 {node.get('type', 'unknown')} 描述时出错: {str(e)}")
                    continue
            
            return "\n".join(node_descriptions)
        except Exception as e:
            print(f"生成节点描述时出错: {str(e)}")
            return "获取节点描述失败"
    
    def get_nodes_json_example(self) -> str:
        """
        获取节点配置的JSON示例，展示一个实际的工作流场景
        
        Returns:
            str: JSON格式的工作流示例
        """
        workflow_json = {
            "nodes": [
                # 第一层：搜索相关论文
                {
                    "id": "arxiv_search",
                    "type": "arxiv_search",
                    "params": {
                        "query": "Large Language Models recent advances"
                    }
                },
                # 第二层：循环处理搜索结果
                {
                    "id": "loop_papers",
                    "type": "loop_node",
                    "params": {
                        "array": "${arxiv_search.results}",
                        "workflow_json": {
                            "nodes": [
                                # 获取每篇论文的PDF内容
                                {
                                    "id": "crawler",
                                    "type": "web_crawler",
                                    "params": {
                                        "url": "${item.pdf_url}"
                                    }
                                },
                                # 使用AI分析论文内容
                                {
                                    "id": "paper_analysis",
                                    "type": "chat",
                                    "params": {
                                        "system_prompt": "You are a research assistant. Analyze the given paper and extract key findings and contributions.",
                                        "user_question": "Please analyze this paper and provide key findings:\n${crawler.content}",
                                        "temperature": 0.3
                                    }
                                },
                                # 保存分析结果到文件
                                {
                                    "id": "save_analysis",
                                    "type": "file_write",
                                    "params": {
                                        "filename": "${item.entry_id}",
                                        "content": "Title: ${item.title}\nAuthors: ${item.authors}\nAnalysis:\n${paper_analysis.response}",
                                        "format": "txt"
                                    }
                                }
                            ],
                            "edges": [
                                {"from": "crawler", "to": "paper_analysis"},
                                {"from": "paper_analysis", "to": "save_analysis"}
                            ]
                        }
                    }
                },
                # 第三层：数据库操作
                {
                    "id": "db_save",
                    "type": "db_execute",
                    "params": {
                        "host": "localhost",
                        "database": "research_db",
                        "user": "researcher",
                        "password": "password123",
                        "statement": "INSERT INTO paper_analysis (paper_id, title, authors, analysis) VALUES (?, ?, ?, ?)",
                        "parameters": ["${item.entry_id}", "${item.title}", "${item.authors}", "${paper_analysis.response}"]
                    }
                },
                # 第四层：执行Python代码进行数据分析
                {
                    "id": "data_analysis",
                    "type": "python_execute",
                    "params": {
                        "code": """
                        import pandas as pd
                        import numpy as np
                        
                        def analyze_results(data):
                            # 进行数据分析
                            df = pd.DataFrame(data)
                            summary = {
                                'total_papers': len(df),
                                'avg_length': df['analysis'].str.len().mean(),
                                'key_topics': df['analysis'].str.lower().str.findall(r'\\w+').explode().value_counts().head(10).to_dict()
                            }
                            return summary
                        """,
                        "variables": {
                            "data": "${loop_papers.results}"
                        },
                        "timeout": 60
                    }
                }
            ],
            "edges": [
                {"from": "arxiv_search", "to": "loop_papers"},
                {"from": "loop_papers", "to": "db_save"},
                {"from": "db_save", "to": "data_analysis"}
            ]
        }
        return json.dumps(workflow_json, indent=2, ensure_ascii=False)
