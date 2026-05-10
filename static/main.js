document.addEventListener('DOMContentLoaded', () => {
    // === 1. GPU 监控 (SSE) ===
    const evtSource = new EventSource('/api/gpu_stats');
    const vramVal = document.getElementById('vram-val');
    const vramBar = document.getElementById('vram-bar');
    const utilVal = document.getElementById('util-val');
    const utilBar = document.getElementById('util-bar');
    const tempVal = document.getElementById('temp-val');

    evtSource.onmessage = function (event) {
        const data = JSON.parse(event.data);
        vramVal.innerText = `${data.memory_used.toFixed(1)} / ${data.memory_total.toFixed(1)} GB`;
        vramBar.style.width = `${(data.memory_used / data.memory_total) * 100}%`;

        utilVal.innerText = `${data.utilization}%`;
        utilBar.style.width = `${data.utilization}%`;

        tempVal.innerText = `${data.temperature}°C`;
    };

    // === 2. 智库摘要逻辑 ===
    const btnSummarize = document.getElementById('btn-summarize');
    const meetingText = document.getElementById('meeting-text');
    const sumProgCont = document.getElementById('sum-progress-container');
    const sumStatus = document.getElementById('sum-status');
    const sumResult = document.getElementById('sum-result');

    btnSummarize.addEventListener('click', async () => {
        const text = meetingText.value.trim();
        if (!text) return alert("请先粘贴文本内容！");

        // UI 切换
        meetingText.classList.add('hidden');
        btnSummarize.classList.add('hidden');
        sumProgCont.classList.remove('hidden');
        sumResult.classList.remove('hidden');
        sumResult.innerText = "";

        try {
            const response = await fetch('/api/summarize', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: text })
            });

            const reader = response.body.getReader();
            const decoder = new TextDecoder('utf-8');

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value);
                const lines = chunk.split('\n').filter(line => line.trim());

                for (let line of lines) {
                    try {
                        const data = JSON.parse(line);
                        if (data.status === 'processing') {
                            sumStatus.innerText = data.message;
                        } else if (data.status === 'done') {
                            sumProgCont.classList.add('hidden');
                            sumResult.innerText = data.result;
                        }
                    } catch (e) { }
                }
            }
        } catch (error) {
            sumStatus.innerText = "处理出错: " + error.message;
        }
    });

    // === 3. 转录上传逻辑 ===
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const transProgCont = document.getElementById('trans-progress-container');
    const transStatus = document.getElementById('trans-status');
    const transBar = document.getElementById('trans-bar');
    const downloadCont = document.getElementById('download-container');
    const btnDownload = document.getElementById('btn-download');

    dropZone.addEventListener('click', () => fileInput.click());

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });

    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        if (e.dataTransfer.files.length) handleUpload(e.dataTransfer.files[0]);
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length) handleUpload(e.target.files[0]);
    });

    async function handleUpload(file) {
        dropZone.classList.add('hidden');
        transProgCont.classList.remove('hidden');
        transStatus.innerText = "正在上传并启动模型...";
        transBar.style.width = "5%";

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('/api/transcribe', {
                method: 'POST',
                body: formData
            });

            const reader = response.body.getReader();
            const decoder = new TextDecoder('utf-8');

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value);
                const lines = chunk.split('\n').filter(line => line.trim());

                for (let line of lines) {
                    try {
                        const data = JSON.parse(line);
                        if (data.status === 'processing') {
                            transStatus.innerText = data.message;
                            transBar.style.width = `${data.progress}%`;
                        } else if (data.status === 'done') {
                            transStatus.innerText = data.message;
                            transBar.style.width = "100%";

                            // 显示下载按钮
                            downloadCont.classList.remove('hidden');
                            btnDownload.href = `/api/download_srt?path=${encodeURIComponent(data.srt_path)}`;
                        }
                    } catch (e) { }
                }
            }
        } catch (error) {
            transStatus.innerText = "处理出错: " + error.message;
            transBar.style.backgroundColor = "red";
        }
    }
    // === 4. AI 聊天逻辑 ===
    const chatHistory = document.getElementById('chat-history');
    const chatInput = document.getElementById('chat-input');
    const btnChatSend = document.getElementById('btn-chat-send');
    const btnNewChat = document.getElementById('btn-new-chat');

    let messages = [{ "role": "assistant", "content": "你好！我是你的本地 AI 助理。你可以问我任何问题，或者让我帮你分析处理过的文本。" }];

    // 全局音频播放器
    const audioPlayer = new Audio();

    // 新建对话逻辑
    btnNewChat.addEventListener('click', () => {
        if (messages.length > 1) {
            if (!confirm("确定要清空当前的对话记录并开始新对话吗？")) return;
        }
        // 1. 重置数据
        messages = [{ "role": "assistant", "content": "你好！我是你的本地 AI 助理。你可以问我任何问题，或者让我帮你分析处理过的文本。" }];
        // 2. 清空 UI 并显示欢迎语
        chatHistory.innerHTML = "";
        appendMessage('assistant', messages[0].content);
    });

    async function sendChatMessage() {
        const text = chatInput.value.trim();
        if (!text) return;

        // 1. 添加用户消息到 UI
        appendMessage('user', text);
        chatInput.value = "";
        messages.push({ "role": "user", "content": text });

        // 2. 显示加载状态
        const loadingMsg = appendMessage('assistant', '正在思考...');

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ messages: messages })
            });

            const data = await response.json();

            // 3. 更新回复
            loadingMsg.innerText = data.response;
            messages.push({ "role": "assistant", "content": data.response });

            // 保持滚动到底部
            chatHistory.scrollTop = chatHistory.scrollHeight;
        } catch (error) {
            loadingMsg.innerText = "出错了: " + error.message;
        }
    }

    function appendMessage(role, text) {
        const div = document.createElement('div');
        div.className = `msg ${role}`;
        
        const contentSpan = document.createElement('span');
        contentSpan.innerText = text;
        div.appendChild(contentSpan);

        // 如果是助手消息，添加朗读按钮
        if (role === 'assistant') {
            const speakBtn = document.createElement('button');
            speakBtn.className = 'btn-speak';
            speakBtn.innerHTML = '🔊';
            speakBtn.title = '朗读此段';
            speakBtn.onclick = () => {
                const currentText = contentSpan.innerText;
                if (currentText === '正在思考...') return;

                const ttsUrl = `/api/tts?text=${encodeURIComponent(currentText)}`;
                
                // 简单的防抖：如果正在放同一段，则停止
                if (audioPlayer.src.includes(encodeURIComponent(currentText)) && !audioPlayer.paused) {
                    audioPlayer.pause();
                    return;
                }

                audioPlayer.src = ttsUrl;
                audioPlayer.play().catch(e => console.error("播放失败:", e));
            };
            div.appendChild(speakBtn);
        }

        chatHistory.appendChild(div);
        chatHistory.scrollTop = chatHistory.scrollHeight;
        return contentSpan;
    }

    btnChatSend.addEventListener('click', sendChatMessage);
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendChatMessage();
    });

    // === 5. 点击代码块自动复制 ===
    document.querySelectorAll('.code-block code').forEach(codeEl => {
        codeEl.style.cursor = 'pointer';
        codeEl.addEventListener('click', () => {
            navigator.clipboard.writeText(codeEl.innerText).then(() => {
                const originalColor = codeEl.style.color;
                codeEl.style.color = '#ffffff';
                setTimeout(() => { codeEl.style.color = originalColor; }, 500);
            });
        });
    });

    // === 6. 停止服务器 ===
    const btnShutdown = document.getElementById('btn-shutdown');
    if (btnShutdown) {
        btnShutdown.onclick = async () => {
            if (!confirm("确定要停止服务器并释放显存吗？\n停止后你需要在终端手动重新启动。")) return;
            
            try {
                btnShutdown.innerText = "正在停止...";
                btnShutdown.disabled = true;
                
                // 使用 fetch 发送指令，设置一个较短的超时
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 2000);

                await fetch('/api/shutdown', { 
                    method: 'POST',
                    signal: controller.signal 
                });
                
                alert("指令已发送，服务器正在关闭中...\n(终端窗口随后会自动退出)");
            } catch (e) {
                // 如果 fetch 报错（通常是因为服务器关得太快了），也认为成功
                alert("服务器已接收关闭指令并正在退出。");
            }
        };
    }

});
