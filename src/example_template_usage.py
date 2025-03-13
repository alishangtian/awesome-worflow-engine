from string import Template

# 示例模板
template = """Respond to the human as helpfully and accurately as possible. 

${instruction}

You have access to the following tools:

${tools}

Use a json blob to specify a tool by providing an action key (tool name) and an action_input key (tool input).
Valid "action" values: "Final Answer" or ${tool_names}

Question: ${query}
${agent_scratchpad}"""

# 准备要替换的变量值
values = {
    'instruction': 'Help the user with their questions',
    'tools': '''- search: Search the internet
- calculator: Perform calculations''',
    'tool_names': 'search, calculator',
    'query': 'What is 2+2?',
    'agent_scratchpad': 'Thinking about the answer...'
}

# 创建Template对象并替换变量
template_obj = Template(template)
result = template_obj.safe_substitute(values)

print("替换后的结果:")
print(result)
