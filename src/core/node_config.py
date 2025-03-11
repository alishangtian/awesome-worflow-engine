"""节点配置管理模块"""
 
import yaml
import os
import json
from typing import Dict, Optional, List

class NodeConfigManager:
    """节点配置管理类"""
    
    def __init__(self, config_path: str = None):
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
            node_type: 节点类型（下划线格式，如 text_concat）
            
        Returns:
            节点配置信息，如果节点不存在则返回None
        """
        # 转换节点类型为类名，例如: text_concat -> TextConcatNode
        parts = node_type.split('_')
        class_name = ''.join(part.capitalize() for part in parts)
        if not class_name.endswith('Node'):
            class_name += 'Node'
        
        config = self.node_configs.get(class_name)
        if config is not None:
            return {
                "type": node_type,
                **config
            }
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
                
            # 转换类名为节点类型，例如: TextConcatNode -> text_concat
            if class_name.endswith('Node'):
                class_name = class_name[:-4]  # 移除 'Node' 后缀
            
            # 转换驼峰命名为下划线命名
            node_type = ''.join(['_' + c.lower() if c.isupper() else c.lower() for c in class_name]).lstrip('_')
                
            nodes.append({
                "type": node_type,  # 使用转换后的类型名称
                **config
            })
        return nodes
    
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
