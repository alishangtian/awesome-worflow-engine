import os
import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime

class LoggerConfig:
    """统一的日志配置类"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LoggerConfig, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not LoggerConfig._initialized:
            self._setup_logger()
            LoggerConfig._initialized = True

    def _setup_logger(self):
        """设置日志配置"""
        # 创建logs目录
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs')
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        # 设置日志文件路径
        log_file = os.path.join(log_dir, 'workflow_engine.log')
        
        # 创建logger
        self.logger = logging.getLogger('workflow_engine')
        self.logger.setLevel(logging.INFO)
        
        # 日志格式
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] [%(module)s:%(lineno)d] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.INFO)
        
        # 文件处理器(每天轮换)
        file_handler = TimedRotatingFileHandler(
            filename=log_file,
            when='midnight',
            interval=1,
            backupCount=30,  # 保留30天的日志
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.INFO)
        
        # 添加处理器（避免重复添加）
        if not any(isinstance(h, logging.StreamHandler) for h in self.logger.handlers):
            self.logger.addHandler(console_handler)
        if not any(isinstance(h, TimedRotatingFileHandler) for h in self.logger.handlers):
            self.logger.addHandler(file_handler)
    
    @classmethod
    def get_logger(cls):
        """获取logger实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance.logger

# 使用示例
# from utils.logger import LoggerConfig
# logger = LoggerConfig.get_logger()
# logger.info("这是一条信息日志")
# logger.error("这是一条错误日志")
