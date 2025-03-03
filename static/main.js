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
    
    // 发送消息
    function sendMessage() {
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

        // 创建SSE连接
        const eventSource = new EventSource(`stream?text=${encodeURIComponent(text)}`);
        
        // 超时处理
        const timeoutId = setTimeout(() => {
            eventSource.close();
            answerElement.innerHTML += `<div class="error">请求超时</div>`;
            resetUI();
        }, 60000);
        
        // 处理状态消息
        eventSource.addEventListener('status', event => {
            console.log("status \n"+event.data);
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
                console.log("workflow \n"+workflow);
                const workflowDiv = document.createElement('div');
                workflowDiv.className = 'workflow-info';
                workflowDiv.innerHTML = `
                    <div>工作流已生成: ${workflow.nodes.length} 个节点</div>
                    <pre>${JSON.stringify(workflow, null, 2)}</pre>
                `;
                answerElement.appendChild(workflowDiv);
            } catch {
                const errorDiv = document.createElement('div');
                errorDiv.className = 'error';
                errorDiv.textContent = '解析工作流失败';
                answerElement.appendChild(errorDiv);
            }
        });

        // 处理节点结果
        eventSource.addEventListener('node_result', event => {
            try {
                const data = JSON.parse(event.data); 
                console.log("node_result \n"+data);
                renderNodeResult(data, answerElement);
            } catch {
                answerElement.innerHTML += `<div class="error">解析节点结果失败</div>`;
            }
        });

        // 渲染节点结果
        function renderNodeResult(data, container) {
            const statusClass = data.success ? 'success' : 'error';
            const content = data.success 
                ? `<pre>${JSON.stringify(data.data, null, 2)}</pre>`
                : `<div class="error">${data.error}</div>`;
            
            const nodeDiv = document.createElement('div');
            nodeDiv.className = `node-result ${statusClass}`;
            nodeDiv.innerHTML = `
                <div class="node-header">
                    <span>节点: ${data.node_id}</span>
                    <span>${data.success ? '成功' : '失败'}</span>
                </div>
                <div class="node-content">${content}</div>
            `;
            container.appendChild(nodeDiv);
        }

        // 初始化Markdown转换器
        const converter = new showdown.Converter({
            tables: true,
            tasklists: true,
            strikethrough: true,
            emoji: true
        });

        // 处理解释说明
        eventSource.addEventListener('explanation', event => {
            try {
                const content = JSON.parse(event.data);
                // 累积解释内容
                currentExplanation += content.data;
                renderExplanation(currentExplanation, answerElement);
            } catch {
                answerElement.innerHTML += `<div class="error">解析解释说明失败</div>`;
            }
        });

        // 处理直接回答
        eventSource.addEventListener('answer', event => {
            try {
                const content = JSON.parse(event.data);
                // 累积回答内容
                currentAnswer += content.data;
                renderAnswer(currentAnswer, answerElement);
            } catch {
                answerElement.innerHTML += `<div class="error">解析回答失败</div>`;
            }
        });

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

        // 处理完成事件
        eventSource.addEventListener('complete', event => {
            try {
                const message = event.data;
                const completeDiv = document.createElement('div');
                completeDiv.className = 'complete';
                completeDiv.innerHTML = `<div>${message}</div>`;
                answerElement.appendChild(completeDiv);
            } catch {
                const errorDiv = document.createElement('div');
                errorDiv.className = 'error';
                errorDiv.textContent = '解析完成事件失败';
                answerElement.appendChild(errorDiv);
            }
            eventSource.close();
            clearTimeout(timeoutId);
            resetUI();
        });

        // 添加非流式工作流执行函数
        async function executeWorkflow(workflow, globalParams = {}) {
            try {
                const response = await fetch('/execute_workflow', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        workflow: workflow,
                        global_params: globalParams
                    })
                });

                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }

                const result = await response.json();
                
                // 渲染工作流
                answerElement.innerHTML += `
                    <div class="workflow-info">
                        <div>工作流已生成: ${result.workflow.nodes.length} 个节点</div>
                        <pre>${JSON.stringify(result.workflow, null, 2)}</pre>
                    </div>`;

                // 渲染所有事件
                result.events.forEach(event => {
                    if (event.node_id) {
                        renderNodeResult(event, answerElement);
                    } else {
                        renderExplanation(event, answerElement);
                    }
                });

                return result;
            } catch (error) {
                answerElement.innerHTML += `<div class="error">执行工作流失败: ${error.message}</div>`;
                throw error;
            }
        }
        
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
        
        // 重置UI
        function resetUI() {
            userInput.value = '';
            userInput.disabled = false;
            sendButton.disabled = false;
            userInput.focus();
        }
    }
});
