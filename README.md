# Workflow Engine

基于DAG的工作流执行引擎，支持多种节点类型和自然语言输入。

## 功能特点

- 支持多种节点类型：
  - 文本处理：连接、替换等
  - 数学运算：加法、乘法等
  - LLM对话：支持与大语言模型交互
- 基于DAG的工作流执行
- 节点间数据流转
- 支持自然语言输入自动生成工作流
- RESTful API接口
- 异步执行
- 错误重试机制

## 安装

1. 克隆仓库：

```bash
git clone https://github.com/yourusername/workflow_engine.git
cd workflow_engine
```

2. 创建并激活虚拟环境（可选）：

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

3. 安装依赖：

```bash
pip install -e .
```

开发环境额外依赖：

```bash
pip install -e ".[dev]"
```

## 配置

1. 复制环境变量示例文件：

```bash
cp .env.example .env
```

2. 编辑.env文件，设置必要的环境变量：

```
API_KEY=your_api_key_here
MODEL_NAME=deepseek-chat
BASE_URL=https://api.deepseek.com/v1
```

## 使用方法

### 1. 启动服务

```bash
python -m workflow_engine.api.main
```

或者使用uvicorn：

```bash
uvicorn workflow_engine.api.main:app --reload
```

服务默认运行在 http://localhost:8000

### 2. API接口

#### 执行工作流

```bash
curl -X POST http://localhost:8000/execute \
  -H "Content-Type: application/json" \
  -d '{
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
  }'
```

#### 自然语言处理

```bash
curl -X POST http://localhost:8000/natural_language \
  -H "Content-Type: application/json" \
  -d '{
    "text": "计算(10+20)*2"
  }'
```

### 3. 支持的节点类型

#### 文本处理节点

1. text_concat
   - 参数：
     - text1: 第一个文本
     - text2: 第二个文本
     - separator: 分隔符（可选）

2. text_replace
   - 参数：
     - text: 原始文本
     - old_str: 要替换的文本
     - new_str: 替换成的文本

#### 数学运算节点

1. add
   - 参数：
     - num1: 第一个数字
     - num2: 第二个数字

2. multiply
   - 参数：
     - num1: 第一个数字
     - num2: 第二个数字

#### LLM对话节点

1. chat
   - 参数：
     - input: 输入文本
     - model: 模型名称（可选）
     - temperature: 温度参数（可选）

### 4. 工作流示例

#### 文本处理工作流

```json
{
  "workflow": {
    "nodes": [
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
        "id": "replace1",
        "type": "text_replace",
        "params": {
          "text": "$concat1.result",
          "old_str": "World",
          "new_str": "Python"
        }
      }
    ],
    "edges": [
      {"from": "concat1", "to": "replace1"}
    ]
  }
}
```

#### 数学计算工作流

```json
{
  "workflow": {
    "nodes": [
      {
        "id": "add1",
        "type": "add",
        "params": {
          "num1": 10,
          "num2": 20
        }
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

## API文档

启动服务后访问：http://localhost:8000/docs

## 开发

### 运行测试

```bash
pytest
```

### 代码格式化

```bash
black .
isort .
```

### 类型检查

```bash
mypy .
```

### 代码风格检查

```bash
flake8
```

## 许可证

MIT License
