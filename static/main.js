document.addEventListener('DOMContentLoaded', () => {
    // === 0. Markdown 渲染配置 ===
    // 配置 marked
    marked.setOptions({
        highlight: function(code, lang) {
            if (lang && hljs.getLanguage(lang)) {
                try { return hljs.highlight(code, { language: lang }).value; } catch (e) {}
            }
            return hljs.highlightAuto(code).value;
        },
        breaks: true,
        gfm: true
    });

    // 配置 Mermaid
    mermaid.initialize({
        startOnLoad: false,
        theme: 'dark',
        themeVariables: {
            primaryColor: '#0ea5e9',
            primaryTextColor: '#f0f4f8',
            primaryBorderColor: '#1e293b',
            lineColor: '#64748b',
            secondaryColor: '#1e293b',
            tertiaryColor: '#0f172a'
        }
    });

    // 全局 Mermaid 计数器
    let mermaidCounter = 0;

    /**
     * 渲染 Markdown 文本为 HTML
     * 支持：标准 Markdown + KaTeX 数学公式 + Mermaid 图表
     * @param {string} text - 原始 Markdown 文本
     * @returns {string} 渲染后的 HTML
     */
    function renderMarkdown(text) {
        if (!text) return '';
        
        // 1. 保护 Mermaid 代码块，避免被 marked 解析
        const mermaidBlocks = [];
        text = text.replace(/```mermaid\n([\s\S]*?)```/g, (match, code) => {
            const placeholder = `%%MERMAID_${mermaidBlocks.length}%%`;
            mermaidBlocks.push(code.trim());
            return placeholder;
        });

        // 2. 保护数学公式，避免被 marked 解析
        const mathBlocks = [];
        // 块级公式 $$...$$
        text = text.replace(/\$\$([\s\S]*?)\$\$/g, (match, formula) => {
            const placeholder = `%%MATH_BLOCK_${mathBlocks.length}%%`;
            mathBlocks.push({ formula: formula.trim(), display: true });
            return placeholder;
        });
        // 行内公式 $...$
        text = text.replace(/\$([^$\n]+?)\$/g, (match, formula) => {
            const placeholder = `%%MATH_INLINE_${mathBlocks.length}%%`;
            mathBlocks.push({ formula: formula.trim(), display: false });
            return placeholder;
        });

        // 3. 用 marked 渲染 Markdown
        let html = marked.parse(text);

        // 4. 还原并渲染 KaTeX 数学公式
        mathBlocks.forEach((item, i) => {
            const blockKey = `%%MATH_BLOCK_${i}%%`;
            const inlineKey = `%%MATH_INLINE_${i}%%`;
            const key = item.display ? blockKey : inlineKey;
            try {
                const rendered = katex.renderToString(item.formula, {
                    displayMode: item.display,
                    throwOnError: false,
                    trust: true
                });
                html = html.replace(key, rendered);
            } catch (e) {
                html = html.replace(key, item.display 
                    ? `$$${item.formula}$$` 
                    : `$${item.formula}$`);
            }
        });

        // 5. 还原 Mermaid 占位符为容器（异步渲染）
        mermaidBlocks.forEach((code, i) => {
            const placeholder = `%%MERMAID_${i}%%`;
            const containerId = `mermaid-${Date.now()}-${i}`;
            const container = `<div class="mermaid-container" id="${containerId}" data-mermaid-code="${encodeURIComponent(code)}">` +
                `<div class="mermaid-loading">🔄 图表加载中...</div></div>`;
            html = html.replace(placeholder, container);
        });

        return html;
    }

    /**
     * 异步渲染页面中所有未渲染的 Mermaid 图表
     */
    async function renderMermaidDiagrams() {
        const containers = document.querySelectorAll('.mermaid-container:not(.mermaid-rendered)');
        for (const container of containers) {
            const code = decodeURIComponent(container.dataset.mermaidCode);
            try {
                const id = `mermaid-svg-${mermaidCounter++}`;
                const { svg } = await mermaid.render(id, code);
                container.innerHTML = svg;
                container.classList.add('mermaid-rendered');
            } catch (e) {
                container.innerHTML = `<div class="mermaid-error">⚠️ Mermaid 语法错误: <code>${e.message}</code></div>`;
                container.classList.add('mermaid-rendered');
            }
        }
    }

    // === 0.5 标签页切换逻辑 ===
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabPages = document.querySelectorAll('.tab-page');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetTab = btn.dataset.tab;
            
            // 切换标签按钮状态
            tabBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            // 切换页面显示
            tabPages.forEach(page => page.classList.remove('active'));
            const targetPage = document.getElementById(`page-${targetTab}`);
            if (targetPage) targetPage.classList.add('active');
        });
    });

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

    // === 1.5 AI Worker 状态轮询 ===
    const workerDot = document.getElementById('worker-status-dot');
    const workerText = document.getElementById('worker-status-text');
    const workerUptime = document.getElementById('worker-uptime');

    // === 1.6 模型选择器 ===
    const selectModel = document.getElementById('select-model');
    const currentModelTag = document.getElementById('current-model-tag');
    let currentModelId = 'qwen-general';

    async function loadModels() {
        try {
            const resp = await fetch('/api/models');
            const data = await resp.json();
            
            // 清空并填充下拉框
            if (selectModel) {
                selectModel.innerHTML = '';
                for (const model of data.available || []) {
                    const option = document.createElement('option');
                    option.value = model.id;
                    option.textContent = model.name;
                    if (model.current) {
                        option.selected = true;
                        currentModelId = model.id;
                    }
                    selectModel.appendChild(option);
                }
            }
            
            // 更新标签
            if (currentModelTag && data.current) {
                currentModelTag.textContent = data.current.name;
            }
        } catch (e) {
            console.error('加载模型列表失败:', e);
            if (selectModel) {
                selectModel.innerHTML = '<option value="">加载失败</option>';
            }
        }
    }

    // 模型选择变化时切换
    if (selectModel) {
        selectModel.addEventListener('change', async (e) => {
            const newModelId = e.target.value;
            if (!newModelId || newModelId === currentModelId) return;
            
            selectModel.disabled = true;
            currentModelTag.textContent = '切换中...';
            
            try {
                const resp = await fetch('/api/switch_model', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ model_id: newModelId })
                });
                const data = await resp.json();
                
                if (data.status === 'ok' && data.current_model) {
                    currentModelId = newModelId;
                    currentModelTag.textContent = data.current_model.name;
                    showToast(`✅ 已切换到 ${data.current_model.name}`);
                } else {
                    showToast('❌ 切换失败: ' + (data.message || '未知错误'));
                    selectModel.value = currentModelId;
                    loadModels(); // 重新加载
                }
            } catch (e) {
                showToast('❌ 切换失败: ' + e.message);
                selectModel.value = currentModelId;
                loadModels();
            } finally {
                selectModel.disabled = false;
            }
        });
    }

    // 页面加载时加载模型列表
    loadModels();

    setInterval(async () => {
        try {
            const resp = await fetch('/api/worker_status');
            const data = await resp.json();
            if (workerDot && workerText) {
                if (data.running) {
                    workerDot.style.background = '#4caf50';
                    workerText.textContent = '● 运行中';
                    workerText.style.color = '#4caf50';
                    if (workerUptime) {
                        const mins = Math.floor(data.uptime_seconds / 60);
                        const secs = data.uptime_seconds % 60;
                        workerUptime.textContent = `已运行 ${mins}分${secs}秒`;
                    }
                } else {
                    workerDot.style.background = '#555';
                    workerText.textContent = '○ 未启动';
                    workerText.style.color = '#aaa';
                    if (workerUptime) workerUptime.textContent = '';
                }
            }
        } catch (e) {
            // 忽略轮询错误
        }
    }, 2000);

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
            streamingAudioQueue.clear();
        });
    }

    // === 流式语音队列（带预加载） ===
    const streamingAudioQueue = {
        queue: [],         // [{sentence, audio, audioPromise}]
        isPlaying: false,
        currentAudio: null,

        enqueue(sentence) {
            if (!sentence.trim()) return;
            // 立即开始预加载音频（不等播放）
            const engine = selectTTSEngine ? selectTTSEngine.value : 'edge';
            const audio = new Audio(`/api/tts?text=${encodeURIComponent(sentence)}&engine=${engine}`);
            const audioPromise = new Promise((resolve) => {
                audio.addEventListener('canplaythrough', () => resolve(audio), { once: true });
                audio.addEventListener('error', () => resolve(null), { once: true });
                audio.load(); // 触发浏览器预加载
            });
            this.queue.push({ sentence, audio, audioPromise });
            if (!this.isPlaying) this.processNext();
        },

        async processNext() {
            if (this.queue.length === 0) {
                this.isPlaying = false;
                return;
            }
            this.isPlaying = true;
            const { sentence, audio, audioPromise } = this.queue.shift();

            try {
                // 等音频加载完（预加载已提前开始，通常立即可用）
                const readyAudio = await audioPromise;
                if (readyAudio) {
                    this.currentAudio = readyAudio;
                    await readyAudio.play();
                    await new Promise(resolve => { readyAudio.onended = resolve; });
                }
            } catch (e) {
                console.warn('流式 TTS 播放失败:', e);
            }

            this.currentAudio = null;
            this.processNext();
        },

        clear() {
            this.queue = [];
            if (this.currentAudio) {
                this.currentAudio.pause();
                this.currentAudio = null;
            }
            this.isPlaying = false;
        }
    };

    // 句子边界检测
    const SENTENCE_ENDS = '。！？.!?\n';
    let ttsPointer = 0;

    function extractNewSentences(fullText) {
        const pending = fullText.substring(ttsPointer);
        const sentences = [];
        let currentStart = 0;
        for (let i = 0; i < pending.length; i++) {
            if (SENTENCE_ENDS.includes(pending[i])) {
                const s = pending.substring(currentStart, i + 1).trim();
                if (s) sentences.push(s);
                currentStart = i + 1;
            }
        }
        ttsPointer += currentStart;
        return sentences;
    }

    async function sendChatMessage() {
        const text = chatInput.value.trim();
        if (!text) return;
        appendMessage('user', text);
        chatInput.value = "";
        messages.push({ "role": "user", "content": text });
        const loadingMsg = appendMessage('assistant', '');
        
        // 重置流式 TTS 状态
        streamingAudioQueue.clear();
        ttsPointer = 0;
        const useStreamingTTS = checkAutoSpeak && checkAutoSpeak.checked;
        
        try {
            const response = await fetch('/api/chat_stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    messages: messages,
                    model_id: currentModelId
                })
            });
            
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let fullResponse = '';
            
            while (true) {
                const { value, done } = await reader.read();
                if (done) break;
                
                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk.split('\n');
                
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const data = line.slice(6);
                        if (data === '[DONE]') {
                            break;
                        }
                        try {
                            const json = JSON.parse(data);
                            if (json.token) {
                                fullResponse += json.token;
                                // 流式更新：渲染 Markdown
                                loadingMsg.innerHTML = renderMarkdown(fullResponse);
                                chatHistory.scrollTop = chatHistory.scrollHeight;
                                
                                // 流式语音：检测到完整句子立即送 TTS
                                if (useStreamingTTS) {
                                    const newSentences = extractNewSentences(fullResponse);
                                    newSentences.forEach(s => streamingAudioQueue.enqueue(s));
                                }
                            }
                        } catch (e) {
                            // 忽略解析错误
                        }
                    }
                }
            }
            
            // 完成后将回复加入消息历史
            messages.push({ "role": "assistant", "content": fullResponse });
            
            // 渲染 Mermaid 图表（流式结束后可能有未渲染的图表）
            renderMermaidDiagrams();
            
            // 流式 TTS：刷入剩余未完句子
            if (useStreamingTTS && fullResponse.substring(ttsPointer).trim()) {
                streamingAudioQueue.enqueue(fullResponse.substring(ttsPointer).trim());
            }
        } catch (error) { 
            loadingMsg.innerText = "出错了: " + error.message; 
        }
    }

    function appendMessage(role, text) {
        // 创建消息包装器
        const wrapper = document.createElement('div');
        wrapper.className = `msg-wrapper ${role}`;
        
        // 创建消息内容区
        const contentDiv = document.createElement('div');
        contentDiv.className = `msg-content ${role}`;
        
        const contentSpan = document.createElement('span');
        
        if (role === 'assistant') {
            // 助手消息：渲染 Markdown
            contentSpan.className = 'markdown-content';
            contentSpan.innerHTML = renderMarkdown(text);
            // 异步渲染 Mermaid 图表
            setTimeout(renderMermaidDiagrams, 50);
        } else {
            // 用户消息：纯文本
            contentSpan.innerText = text;
        }
        
        contentDiv.appendChild(contentSpan);
        wrapper.appendChild(contentDiv);
        
        // 添加工具栏（复制按钮 + 朗读按钮）
        const toolbar = document.createElement('div');
        toolbar.className = 'msg-toolbar';
        
        // 复制按钮
        const copyBtn = document.createElement('button');
        copyBtn.className = 'btn-icon btn-copy-inline';
        copyBtn.innerHTML = '📋 复制';
        copyBtn.onclick = async () => {
            try {
                await navigator.clipboard.writeText(contentSpan.innerText);
                copyBtn.innerHTML = '✅ 已复制';
                copyBtn.classList.add('copied');
                setTimeout(() => {
                    copyBtn.innerHTML = '📋 复制';
                    copyBtn.classList.remove('copied');
                }, 2000);
            } catch (e) {
                console.error('复制失败:', e);
            }
        };
        toolbar.appendChild(copyBtn);
        
        // 助手消息额外添加朗读按钮
        if (role === 'assistant') {
            const speakBtn = document.createElement('button');
            speakBtn.className = 'btn-icon';
            speakBtn.innerHTML = '🔊 朗读';
            speakBtn.onclick = () => playTTS(contentSpan.innerText, speakBtn);
            toolbar.appendChild(speakBtn);
        }
        
        wrapper.appendChild(toolbar);
        
        chatHistory.appendChild(wrapper);
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
