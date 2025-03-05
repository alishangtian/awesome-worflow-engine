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
        获取所有节点的描述信息
        
        Returns:
            str: 格式化的节点描述字符串
        """
        try:
            node_descriptions = []
            for node in self.get_all_nodes():
                try:
                    node_type = node.get("type", "unknown")
                    name = node.get("name", node_type)  # 如果没有name，使用type作为默认值
                    description = node.get("description", "无描述")
                    params = node.get("params", {})
                    output = node.get("output", {})
                    
                    # 构建参数描述
                    param_desc = []
                    for param_name, param_info in params.items():
                        if not isinstance(param_info, dict):
                            continue
                        
                        # 获取参数的所有字段
                        param_type = param_info.get("type", "unknown")
                        required = param_info.get("required", False)
                        default = param_info.get("default", None)
                        description = param_info.get("description", "无描述")
                        
                        # 构建参数描述字符串
                        param_str = f"* {param_name}: {description}"
                        param_str += f" (类型: {param_type}"
                        
                        # 根据required字段决定是否显示default值
                        if not required:
                            param_str += f", 可选, 默认值: {default}"
                        else:
                            param_str += ", 必填"
                            
                        param_str += ")"
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
                except Exception as e:
                    print(f"处理节点 {node.get('type', 'unknown')} 描述时出错: {str(e)}")
                    continue
            
            return "\n\n".join(node_descriptions)
        except Exception as e:
            print(f"生成节点描述时出错: {str(e)}")
            return "获取节点描述失败"
    
    def get_nodes_json_example(self) -> str:
        """
        获取节点配置的JSON示例
        
        Returns:
            str: JSON格式的工作流示例
        """
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
        return json.dumps(workflow_json, indent=2, ensure_ascii=False)
