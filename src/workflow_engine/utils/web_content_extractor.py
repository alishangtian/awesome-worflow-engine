"""网页内容提取工具类"""

import os
from typing import Dict, Any, Optional
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
import logging
from functools import wraps
import time
import aiohttp
import json
from ..api.config import API_CONFIG

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def retry_on_error(max_retries: int = 3, delay: float = 1.0):
    """重试装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        wait_time = delay * (attempt + 1)
                        logger.warning(
                            f"第{attempt + 1}次尝试失败: {str(e)}，"
                            f"{wait_time}秒后重试..."
                        )
                        time.sleep(wait_time)
                    else:
                        logger.error(f"所有重试都失败了: {str(e)}")
                        raise last_error
        return wrapper
    return decorator

class WebContentExtractor:
    """网页内容提取器"""
    
    def __init__(self):
        """初始化Chrome选项"""
        self.chrome_options = Options()
        self.chrome_options.add_argument('--headless')
        self.chrome_options.add_argument('--no-sandbox')
        self.chrome_options.add_argument('--disable-dev-shm-usage')
    
    @retry_on_error(max_retries=3)
    async def extract_content(
        self,
        url: str,
        output_dir: str = "output",
        wait_time: int = 5,
        save_to_file: bool = True
    ) -> Dict[str, Any]:
        """
        提取网页内容并转换为Markdown格式
        
        Args:
            url: 网页URL
            output_dir: 输出目录
            wait_time: 等待页面加载的时间（秒）
            save_to_file: 是否保存到文件
            
        Returns:
            Dict包含以下字段：
            - success: 是否成功
            - content: Markdown格式的内容
            - output_file: 输出文件路径（如果save_to_file=True）
            - error: 错误信息（如果失败）
        """
        logger.info(f"开始处理URL: {url}")
        
        try:
            # 确保输出目录存在
            if save_to_file:
                os.makedirs(output_dir, exist_ok=True)
            
            # 获取页面内容
            page_content = await self._fetch_page_content(url, wait_time)
            
            # 初始化结果字典
            result = {
                "success": True
            }
            
            # 保存到html
            if save_to_file:
                raw_file = os.path.join(output_dir, "output.html")
                with open(raw_file, 'w', encoding='utf-8') as f:
                    f.write(page_content)
                result["raw_file"] = raw_file
            
            # 转换为Markdown
            markdown_content = await self._convert_to_markdown(page_content)
            
            # 更新结果
            result.update({
                "content": markdown_content,
                "content_length": len(markdown_content)
            })
            
            # 保存到文件
            if save_to_file:
                output_file = os.path.join(output_dir, "output.md")
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(markdown_content)
                result["output_file"] = output_file
                
            logger.info("内容提取完成")
            return result
            
        except Exception as e:
            error_msg = f"内容提取失败: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "content": "",  # 添加空内容
                "content_length": 0  # 添加内容长度为0
            }
    
    async def _fetch_page_content(self, url: str, wait_time: int) -> str:
        """获取页面内容"""
        logger.info("启动Chrome获取页面内容")
        driver = webdriver.Chrome(options=self.chrome_options)
        try:
            driver.get(url)
            
            # 等待页面加载完成
            WebDriverWait(driver, wait_time).until(
                lambda d: d.execute_script('return document.readyState') == 'complete'
            )
            
            return driver.page_source
        finally:
            driver.quit()
    
    def _extract_context_length(self, model_name: str) -> int:
        """从模型名称中提取上下文长度"""
        try:
            # 查找包含k的数字部分
            import re
            match = re.search(r'(\d+)k', model_name.lower())
            if match:
                # 提取数字并转换为整数
                return int(match.group(1)) * 1024
            else:
                # 默认使用32k上下文长度
                logger.warning(f"无法从模型名称 {model_name} 中提取上下文长度，使用默认值32k")
                return 32 * 1024
        except Exception as e:
            logger.error(f"提取上下文长度时出错: {str(e)}")
            return 32 * 1024

    @retry_on_error(max_retries=0)
    async def _convert_to_markdown(self, html_content: str) -> str:
        """使用API将HTML转换为Markdown，支持长文本分段处理"""
        logger.info("开始转换为Markdown格式")
        
        system_prompt = """你是一个网页内容提取助手。请从提供的HTML内容中提取主要正文内容，
        并将其转换为Markdown格式。请去除广告、导航栏、页脚等无关内容，只保留文章的主体部分。
        确保输出格式规范的Markdown文本。"""

        # 获取模型上下文长度并计算最大输入长度
        model_name = API_CONFIG["long_context_model"]
        context_length = self._extract_context_length(model_name)
        max_input_length = context_length // 2
        logger.info(f"模型 {model_name} 的上下文长度为 {context_length}，最大输入长度为 {max_input_length}")
        
        # 计算系统提示的长度
        system_message_length = len(system_prompt)
        
        # 计算实际可用于内容的长度
        available_length = max_input_length - system_message_length - 100  # 预留一些空间给其他字段
        
        # 如果内容长度超过限制，需要分段处理
        if len(html_content) > available_length:
            logger.info(f"内容长度({len(html_content)})超过限制({available_length})，进行分段处理")
            
            # 分段处理
            segments = [html_content[i:i + available_length] 
                       for i in range(0, len(html_content), available_length)]
            
            # 存储所有段落的处理结果
            markdown_segments = []
            
            # 处理每个段落
            for i, segment in enumerate(segments):
                logger.info(f"处理第 {i+1}/{len(segments)} 段")
                
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": segment}
                ]
                
                async with aiohttp.ClientSession() as session:
                    headers = {
                        "Authorization": f"Bearer {API_CONFIG['api_key']}",
                        "Content-Type": "application/json"
                    }
                    
                    data = {
                        "model": model_name,
                        "messages": messages
                    }
                    
                    async with session.post(
                        f"{API_CONFIG['base_url']}/chat/completions",
                        headers=headers,
                        json=data
                    ) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            logger.error(f"API调用失败: 状态码={response.status}, 错误信息={error_text}")
                            raise ValueError(f"API调用失败 (状态码: {response.status}): {error_text}")
                        
                        result = await response.json()
                        markdown_segments.append(result["choices"][0]["message"]["content"])
            
            # 合并所有段落
            logger.info("合并所有处理后的段落")
            return "\n\n".join(markdown_segments)
            
        else:
            # 如果内容长度在限制范围内，直接处理
            logger.info("内容长度在限制范围内，直接处理")
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": html_content}
            ]
            
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {API_CONFIG['api_key']}",
                    "Content-Type": "application/json"
                }
                
                data = {
                    "model": model_name,
                    "messages": messages
                }
                
                async with session.post(
                    f"{API_CONFIG['base_url']}/chat/completions",
                    headers=headers,
                    json=data
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"API调用失败: 状态码={response.status}, 错误信息={error_text}")
                        raise ValueError(f"API调用失败 (状态码: {response.status}): {error_text}")
                    
                    logger.info("API调用成功")
                    result = await response.json()
                    return result["choices"][0]["message"]["content"]

# 使用示例
async def main():
    extractor = WebContentExtractor()
    result = await extractor.extract_content(
        url="https://example.com",
        output_dir="output"
    )
    print(result)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
