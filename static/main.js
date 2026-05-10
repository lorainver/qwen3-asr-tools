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
        if (vramVal) vramVal.innerText = `${data.memory_used.toFixed(1)} / ${data.memory_total.toFixed(1)} GB`;
        if (vramBar) vramBar.style.width = `${(data.memory_used / data.memory_total) * 100}%`;
        if (utilVal) utilVal.innerText = `${data.utilization}%`;
        if (utilBar) utilBar.style.width = `${data.utilization}%`;
        if (tempVal) tempVal.innerText = `${data.temperature}°C`;
    };

    // === 2. 智库摘要逻辑 ===
    const btnSummarize = document.getElementById('btn-summarize');
    const meetingText = document.getElementById('meeting-text');
    const sumProgCont = document.getElementById('sum-progress-container');
    const sumStatus = document.getElementById('sum-status');
    const sumResult = document.getElementById('sum-result');

    if (btnSummarize) {
        btnSummarize.addEventListener('click', async () => {
            const text = meetingText.value.trim();
            if (!text) return alert("请先粘贴文本内容！");
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
    }

    // === 3. 转录上传逻辑 (文件拖拽) ===
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const transProgCont = document.getElementById('trans-progress-container');
    const transStatus = document.getElementById('trans-status');
    const transBar = document.getElementById('trans-bar');
    const downloadCont = document.getElementById('download-container');
    const btnDownload = document.getElementById('btn-download');

    if (dropZone) {
        dropZone.addEventListener('click', () => fileInput.click());
        dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('dragover'); });
        dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('dragover');
            if (e.dataTransfer.files.length) handleUpload(e.dataTransfer.files[0]);
        });
        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length) handleUpload(e.target.files[0]);
        });
    }

    async function handleUpload(file) {
        if (document.querySelector('.path-input-mode')) document.querySelector('.path-input-mode').classList.add('hidden');
        dropZone.classList.add('hidden');
        transProgCont.classList.remove('hidden');
        transStatus.innerText = "正在上传并启动模型...";
        transBar.style.width = "5%";
        const formData = new FormData();
        formData.append('file', file);
        try {
            const response = await fetch('/api/transcribe', { method: 'POST', body: formData });
            await processStream(response);
        } catch (error) {
            transStatus.innerText = "处理出错: " + error.message;
            transBar.style.backgroundColor = "red";
        }
    }

    // === 4. 本地路径转录逻辑 ===
    const btnStartPath = document.getElementById('btn-start-path');
    const localPathInput = document.getElementById('local-video-path');
    if (btnStartPath) {
        btnStartPath.addEventListener('click', async () => {
            const path = localPathInput.value.trim();
            if (!path) return alert("请输入完整路径！");
            if (document.querySelector('.path-input-mode')) document.querySelector('.path-input-mode').classList.add('hidden');
            dropZone.classList.add('hidden');
            transProgCont.classList.remove('hidden');
            transStatus.innerText = "正在定位文件并启动...";
            transBar.style.width = "5%";
            const formData = new FormData();
            formData.append('path', path);
            try {
                const response = await fetch('/api/transcribe_path', { method: 'POST', body: formData });
                await processStream(response);
            } catch (error) {
                transStatus.innerText = "处理出错: " + error.message;
                transBar.style.backgroundColor = "red";
            }
        });
    }

    async function processStream(response) {
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
                        downloadCont.classList.remove('hidden');
                        document.getElementById('srt-path-display').innerText = data.srt_path;
                        btnDownload.href = `/api/download_srt?path=${encodeURIComponent(data.srt_path)}`;
                        const btnOpenFolder = document.getElementById('btn-open-folder');
                        if (btnOpenFolder) {
                            btnOpenFolder.onclick = async () => {
                                await fetch('/api/open_recordings', { method: 'POST' });
                            };
                        }
                    } else if (data.status === 'error') {
                        alert(data.message);
                        transStatus.innerText = data.message;
                    }
                } catch (e) { }
            }
        }
    }

    // === 5. AI 聊天逻辑 ===
    const chatHistory = document.getElementById('chat-history');
    const chatInput = document.getElementById('chat-input');
    const btnChatSend = document.getElementById('btn-chat-send');
    const btnNewChat = document.getElementById('btn-new-chat');
    const checkAutoSpeak = document.getElementById('check-auto-speak');
    const selectTTSEngine = document.getElementById('select-tts-engine');

    let messages = [{ "role": "assistant", "content": "你好！我是你的本地 AI 助理。" }];
    const audioPlayer = new Audio();

    async function playTTS(text, btn) {
        if (!text || text === '正在思考...') return;
        const engine = selectTTSEngine ? selectTTSEngine.value : 'edge';
        const ttsUrl = `/api/tts?text=${encodeURIComponent(text)}&engine=${engine}`;
        if (audioPlayer.src.includes(encodeURIComponent(text)) && !audioPlayer.paused) {
            audioPlayer.pause();
            audioPlayer.currentTime = 0;
            if (btn) btn.innerHTML = '🔊';
            return;
        }
        document.querySelectorAll('.btn-speak').forEach(b => b.innerHTML = '🔊');
        audioPlayer.src = ttsUrl;
        if (btn) btn.innerHTML = '⏹️';
        try {
            await audioPlayer.play();
            audioPlayer.onended = () => { if (btn) btn.innerHTML = '🔊'; };
        } catch (e) { if (btn) btn.innerHTML = '🔊'; }
    }

    if (btnNewChat) {
        btnNewChat.addEventListener('click', () => {
            messages = [{ "role": "assistant", "content": "你好！我是你的本地 AI 助理。" }];
            chatHistory.innerHTML = "";
            appendMessage('assistant', messages[0].content);
        });
    }

    async function sendChatMessage() {
        const text = chatInput.value.trim();
        if (!text) return;
        appendMessage('user', text);
        chatInput.value = "";
        messages.push({ "role": "user", "content": text });
        const loadingMsg = appendMessage('assistant', '正在思考...');
        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ messages: messages })
            });
            const data = await response.json();
            loadingMsg.innerText = data.response;
            messages.push({ "role": "assistant", "content": data.response });
            if (checkAutoSpeak && checkAutoSpeak.checked) {
                const btn = loadingMsg.parentElement.querySelector('.btn-speak');
                playTTS(data.response, btn);
            }
        } catch (error) { loadingMsg.innerText = "出错了: " + error.message; }
    }

    function appendMessage(role, text) {
        const div = document.createElement('div');
        div.className = `msg ${role}`;
        const contentSpan = document.createElement('span');
        contentSpan.innerText = text;
        div.appendChild(contentSpan);
        if (role === 'assistant') {
            const speakBtn = document.createElement('button');
            speakBtn.className = 'btn-speak';
            speakBtn.innerHTML = '🔊';
            speakBtn.onclick = () => playTTS(contentSpan.innerText, speakBtn);
            div.appendChild(speakBtn);
        }
        chatHistory.appendChild(div);
        chatHistory.scrollTop = chatHistory.scrollHeight;
        return contentSpan;
    }

    if (btnChatSend) btnChatSend.addEventListener('click', sendChatMessage);
    if (chatInput) chatInput.addEventListener('keypress', (e) => { if (e.key === 'Enter') sendChatMessage(); });

    // === 6. 释放显存（终止 AI Worker 子进程） ===
    const btnRelease = document.getElementById('btn-shutdown');
    if (btnRelease) {
        btnRelease.addEventListener('click', async () => {
            console.log('[ReleaseGPU] Button clicked');
            btnRelease.disabled = true;
            btnRelease.innerText = "🚀 正在终止 AI 进程...";
            btnRelease.style.backgroundColor = "#ff5252";
            try {
                const resp = await fetch('/api/release_gpu', { method: 'POST' });
                const data = await resp.json();
                console.log('[ReleaseGPU] Response:', data);
                btnRelease.innerText = "✅ 显存已完全释放";
                btnRelease.style.backgroundColor = "#4caf50";
                showToast("✅ AI 进程已终止，显存已完全释放（含 CUDA context）");
                // 3秒后恢复按钮
                setTimeout(() => {
                    btnRelease.disabled = false;
                    btnRelease.innerText = "🛑 释放显存（终止 AI 进程）";
                    btnRelease.style.backgroundColor = "";
                }, 3000);
            } catch (e) {
                console.error('[ReleaseGPU] Error:', e);
                btnRelease.innerText = "❌ 释放失败";
                btnRelease.style.backgroundColor = "#f44336";
                setTimeout(() => {
                    btnRelease.disabled = false;
                    btnRelease.innerText = "🛑 释放显存（终止 AI 进程）";
                    btnRelease.style.backgroundColor = "";
                }, 2000);
            }
        });
    } else {
        console.error('[ReleaseGPU] Button not found!');
    }
    
    function showToast(message) {
        const toast = document.createElement('div');
        toast.style.cssText = `
            position: fixed; top: 20px; left: 50%; transform: translateX(-50%);
            background: rgba(0,0,0,0.85); color: white; padding: 12px 24px;
            border-radius: 8px; z-index: 10000; font-family: Inter, sans-serif;
            animation: fadeInOut 3s ease;
        `;
        toast.textContent = message;
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 3000);
    }
});
