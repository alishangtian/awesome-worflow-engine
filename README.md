# Awesome Workflow Engine

基于DAG的工作流执行引擎，支持自然语言输入，可扩展的节点系统。

## 功能特点

- 基于DAG（有向无环图）的工作流执行
- 支持多种节点类型：文本处理、数学运算、LLM对话等
- 支持节点间数据流转
- 支持自然语言输入自动生成工作流
- 提供REST API和Web界面
- 支持流式执行和实时反馈
- 可扩展的节点系统

## 系统要求

- Python 3.8+
- FastAPI
- NetworkX
- aiohttp
- 其他依赖见requirements.txt

## 安装步骤

1. 克隆仓库：
```bash
git clone https://github.com/yourusername/awesome-workflow-engine.git
cd awesome-workflow-engine
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

3. 配置环境变量：
在项目根目录创建`.env`文件，添加以下配置：
```env
API_KEY=your_llm_api_key
BASE_URL=your_llm_api_base_url
MODEL_NAME=your_model_name
```

## 启动服务

1. 启动API服务：
```bash
uvicorn awesome_workflow_engine.api.main:app --reload --port 8000
```

2. 访问Web界面：
打开浏览器访问 http://localhost:8000

## API文档

启动服务后访问 http://localhost:8000/docs 查看完整的API文档。

### 主要接口

1. 流式处理接口
```http
GET /stream?text=your_input_text
```
将自然语言输入转换为工作流并执行，以SSE方式流式返回结果。

2. 执行工作流接口
```http
POST /execute_workflow
Content-Type: application/json

{
    "workflow": {
        "nodes": [...],
        "edges": [...]
    },
    "global_params": {}
}
```

## 工作流示例

### 1. 数学运算工作流
```json
{
    "workflow": {
        "nodes": [
            {
                "id": "add1",
                "type": "add",
                "params": {"num1": 10, "num2": 20}
            },
            {
                "id": "multiply1",
                "type": "multiply",
                "params": {
                    "num1": "$add1.result",
                    "num2": 2
                }
            }
        ],
        "edges": [
            {"from": "add1", "to": "multiply1"}
        ]
    }
}
```

### 2. 自然语言示例
发送请求：`"计算(10+20)*2"`
系统会自动生成并执行上述工作流。

## 自定义节点

1. 在`nodes`目录下创建新的节点类：
```python
from awesome_workflow_engine.nodes.base import BaseNode

class MyCustomNode(BaseNode):
    def execute(self, params):
        # 实现节点逻辑
        return {"result": ...}
```

2. 在`node_config.json`中注册节点：
```json
{
    "MyCustomNode": {
        "type": "custom",
        "description": "自定义节点描述",
        "params": {
            "param1": {"type": "string", "description": "参数1说明"},
            "param2": {"type": "number", "description": "参数2说明"}
        }
    }
}
```

## 项目结构

```
awesome-workflow-engine/
├── src/
│   ├── api/                # API相关代码
│   │   ├── main.py        # FastAPI应用
│   │   └── config.py      # API配置
│   ├── core/              # 核心实现
│   │   ├── engine.py      # 工作流引擎
│   │   └── node_config.py # 节点配置管理
│   └── nodes/             # 节点实现
│       ├── base.py        # 基础节点类
│       ├── math/          # 数学运算节点
│       └── text/          # 文本处理节点
├── static/                # 静态文件
│   └── index.html        # Web界面
├── tests/                 # 测试用例
├── requirements.txt       # 项目依赖
└── README.md             # 项目文档
```

## 开发计划

- [ ] 支持更多节点类型
- [ ] 添加节点执行超时机制
- [ ] 支持工作流模板
- [ ] 添加工作流可视化编辑器
- [ ] 支持工作流历史记录和重放
- [ ] 添加更多单元测试

## 贡献指南

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交改动 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建Pull Request

## 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件
