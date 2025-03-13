COT_COMPLETION_PROMPT_TEMPLATES = """
遵循思维链（COT）进行推理。分步骤思考并使用工具：
${instruction}
可用工具：
${tools}
可用工具名称:
"Final Answer" or ${tool_names}
工作流示例：
${workflow_example}

使用JSON格式返回结构化输出：

每次只输出一个action步骤，必须是以下JSON对象：
```
{
  "Thought": "分析问题的思考过程",
  "Action": {
    "action": "工具名称",
    "action_input": "工具参数"
  },
  "Observation": "工具返回的观察结果"
}
```

如果认为已经有了最终答案，必须以包含以下字段的JSON对象结束：
```
{
  "Thought": "已完成推理",
  "Action": {
    "action": "Final Answer",
    "action_input": "最终答案内容"
  }
}
```

当前任务：${query}
已迭代情况：
${agent_scratchpad}
"""
