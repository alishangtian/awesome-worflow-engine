# Awesome Workflow Engine

一个强大而灵活的基于Python构建的DAG工作流引擎,具有自然语言处理能力和实时执行监控功能。

## 项目介绍

Awesome Workflow Engine是一个现代化的工作流引擎,它允许用户通过简单的JSON配置或自然语言描述来定义和执行复杂的工作流程。引擎基于DAG(有向无环图)设计,支持节点间的依赖关系管理,并提供实时执行状态更新。

## 核心特性

- **基于DAG的工作流执行**
  - 支持复杂的节点依赖关系
  - 支持工作流的暂停、恢复和取消
  - 提供工作流验证确保DAG结构的正确性

- **实时状态监控**
  - 支持节点执行状态实时更新
  - 提供工作流进度追踪
  - 支持流式结果输出

- **自然语言处理**
  - 支持通过自然语言描述生成工作流
  - 智能参数解析和上下文理解
  - 自动工作流优化建议

- **高度可扩展**
  - 插件化的节点系统
  - 支持自定义节点类型
  - 灵活的回调机制

- **Web可视化界面**
  - 直观的工作流设计界面
  - 实时执行状态展示
  - 执行历史记录查看

## 内置节点类型

### 数据处理节点
- 文件读写节点(file_read/file_write)
- 文本替换节点(text_replace)
- Python代码执行节点(python_execute)

### 数据库操作节点
- 数据库查询节点(db_query)
- 数据库执行节点(db_execute)

### AI & 搜索节点
- 聊天集成节点(chat)
- DuckDuckGo搜索节点(duckduckgo_search)
- Serper搜索节点(serper_search)
- 向量索引构建/查询节点(index_build/index_query)

### 网络 & 系统节点
- 网页爬虫节点(web_crawler)
- 终端命令执行节点(terminal)

### 基础运算节点
- 数学运算节点(add/multiply)
- 循环处理节点(loop_node)

## 项目统计

- 源代码文件数: 25+
- 内置节点类型: 15+
- 核心模块: 7个(engine, executor, validator等)
- API接口: 10+

## 安装说明

1. 克隆仓库:
```bash
git clone https://github.com/yourusername/awesome-worflow-engine.git
cd awesome-worflow-engine
```

2. 安装依赖:
```bash
pip install -r requirements.txt
```

3. 配置环境变量:
```bash
cp .env.example .env
# 编辑.env文件配置相关参数
```

## 使用方法

### 启动服务

```bash
python main.py
```

服务默认启动在 `http://localhost:8000`

### 创建工作流

#### 方式1: 使用自然语言

```bash
curl -X POST http://localhost:8000/chat -d '{"text": "搜索最近的AI新闻并总结"}'
```

#### 方式2: 直接定义工作流

```json
{
    "workflow": {
        "nodes": [
            {
                "id": "search",
                "type": "duckduckgo_search",
                "params": {
                    "query": "latest AI developments",
                    "max_results": 5
                }
            },
            {
                "id": "summarize",
                "type": "chat",
                "params": {
                    "system_prompt": "总结以下新闻文章:",
                    "user_input": "$search.results"
                }
            }
        ],
        "edges": [
            {
                "from": "search",
                "to": "summarize"
            }
        ]
    }
}
```

## 开发计划

### 即将实现的功能

- [ ] 工作流模板系统
- [ ] 节点执行超时控制
- [ ] 工作流版本控制
- [ ] 分布式执行支持
- [ ] 更多AI模型集成
- [ ] 工作流调试工具
- [ ] 性能监控仪表板
- [ ] 节点市场

### 正在优化的功能

- [ ] 提升工作流执行效率
- [ ] 增强错误处理机制
- [ ] 改进Web界面交互
- [ ] 优化自然语言处理能力

## API文档

完整的API文档可在服务运行时访问: `http://localhost:8000/docs`

## 开发指南

### 添加新节点类型

1. 在`src/nodes/`下创建新的节点类
2. 继承`BaseNode`类
3. 实现必要的方法
4. 在`node_config.yaml`中注册节点类型

示例:
```python
from .base import BaseNode

class CustomNode(BaseNode):
    async def execute(self, params):
        # 实现节点逻辑
        return {"result": "success"}
```

### 项目结构

- `src/core/`: 核心引擎组件
- `src/api/`: API和服务层
- `src/nodes/`: 节点实现
- `static/`: Web界面资源

## 贡献指南

欢迎提交Pull Request! 在提交之前请确保:

1. 代码符合项目规范
2. 添加了必要的测试
3. 更新了相关文档

## 开源协议

本项目采用MIT协议 - 详见LICENSE文件
