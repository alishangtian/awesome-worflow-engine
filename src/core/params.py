import re
from typing import Dict, Any, Optional
from .models import NodeResult

class ParamsProcessor:
    """参数处理器"""
    
    @staticmethod
    def process_params(
        params: Dict[str, Any],
        results: Dict[str, NodeResult],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """处理节点参数，支持嵌套参数和表达式替换
        
        Args:
            params: 原始参数
            results: 已有的执行结果
            context: 上下文变量
            
        Returns:
            Dict[str, Any]: 处理后的参数
        """
        def replace_expression(value: str) -> str:
            """替换字符串中的所有参数表达式"""
            pattern = r'\$([a-zA-Z0-9_]+)(?:\.([a-zA-Z0-9_]+))*'
            
            def replace(match):
                full_match = match.group(0)
                parts = full_match[1:].split('.')
                node_id = parts[0]
                field_parts = parts[1:]
                
                if node_id not in results:
                    raise ValueError(f"引用了未执行的节点: {node_id}")
                if not results[node_id].data:
                    raise ValueError(f"节点 {node_id} 没有返回数据")
                    
                current = results[node_id].data
                for field in field_parts:
                    if isinstance(current, dict):
                        if field not in current:
                            raise ValueError(f"节点 {node_id} 的结果中不存在字段: {field}")
                        current = current[field]
                    elif hasattr(current, field):
                        current = getattr(current, field)
                    else:
                        raise ValueError(f"无法从 {type(current)} 访问字段: {field}")
                return str(current)
                
            return re.sub(pattern, replace, value)
            
        def process_value(value: Any) -> Any:
            """递归处理参数值"""
            if isinstance(value, str):
                # 处理完整的参数引用 (如 "$node1.param" 或 "$item.field1.field2")
                if value.startswith("$"):
                    if "." in value and not " " in value:
                        parts = value[1:].split(".")
                        ref_node = parts[0]
                        field_parts = parts[1:]
                        
                        # 先检查是否是上下文变量
                        if context and ref_node in context:
                            current = context[ref_node]
                            # 逐级访问字段
                            for field in field_parts:
                                if isinstance(current, dict):
                                    if field not in current:
                                        raise ValueError(f"上下文变量 {ref_node} 中不存在字段: {field}")
                                    current = current[field]
                                elif hasattr(current, field):
                                    current = getattr(current, field)
                                else:
                                    raise ValueError(f"无法从 {type(current)} 访问字段: {field}")
                            return current
                            
                        # 再检查是否是节点引用
                        if ref_node not in results:
                            raise ValueError(f"引用了未执行的节点: {ref_node}")
                        if not results[ref_node].data:
                            raise ValueError(f"节点 {ref_node} 没有返回数据")
                            
                        current = results[ref_node].data
                        # 逐级访问字段
                        for field in field_parts:
                            if isinstance(current, dict):
                                if field not in current:
                                    raise ValueError(f"节点 {ref_node} 的结果中不存在字段: {field}")
                                current = current[field]
                            elif hasattr(current, field):
                                current = getattr(current, field)
                            else:
                                raise ValueError(f"无法从 {type(current)} 访问字段: {field}")
                        return current
                        
                # 支持直接引用上下文变量，如 $item
                elif value.startswith("$") and context and value[1:] in context:
                    return context[value[1:]]
                # 处理包含参数表达式的字符串
                elif "$" in value:
                    return replace_expression(value)
                return value
            elif isinstance(value, dict):
                # 如果值是字典类型，直接返回不做处理
                return value
            elif isinstance(value, list):
                return [process_value(item) for item in value]
            return value
        return {key: process_value(value) for key, value in params.items()}
