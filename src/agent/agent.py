from .prompt.agent_prompt import REACT_PROMPT_TEMPLATES
from typing import List, Dict, Any, Optional, Union, Callable, TypeVar, Generic
from dataclasses import dataclass, field
import asyncio
import logging
import time
import hashlib
import json
from string import Template
from functools import wraps, lru_cache
from src.api.llm_api import call_llm_api
from src.api.events import (
    create_action_start_event, create_action_complete_event,
    create_tool_progress_event, create_tool_retry_event,
    create_agent_start_event, create_agent_complete_event,
    create_agent_error_event, create_agent_thinking_event
)

logger = logging.getLogger(__name__)

T = TypeVar('T')

class Cache(Generic[T]):
    """改进的LRU缓存实现，带有TTL和分层缓存支持"""
    def __init__(self, maxsize: int = 100, ttl: int = 3600):
        self.cache: Dict[str, tuple[T, float]] = {}
        self.maxsize = maxsize
        self.ttl = ttl
        self.semantic_cache: Dict[str, tuple[T, float]] = {}  # 语义缓存

    def get(self, key: str, semantic_key: Optional[str] = None) -> Optional[T]:
        """获取缓存值，支持精确匹配和语义匹配"""
        # 首先尝试精确匹配
        if key in self.cache:
            value, timestamp = self.cache[key]
            if time.time() - timestamp <= self.ttl:
                return value
            del self.cache[key]

        # 如果提供了语义键，尝试语义匹配
        if semantic_key and semantic_key in self.semantic_cache:
            value, timestamp = self.semantic_cache[semantic_key]
            if time.time() - timestamp <= self.ttl:
                return value
            del self.semantic_cache[semantic_key]
        return None

    def set(self, key: str, value: T, semantic_key: Optional[str] = None) -> None:
        """设置缓存值，支持精确缓存和语义缓存"""
        current_time = time.time()
        
        # 更新精确缓存
        if len(self.cache) >= self.maxsize:
            oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k][1])
            del self.cache[oldest_key]
        self.cache[key] = (value, current_time)
        
        # 如果提供了语义键，更新语义缓存
        if semantic_key:
            if len(self.semantic_cache) >= self.maxsize:
                oldest_key = min(self.semantic_cache.keys(), 
                               key=lambda k: self.semantic_cache[k][1])
                del self.semantic_cache[oldest_key]
            self.semantic_cache[semantic_key] = (value, current_time)

class Metrics:
    """增强的性能指标收集器"""
    def __init__(self):
        self.total_calls = 0
        self.total_time = 0.0
        self.error_count = 0
        self.last_response_time = 0.0
        self.tool_usage: Dict[str, int] = {}
        self.cache_hits = 0
        self.cache_misses = 0
        self.retry_count = 0
        self.semantic_cache_hits = 0

    def record_call(self, execution_time: float, is_error: bool = False):
        self.total_calls += 1
        self.total_time += execution_time
        self.last_response_time = execution_time
        if is_error:
            self.error_count += 1

    def record_tool_usage(self, tool_name: str):
        self.tool_usage[tool_name] = self.tool_usage.get(tool_name, 0) + 1

    def record_cache_access(self, hit: bool, semantic: bool = False):
        if hit:
            self.cache_hits += 1
            if semantic:
                self.semantic_cache_hits += 1
        else:
            self.cache_misses += 1

    def record_retry(self):
        self.retry_count += 1

    @property
    def average_response_time(self) -> float:
        return self.total_time / self.total_calls if self.total_calls > 0 else 0.0

    @property
    def error_rate(self) -> float:
        return self.error_count / self.total_calls if self.total_calls > 0 else 0.0

    @property
    def cache_hit_rate(self) -> float:
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0

    @property
    def semantic_cache_hit_rate(self) -> float:
        return (self.semantic_cache_hits / self.cache_hits 
                if self.cache_hits > 0 else 0.0)

def log_execution_time(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = asyncio.get_event_loop().time()
        try:
            result = await func(*args, **kwargs)
            execution_time = asyncio.get_event_loop().time() - start_time
            logger.debug(f"{func.__name__} executed in {execution_time:.2f} seconds")
            return result
        except Exception as e:
            execution_time = asyncio.get_event_loop().time() - start_time
            logger.error(f"{func.__name__} failed after {execution_time:.2f} seconds: {str(e)}")
            raise
    return wrapper

class AgentError(Exception):
    """Agent相关错误的基类"""
    pass

class ToolExecutionError(AgentError):
    """工具执行错误"""
    pass

class ToolNotFoundError(AgentError):
    """工具未找到错误"""
    pass

class LLMAPIError(AgentError):
    """LLM API调用错误"""
    pass

@dataclass
class Tool:
    name: str
    description: str
    run: Callable
    is_async: bool = False
    params: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    outputs: Dict[str, str] = field(default_factory=dict)
    max_retries: int = 0  # 新增：最大重试次数
    retry_delay: float = 1.0  # 新增：重试延迟（秒）
    
    def __post_init__(self):
        if not callable(self.run):
            raise AgentError(f"Tool {self.name} 'run' must be callable")
        if self.params:
            self._validate_params()
            
    def _validate_params(self) -> None:
        for param_name, param_info in self.params.items():
            required_keys = {"type", "description"}
            if not all(key in param_info for key in required_keys):
                raise AgentError(f"Tool {self.name} parameter {param_name} missing required keys: {required_keys}")

class Agent:
    def __init__(
        self, 
        tools: List[Tool], 
        instruction: str = "", 
        timeout: int = 30,
        max_iterations: int = 5,
        memory_size: int = 10,
        cache_size: int = 100,
        cache_ttl: int = 3600,
        stream_manager = None
    ):
        if not tools:
            raise AgentError("At least one tool must be provided")
            
        self.tools = {tool.name: tool for tool in tools}
        self.instruction = instruction
        self.timeout = timeout
        self.max_iterations = max_iterations
        self.memory_size = memory_size
        self._validate_tools()
        
        self._response_cache = Cache[str](maxsize=cache_size, ttl=cache_ttl)
        self.metrics = Metrics()
        self.stream_manager = stream_manager

    def _validate_tools(self) -> None:
        seen_names = set()
        for tool_name, tool in self.tools.items():
            if not isinstance(tool, Tool):
                raise AgentError(f"Invalid tool type: {type(tool)}. Must be Tool instance.")
            if tool_name in seen_names:
                raise AgentError(f"Duplicate tool name found: {tool_name}")
            seen_names.add(tool_name)

    def _construct_prompt(self, query: str, historic_messages: List[str], agent_scratchpad: str) -> str:
        """构造提示模板，使用缓存优化工具描述生成"""
        @lru_cache(maxsize=1)  # 只缓存最新的工具描述，因为工具列表不经常变化
        def get_tools_description() -> tuple[str, str]:
            """获取工具描述和工具名称列表，只包含name、description、params和outputs字段"""
            tool_names = ', '.join(self.tools.keys())
            tools_desc = []
            
            for tool in self.tools.values():
                # 基本描述
                desc_parts = [f"- {tool.name}: {tool.description}"]
                
                # 参数信息
                if tool.params:
                    desc_parts.append("     Parameters:")
                    for param_name, param_info in tool.params.items():
                        param_type = param_info.get("type", "unknown")
                        param_desc = param_info.get("description", "")
                        desc_parts.append(f"        {param_name} ({param_type}): {param_desc}")
                
                # 输出信息
                if tool.outputs:
                    desc_parts.append("     Outputs:")
                    for name, desc in tool.outputs.items():
                        desc_parts.append(f"        {name}: {desc}")
                
                tools_desc.append("\n".join(desc_parts))
            
            return "\n".join(tools_desc), tool_names

        prompt_template = REACT_PROMPT_TEMPLATES['english']['completion']['prompt']
        tools_list, tool_names = get_tools_description()
        formatted_historic = "\n".join(historic_messages[-self.memory_size:])
        values = {
            'instruction': self.instruction,
            'tools': tools_list,
            'tool_names': tool_names,
            'query': query,
            'agent_scratchpad': agent_scratchpad,
            'historic_messages': formatted_historic
        }
        agent_prompt = Template(prompt_template).safe_substitute(values)
        return agent_prompt

    async def _call_model(self, prompt: str,chat_id: str) -> str:
        """调用LLM API并使用分层缓存策略"""
        def get_semantic_key(prompt: str, chat_id: str) -> str:
            """生成语义缓存键
            
            Args:
                prompt: 提示文本
                chat_id: 聊天会话ID
                
            Returns:
                str: 包含会话ID的语义缓存键
            """
            # 提取查询和工具名称等关键信息
            key_parts = [chat_id]  # 将chat_id作为key的第一部分
            if "Question:" in prompt:
                key_parts.append(prompt.split("Question:")[1].split("\n")[0].strip())
            if "Action:" in prompt:
                key_parts.append(prompt.split("Action:")[1].split("\n")[0].strip())
            return hashlib.md5("".join(key_parts).encode()).hexdigest()

        # 生成包含chat_id的缓存键
        cache_key = hashlib.md5(f"{chat_id}:{prompt}".encode()).hexdigest()
        semantic_key = get_semantic_key(prompt, chat_id)
        
        # 检查缓存
        cached_response = self._response_cache.get(cache_key, semantic_key)
        if cached_response:
            logger.debug("Using cached response")
            self.metrics.record_cache_access(hit=True, semantic=semantic_key is not None)
            return cached_response

        self.metrics.record_cache_access(hit=False)
        start_time = time.time()
        try:
            messages = [{"role": "user", "content": prompt}]
            response = await call_llm_api(messages)
            execution_time = time.time() - start_time
            self.metrics.record_call(execution_time)
            
            # 缓存响应
            self._response_cache.set(cache_key, response, semantic_key)
            return response
        except Exception as e:
            execution_time = time.time() - start_time
            self.metrics.record_call(execution_time, is_error=True)
            raise LLMAPIError(f"LLM API call failed: {str(e)}")

    def _parse_action(self, response_text: str) -> Dict[str, Any]:
        """解析LLM响应为动作字典"""
        try:
            if "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            return json.loads(response_text)
        except Exception as e:
            logger.error(f"Failed to parse action from response: {response_text}")
            return {
                "action": "Final Answer",
                "action_input": f"Error parsing response: {str(e)}"
            }

    @log_execution_time
    async def run(self, query: str, chat_id: str, stream: bool = True) -> str:
        """执行Agent的主要逻辑
        
        Args:
            query: 用户输入的查询文本
            chat_id: 聊天会话ID，用于隔离不同会话的上下文和缓存
            stream: 是否启用事件流式传输
            
        Returns:
            str: Agent的响应结果
        """
        try:
            # 发送agent开始事件
            if stream and self.stream_manager:
                event = await create_agent_start_event(query)
                await self.stream_manager.send_message(chat_id, event)

            # 为每个会话维护独立的历史记录
            if not hasattr(self, '_session_history'):
                self._session_history = {}
            if chat_id not in self._session_history:
                self._session_history[chat_id] = []
                
            historic_messages = self._session_history[chat_id]
            agent_scratchpad = ""
            iteration_count = 0
            final_answer = None
            
            while iteration_count < self.max_iterations:
                iteration_count += 1
                try:
                    prompt = self._construct_prompt(query, historic_messages, agent_scratchpad)
                    logger.info(f"Prompt for iteration {iteration_count}: \n{prompt}")

                    # 发送agent思考事件
                    if stream and self.stream_manager:
                        event = await create_agent_thinking_event(f"Iteration {iteration_count}")
                        await self.stream_manager.send_message(chat_id, event)

                    model_response = await asyncio.wait_for(
                        self._call_model(prompt,chat_id),
                        timeout=self.timeout
                    )
                    logger.info(f"LLM Response: \n{model_response}")
                    
                    action_dict = self._parse_action(model_response)
                    action = action_dict.get("action", "")
                    action_input = action_dict.get("action_input", "")
                    
                    if action == "Final Answer":
                        final_answer = action_input
                        break
                        
                    if not action or action not in self.tools:
                        raise ToolNotFoundError(f"Invalid action: {action}")
                        
                    tool = self.tools[action]
                    
                    # 发送动作开始事件
                    if stream and self.stream_manager:
                        event = await create_action_start_event(action, action_input)
                        await self.stream_manager.send_message(chat_id, event)
                    
                    retry_count = 0
                    while retry_count <= tool.max_retries:
                        try:
                            # 发送工具进度事件
                            if stream and self.stream_manager:
                                event = await create_tool_progress_event(
                                    action, "running", action_input
                                )
                                await self.stream_manager.send_message(chat_id, event)
                            
                            # 执行工具
                            if tool.is_async:
                                observation = await tool.run(action_input)
                            else:
                                observation = tool.run(action_input)
                                
                            self.metrics.record_tool_usage(action)
                            
                            # 发送动作完成事件
                            if stream and self.stream_manager:
                                event = await create_action_complete_event(action, observation)
                                await self.stream_manager.send_message(chat_id, event)
                                
                            break  # 工具执行成功，退出重试循环
                            
                        except Exception as e:
                            retry_count += 1
                            self.metrics.record_retry()
                            error_msg = str(e)
                            
                            # 发送工具重试事件
                            if stream and self.stream_manager:
                                event = await create_tool_retry_event(
                                    action, retry_count, tool.max_retries, error_msg
                                )
                                await self.stream_manager.send_message(chat_id, event)
                                
                            if retry_count > tool.max_retries:
                                raise ToolExecutionError(
                                    f"Tool {action} failed after {retry_count} retries: {error_msg}"
                                )
                                
                            await asyncio.sleep(tool.retry_delay)
                            
                    agent_scratchpad += f"\nAction: {action}\nAction Input: {action_input}\nObservation: {observation}\n"
                    
                except asyncio.TimeoutError:
                    error_msg = f"Model response timeout after {self.timeout} seconds"
                    if stream and self.stream_manager:
                        event = await create_agent_error_event(error_msg)
                        await self.stream_manager.send_message(chat_id, event)
                    raise LLMAPIError(error_msg)
                    
                except Exception as e:
                    error_msg = str(e)
                    if stream and self.stream_manager:
                        event = await create_agent_error_event(error_msg)
                        await self.stream_manager.send_message(chat_id, event)
                    raise
                    
            if not final_answer:
                error_msg = f"Failed to get final answer after {self.max_iterations} iterations"
                if stream and self.stream_manager:
                    event = await create_agent_error_event(error_msg)
                    await self.stream_manager.send_message(chat_id, event)
                raise AgentError(error_msg)
                
            # 发送agent完成事件
            if stream and self.stream_manager:
                event = await create_agent_complete_event(final_answer)
                await self.stream_manager.send_message(chat_id, event)
                
            return final_answer
            
        except Exception as e:
            error_msg = str(e)
            if stream and self.stream_manager:
                event = await create_agent_error_event(error_msg)
                await self.stream_manager.send_message(chat_id, event)
            raise
