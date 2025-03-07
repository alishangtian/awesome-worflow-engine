document.addEventListener('DOMContentLoaded', () => {
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-button');
    const conversationHistory = document.getElementById('conversation-history');
    
    // 用于存储累积的内容
    let currentExplanation = '';
    let currentAnswer = '';

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
                    statusClass = 'running';
                    statusText = '执行中';
                    content = '<div class="running-indicator"></div>';
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
            existingNode.innerHTML = `
                <div class="node-header">
                    <span>节点: ${data.node_id}</span>
                    <span>${statusText}</span>
                </div>
                <div class="node-content">${content}</div>
            `;
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
            container.appendChild(nodeDiv);
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
        questionElement.innerHTML = `<div class="question">问题: ${text}</div>`;
        
        const answerElement = document.createElement('div');
        answerElement.className = 'answer';
        questionElement.appendChild(answerElement);
        
        conversationHistory.appendChild(questionElement);
        
        // 重置累积的内容
        currentExplanation = '';
        currentAnswer = '';

        try {
            // 先发送POST请求创建chat会话
            const response = await fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ text })
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
                try {
                    const workflow = JSON.parse(event.data);
                    const workflowDiv = document.createElement('div');
                    workflowDiv.className = 'workflow-info';
                    workflowDiv.innerHTML = `
                        <div>工作流已生成: ${workflow.nodes.length} 个节点</div>
                        <pre>${JSON.stringify(workflow, null, 2)}</pre>
                    `;
                    answerElement.appendChild(workflowDiv);
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
