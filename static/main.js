
document.addEventListener('DOMContentLoaded', () => {
    // 添加模型选项按钮点击事件
    const modelOptions = document.querySelectorAll('.model-option');
    modelOptions.forEach(option => {
        option.addEventListener('click', (e) => {
            modelOptions.forEach(btn => btn.classList.remove('active'));
            e.currentTarget.classList.add('active');
            
            // 显示/隐藏轮次输入
            const itecountContainer = document.getElementById('itecount-container');
            if (e.currentTarget.getAttribute('data-model') === 'agent') {
                itecountContainer.style.display = 'inline-block';
            } else {
                itecountContainer.style.display = 'none';
            }
        });
    });
    
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-button');
    const conversationHistory = document.getElementById('conversation-history');
    
    // 用于存储累积的内容
    let currentExplanation = '';
    let currentAnswer = '';
    let currentActionGroup = null;
    let currentActionId = null;
    let currentIteration = 1; // 当前迭代计数

    // 自动滚动到底部的函数
    let isScrolling = false;
    let scrollTimeout = null;

    function scrollToBottom() {
        if (isScrolling) return;
        
        isScrolling = true;
        const lastElement = conversationHistory.lastElementChild;
        if (lastElement) {
            lastElement.scrollIntoView({ behavior: 'smooth', block: 'end' });
        }
        
        // 设置滚动冷却时间
        clearTimeout(scrollTimeout);
        scrollTimeout = setTimeout(() => {
            isScrolling = false;
        }, 500); // 500ms内不重复滚动
    }

    // 事件处理
    sendButton.addEventListener('click', () => {
        sendMessage();
        scrollToBottom();
    });
    
    userInput.addEventListener('keypress', e => {
        if (e.key === 'Enter') {
            sendMessage();
            scrollToBottom();
        }
    });

    // 重置UI
    function resetUI() {
        userInput.value = '';
        userInput.disabled = false;
        sendButton.disabled = false;
        userInput.focus();
    }

    // 渲染节点结果
    function renderNodeResult(data, container) {
        // 根据状态设置样式类和文本
        let statusClass = '';
        let statusText = '';
        let content = '';
        
        // 首先检查error是否存在
        if (data.error) {
            statusClass = 'error';
            statusText = '执行失败';
            content = `<div class="error">${data.error}</div>`;
        } else {
            // 如果没有error，则根据status判断
            switch(data.status) {
                case 'running':
                    // 如果是上一个迭代的节点或已完成的节点，显示为completed
                    if (data.iteration && data.iteration < currentIteration) {
                        statusClass = 'success';
                        statusText = '执行完成';
                    content = data.data ? (typeof data.data === 'string' ? converter.makeHtml(data.data) : `<pre>${JSON.stringify(data.data, null, 2)}</pre>`) : '';
                    } else if (data.completed) {
                        statusClass = 'success';
                        statusText = '执行完成';
                    content = data.data ? (typeof data.data === 'string' ? converter.makeHtml(data.data) : `<pre>${JSON.stringify(data.data, null, 2)}</pre>`) : '';
                    } else {
                        statusClass = 'running';
                        statusText = '执行中';
                        content = '<div class="running-indicator"></div>';
                    }
                    break;
                case 'completed':
                    statusClass = 'success';
                    statusText = '执行完成';
                    content = data.data ? `<pre>${JSON.stringify(data.data, null, 2)}</pre>` : '';
                    break;
                default:
                    statusClass = '';
                    statusText = data.status || '未知状态';
                    content = '';
            }
        }
        
        // 查找是否已存在相同节点的div
        const existingNode = container.querySelector(`[data-node-id="${data.node_id}"]`);
        if (existingNode) {
            // 更新现有节点
            existingNode.className = `node-result ${statusClass}`;
            const wasCollapsed = existingNode.classList.contains('collapsed');
            existingNode.innerHTML = `
                <div class="node-header">
                    <span>节点: ${data.node_id}</span>
                    <span>${statusText}</span>
                </div>
                <div class="node-content">${content}</div>
            `;
            if (wasCollapsed || data.status === 'completed') {
                existingNode.classList.add('collapsed');
            }
        } else {
            // 创建新节点
            const nodeDiv = document.createElement('div');
            nodeDiv.className = `node-result ${statusClass}`;
            nodeDiv.setAttribute('data-node-id', data.node_id);
            nodeDiv.innerHTML = `
                <div class="node-header">
                    <span>节点: ${data.node_id}</span>
                    <span>${statusText}</span>
                </div>
                <div class="node-content">${content}</div>
            `;
            // 如果节点执行完成，默认折叠
            if (data.status === 'completed') {
                nodeDiv.classList.add('collapsed');
            }
            container.appendChild(nodeDiv);
        }
        
        // 添加点击事件处理
        const nodeHeader = container.querySelector(`[data-node-id="${data.node_id}"] .node-header`);
        if (nodeHeader) {
            nodeHeader.onclick = function() {
                this.closest('.node-result').classList.toggle('collapsed');
            };
        }
    }

    // 渲染解释说明
    function renderExplanation(content, container) {
        // 查找或创建explanation div
        let explanationDiv = container.querySelector('.explanation');
        if (!explanationDiv) {
            explanationDiv = document.createElement('div');
            explanationDiv.className = 'explanation';
            container.appendChild(explanationDiv);
        }
        // 使用累积的内容更新div
        const htmlContent = converter.makeHtml(content);
        explanationDiv.innerHTML = htmlContent;
    }

    // 渲染回答
    function renderAnswer(content, container) {
        // 查找或创建answer div
        let answerDiv = container.querySelector('.answer:last-child');
        if (!answerDiv) {
            answerDiv = document.createElement('div');
            answerDiv.className = 'answer';
            container.appendChild(answerDiv);
        }
        // 使用累积的内容更新div
        const htmlContent = converter.makeHtml(content);
        answerDiv.innerHTML = htmlContent;
    }

    // 初始化Markdown转换器
    const converter = new showdown.Converter({
        tables: true,
        tasklists: true,
        strikethrough: true,
        emoji: true
    });

    // 发送消息
    async function sendMessage() {
        const text = userInput.value.trim();
        if (!text) return;
        
        // 禁用输入
        userInput.disabled = true;
        sendButton.disabled = true;
        
        // 创建消息元素
        const questionElement = document.createElement('div');
        questionElement.className = 'history-item';
        
        // 创建qa-container
        const qaContainer = document.createElement('div');
        qaContainer.className = 'qa-container';
        
        // 添加问题
        const questionDiv = document.createElement('div');
        questionDiv.className = 'question';
        questionDiv.textContent = text;
        qaContainer.appendChild(questionDiv);
        
        // 添加回答容器
        const answerElement = document.createElement('div');
        answerElement.className = 'answer';
        qaContainer.appendChild(answerElement);
        
        // 将qa-container添加到history-item
        questionElement.appendChild(qaContainer);
        
        conversationHistory.appendChild(questionElement);
        
        // 重置累积的内容
        currentExplanation = '';
        currentAnswer = '';

        try {
            // 先发送POST请求创建chat会话
            const selectedModelButton = document.querySelector('.model-option.active');
            const selectedModel = selectedModelButton.getAttribute('data-model');
            const response = await fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ 
                    text,
                    model: selectedModel,
                    itecount: selectedModel === 'agent' ? parseInt(document.getElementById('itecount').value) : undefined
                })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const result = await response.json();
            if (!result.success) {
                throw new Error(result.error || '创建会话失败');
            }
            
            // 使用返回的chat_id建立SSE连接
            const eventSource = new EventSource(`stream/${result.chat_id}`);
            
            // 超时处理
            const timeoutId = setTimeout(() => {
                eventSource.close();
                answerElement.innerHTML += `<div class="error">请求超时</div>`;
                resetUI();
            }, 600000);
            
            // 处理状态消息
            eventSource.addEventListener('status', event => {
                const message = event.data;
                const statusDiv = document.createElement('div');
                statusDiv.className = 'status-message';
                statusDiv.textContent = message;
                answerElement.appendChild(statusDiv);
            });

            // 处理工作流事件
            eventSource.addEventListener('workflow', event => {
                currentIteration++; // 每次收到新的工作流事件时增加迭代计数
                try {
                    const workflow = JSON.parse(event.data);
                    const workflowDiv = document.createElement('div');
                    workflowDiv.className = 'workflow-info collapsed';
                    workflowDiv.innerHTML = `
                        <div class="workflow-header">
                            <span>工作流已生成: ${workflow.nodes.length} 个节点</span>
                        </div>
                        <div class="workflow-content">
                            <pre>${JSON.stringify(workflow, null, 2)}</pre>
                        </div>
                    `;
                    answerElement.appendChild(workflowDiv);
                    
                    // Add click handler for workflow header
                    const workflowHeader = workflowDiv.querySelector('.workflow-header');
                    if (workflowHeader) {
                        workflowHeader.onclick = function() {
                            workflowDiv.classList.toggle('collapsed');
                        };
                    }
                } catch (error) {
                    const errorDiv = document.createElement('div');
                    errorDiv.className = 'error';
                    errorDiv.textContent = '解析工作流失败';
                    answerElement.appendChild(errorDiv);
                }
            });

            // 处理节点结果
            eventSource.addEventListener('node_result', event => {
                try {
                    const result = JSON.parse(event.data);
                    // 如果当前节点完成，将之前所有运行中的节点标记为完成
                    if (result.status === 'completed') {
                        const runningNodes = answerElement.querySelectorAll('.node-result.running');
                        runningNodes.forEach(node => {
                            node.classList.remove('running');
                            node.classList.add('success');
                            const statusSpan = node.querySelector('.node-header span:last-child');
                            if (statusSpan) {
                                statusSpan.textContent = '执行完成';
                            }
                            const loadingIndicator = node.querySelector('.running-indicator');
                            if (loadingIndicator) {
                                loadingIndicator.remove();
                            }
                        });
                    }
                    renderNodeResult(result, answerElement);
                } catch (error) {
                    answerElement.innerHTML += `<div class="error">解析节点结果失败</div>`;
                }
            });

            // 处理解释说明
            eventSource.addEventListener('explanation', event => {
                try {
                    const response = JSON.parse(event.data);
                    if (response.success && response.data) {
                        currentExplanation += response.data;
                        renderExplanation(currentExplanation, answerElement);
                    } else if (!response.success) {
                        answerElement.innerHTML += `<div class="error">${response.error || '解析解释说明失败'}</div>`;
                    }
                } catch (error) {
                    answerElement.innerHTML += `<div class="error">解析解释说明失败</div>`;
                }
            });

            // 处理直接回答
            eventSource.addEventListener('answer', event => {
                try {
                    const response = JSON.parse(event.data);
                    if (response.success && response.data) {
                        currentAnswer += response.data;
                        renderAnswer(currentAnswer, answerElement);
                    } else if (!response.success) {
                        answerElement.innerHTML += `<div class="error">${response.error || '解析回答失败'}</div>`;
                    }
                } catch (error) {
                    answerElement.innerHTML += `<div class="error">解析回答失败</div>`;
                }
            });

            // 处理工具进度事件
            eventSource.addEventListener('tool_progress', event => {
                try {
                    const data = JSON.parse(event.data);
                    const actionId = data.action_id || currentActionId;
                    // 查找工具结果容器并更新状态
                    const actionGroup = currentActionGroup || answerElement.querySelector(`.action-group[data-action-id="${actionId}"]`);
                    if (actionGroup) {
                        const toolStatus = actionGroup.querySelector('.tool-status');
                        if (toolStatus) {
                            toolStatus.textContent = '执行中';
                    
        toolStatus.className = 'tool-status running';
                        }
                    }
                } catch (error) {
                    console.error('解析工具进度失败:', error);
                }
            });

            // 处理工具重试事件
            eventSource.addEventListener('tool_retry', event => {
                try {
                    const data = JSON.parse(event.data);
                    const retryDiv = document.createElement('div');
                    retryDiv.className = 'tool-retry';
                    retryDiv.innerHTML = `
                        <div class="retry-info">
                            <span>工具 ${data.tool} 重试中 (${data.attempt}/${data.max_retries})</span>
                            <span class="retry-error">${data.error}</span>
                        </div>
                    `;
                    answerElement.appendChild(retryDiv);
                } catch (error) {
                    console.error('解析工具重试失败:', error);
                }
            });

            // 处理action开始事件
            eventSource.addEventListener('action_start', event => {
                try {
                    const data = JSON.parse(event.data);
                    
                    // 创建新的action组
                    currentActionGroup = document.createElement('div');
                    currentActionGroup.className = 'action-group';
                    currentActionId = data.action_id || Date.now().toString();
                    currentActionGroup.setAttribute('data-action-id', currentActionId);
                    
                    // 将action组添加到答案容器中
                    answerElement.appendChild(currentActionGroup);
                    
                    // 创建action开始元素
                    const startDiv = document.createElement('div');
                    startDiv.setAttribute('data-action-id', currentActionId);
                    startDiv.className = 'action-start';
                    startDiv.innerHTML = `
                        <div class="action-info">
                            <div class="action-header">
                                <span class="action-label">工具：</span>
                                <span class="action-name">${data.action}</span>
                                <span class="tool-status running">执行中</span>
                            </div>
                            <div class="action-params">
                                <span class="params-label">参数：</span>
                                <pre class="params-json">${JSON.stringify(data.input, null, 2)}</pre>
                                <span class="action-timestamp">${new Date(data.timestamp * 1000).toLocaleTimeString()}</span>
                            </div>
                            
                        </div>
                    `;
                    currentActionGroup.appendChild(startDiv);
                } catch (error) {
                    console.error('解析action开始事件失败:', error);
                }
            });

            // 处理action完成事件
            eventSource.addEventListener('action_complete', event => {
                try {
                    const data = JSON.parse(event.data);
                    
                    // 更新工具状态为完成
                    const actionGroup = currentActionGroup || answerElement.querySelector(`.action-group[data-action-id="${data.action_id || currentActionId}"]`);
                    if (!actionGroup) return;
                    
                    // 更新节点状态
                    // 立即更新所有相关节点的状态为完成
                    const allNodes = answerElement.querySelectorAll('.tool-status');
                    console.log(allNodes)
                    allNodes.forEach(node => {
                        if (node.classList.contains('running')) {
                            // 更新状态为完成
                            console.log(node)
                            node.classList.remove('running');
                            node.classList.add('success');
                            node.textContent = '执行完成';
                            const nodeContent = node.querySelector('.node-content');
                            if (nodeContent) {
                                const loadingIndicator = nodeContent.querySelector('.running-indicator');
                                if (loadingIndicator) {
                                    loadingIndicator.remove();
                                }
                                if (data.result) {
                                    nodeContent.innerHTML = typeof data.result === 'string' ? converter.makeHtml(data.result) : `<pre>${JSON.stringify(data.result, null, 2)}</pre>`;
                                }
                            }
                        }
                    });

                    const completeDiv = document.createElement('div');
                    completeDiv.setAttribute('data-action-id', data.action_id || currentActionId);
                    completeDiv.className = 'action-complete';
                    completeDiv.innerHTML = `
                                <span class="result-label">结果：</span>
                                <pre class="result-json">${JSON.stringify(data.result, null, 2)}</pre>
                                <span class="action-timestamp">${new Date(data.timestamp * 1000).toLocaleTimeString()}</span>
                            </div>
                        </div>
                    `;
                    actionGroup.appendChild(completeDiv);
                    currentActionGroup = null; // 重置当前action组
                } catch (error) {
                    console.error('解析action完成事件失败:', error);
                }
            });

            // 处理agent开始事件
            eventSource.addEventListener('agent_start', event => {
                try {
                    const data = JSON.parse(event.data);
                    const startDiv = document.createElement('div');
                    startDiv.className = 'agent-start';
                    startDiv.innerHTML = `
                        <div class="agent-info">
                            <span class="agent-status">Agent开始处理查询</span>
                            <span class="agent-query">${data.query}</span>
                            <span class="agent-timestamp">${new Date(data.timestamp * 1000).toLocaleTimeString()}</span>
                        </div>
                    `;
                    answerElement.appendChild(startDiv);
                } catch (error) {
                    console.error('解析agent开始事件失败:', error);
                }
            });

            // 处理agent思考事件
            eventSource.addEventListener('agent_thinking', event => {
                try {
                    const data = JSON.parse(event.data);
                    const thinkingDiv = document.createElement('div');
                    thinkingDiv.className = 'agent-thinking';
                    thinkingDiv.innerHTML = `
                        <div class="thinking-info">
                            <span class="thinking-indicator"></span>
                            <span class="thinking-content">${data.thought}</span>
                            <span class="thinking-timestamp">${new Date(data.timestamp * 1000).toLocaleTimeString()}</span>
                        </div>
                    `;
                    answerElement.appendChild(thinkingDiv);
                } catch (error) {
                    console.error('解析agent思考事件失败:', error);
                }
            });

            // 处理agent错误事件
            eventSource.addEventListener('agent_error', event => {
                try {
                    const data = JSON.parse(event.data);
                    const errorDiv = document.createElement('div');
                    errorDiv.className = 'agent-error';
                    errorDiv.innerHTML = `
                        <div class="error-info">
                            <span class="error-icon">⚠️</span>
                            <span class="error-message">${data.error}</span>
                            <span class="error-timestamp">${new Date(data.timestamp * 1000).toLocaleTimeString()}</span>
                        </div>
                    `;
                    answerElement.appendChild(errorDiv);
                } catch (error) {
                    console.error('解析agent错误事件失败:', error);
                }
            });

            // 处理agent完成事件
            eventSource.addEventListener('agent_complete', event => {
                try {
                    const data = JSON.parse(event.data);
                    const content = data.result;
                    const completeDiv = document.createElement('div');
                    completeDiv.className = 'agent-complete';
                    completeDiv.innerHTML = `
                        <div class="complete-info">
                            <span class="complete-icon">✓</span>
                            <div class="action_complete">${converter.makeHtml(content)}</div>
                            <span class="complete-timestamp">${new Date(data.timestamp * 1000).toLocaleTimeString()}</span>
                        </div>
                    `;
                    answerElement.appendChild(completeDiv);
                } catch (error) {
                    console.error('解析agent完成事件失败:', error);
                }
            });

            // 处理完成事件
            eventSource.addEventListener('complete', event => {
                try {
                    const result = event.data;
                    const message = result || '完成';
                    const completeDiv = document.createElement('div');
                    completeDiv.className = 'complete';
                    completeDiv.innerHTML = `<div>${message}</div>`;
                    answerElement.appendChild(completeDiv);
                } catch (error) {
                    const errorDiv = document.createElement('div');
                    errorDiv.className = 'error';
                    errorDiv.textContent = '解析完成事件失败';
                    answerElement.appendChild(errorDiv);
                }
                eventSource.close();
                clearTimeout(timeoutId);
                resetUI();
            });

            // 处理错误
            eventSource.onerror = () => {
                eventSource.close();
                const errorDiv = document.createElement('div');
                errorDiv.className = 'error';
                errorDiv.textContent = '连接错误';
                answerElement.appendChild(errorDiv);
                clearTimeout(timeoutId);
                resetUI();
            };

        } catch (error) {
            console.error('发送消息失败:', error);
            answerElement.innerHTML += `<div class="error">发送消息失败: ${error.message}</div>`;
            resetUI();
        }
    }
});
