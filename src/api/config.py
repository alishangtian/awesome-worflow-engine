"""API配置"""

import os
from functools import wraps
from typing import Any, Callable
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

API_CONFIG = {
    "api_key": os.getenv("API_KEY","API_KEY"),
    "model_name": os.getenv("MODEL_NAME", "deepseek-chat"),
    "base_url": os.getenv("BASE_URL", "https://api.deepseek.com/v1"),
    "doc_dir": os.getenv("DOC_DIR", "./docs"),
    "index_dir": os.getenv("INDEX_DIR", "./storage"),
    "long_context_model": os.getenv("LONG_CONTEXT_MODEL", "Doubao-pro-256k")
}

def retry_on_error(max_retries: int = 3):
    """重试装饰器"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_error = None
            for _ in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_error = e
            raise last_error
        return wrapper
    return decorator
