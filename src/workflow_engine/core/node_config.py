"""节点配置管理模块"""

import yaml
import os
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
            node_type: 节点类型
            
        Returns:
            节点配置信息，如果节点不存在则返回None
        """
        return self.node_configs.get(node_type)
    
    def get_all_nodes(self) -> List[Dict]:
        """
        获取所有节点的配置信息
        
        Returns:
            所有节点的配置信息列表
        """
        return [
            {"type": node_type, **config}
            for node_type, config in self.node_configs.items()
        ]
    
    def get_nodes_description(self) -> str:
        """
        获取所有节点的描述信息
        
        Returns:
            str: 格式化的节点描述字符串
        """
        node_descriptions = []
        for node in self.get_all_nodes():
            node_type = node["type"]
            name = node["name"]
            description = node["description"]
            params = node["params"]
            output = node["output"]
            
            # 构建参数描述
            param_desc = []
            for param_name, param_info in params.items():
                optional = param_info.get("optional", False)
                default = param_info.get("default", None)
                param_str = f"* {param_name}: {param_info['description']}"
                if optional:
                    param_str += f" (可选，默认值: {default})"
                param_desc.append(param_str)
                
            # 构建输出描述
            output_desc = [f"* {key}: {value}" for key, value in output.items()]
            
            # 组合节点完整描述
            node_desc = [
                f"- {node_type}: {name}",
                f"  描述: {description}",
                "  参数:",
                *[f"  {p}" for p in param_desc],
                "  输出:",
                *[f"  {o}" for o in output_desc]
            ]
            node_descriptions.append("\n".join(node_desc))
        
        return "\n\n".join(node_descriptions)
    
    def get_nodes_json_example(self) -> str:
        workflow_json = {
        "nodes": [
            # 第一层：两个并行的文本处理节点
            {
                "id": "concat1",
                "type": "text_concat",
                "params": {
                    "text1": "Hello",
                    "text2": "World",
                    "separator": " "
                }
            },
            {
                "id": "concat2",
                "type": "text_concat",
                "params": {
                    "text1": "Python",
                    "text2": "DAG",
                    "separator": " "
                }
            },
            # 第二层：两个并行的数学运算节点
            {
                "id": "add1",
                "type": "add",
                "params": {
                    "num1": 10,
                    "num2": 20
                }
            },
            {
                "id": "add2",
                "type": "add",
                "params": {
                    "num1": 30,
                    "num2": 40
                }
            },
            # 第三层：基于前面节点结果的并行节点
            {
                "id": "replace1",
                "type": "text_replace",
                "params": {
                    "text": "$concat1.result",
                    "old_str": "World",
                    "new_str": "$concat2.result"
                }
            },
            {
                "id": "multiply1",
                "type": "multiply",
                "params": {
                    "num1": "$add1.result",
                    "num2": "$add2.result"
                }
            }
        ],
        "edges": [
            # concat1 -> replace1
            {"from": "concat1", "to": "replace1"},
            # concat2 -> replace1
            {"from": "concat2", "to": "replace1"},
            # add1 -> multiply1
            {"from": "add1", "to": "multiply1"},
            # add2 -> multiply1
            {"from": "add2", "to": "multiply1"}
            ]
        }
        return workflow_json