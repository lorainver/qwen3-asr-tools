document.addEventListener('DOMContentLoaded', () => {
    // === 0. Markdown 渲染配置 ===
    // 配置 marked
    marked.setOptions({
        highlight: function (code, lang) {
            if (lang && hljs.getLanguage(lang)) {
                try { return hljs.highlight(code, { language: lang }).value; } catch (e) { }
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
     * 解析 <think>...</think> 标签，返回 { thinking, answer }
     */
    /**
     * 解析所有思考标签，返回分段数组（支持多思考块交替）
     * 如分块翻译时每块都有思考过程：text, thinking, text, thinking, text...
     */
    function parseThinking(text) {
        const THINK = '<think>';
        const END = '</think>';
        const segments = [];
        let pos = 0;
        let inThink = false;

        while (true) {
            const nextThink = text.indexOf(THINK, pos);
            const nextEnd = text.indexOf(END, pos);
            const nextOpen = nextThink === -1 ? Infinity : nextThink;
            const nextClose = nextEnd === -1 ? Infinity : nextEnd;

            if (nextOpen === Infinity && nextClose === Infinity) {
                const tail = text.substring(pos);
                if (tail) {
                    if (inThink && segments.length > 0 && segments[segments.length - 1].type === 'thinking') {
                        segments[segments.length - 1].content += tail;
                    } else if (!inThink) {
                        segments.push({ type: 'text', content: tail });
                    }
                }
                break;
            }

            if (nextOpen < nextClose) {
                // 遇到思考块开始标签
                const before = text.substring(pos, nextOpen);
                if (before) segments.push({ type: 'text', content: before });
                pos = nextOpen + THINK.length;
                inThink = true;
                segments.push({ type: 'thinking', content: '' });
            } else {
                // 遇到思考块结束标签
                if (segments.length > 0 && segments[segments.length - 1].type === 'thinking') {
                    segments[segments.length - 1].content += text.substring(pos, nextEnd);
                }
                pos = nextEnd + END.length;
                inThink = false;
            }
        }

        // 清理尾部空段
        while (segments.length > 0 && !segments[segments.length - 1].content.trim()) {
            segments.pop();
        }
        return segments;
    }

    /**
     * 渲染包含思考过程的消息（支持多思考块交替）
     * @param {string} text - 原始文本（含 <think> 标签）
     * @param {boolean} forceOpen - 生成中强制展开思考块
     */
    function renderWithThinking(text, forceOpen = false) {
        const segments = parseThinking(text);
        if (!segments.length) return '';

        let html = '';
        let thinkCount = 0;

        for (let i = 0; i < segments.length; i++) {
            const seg = segments[i];

            if (seg.type === 'thinking') {
                const c = seg.content.trim();
                if (!c) continue;
                thinkCount++;
                const nextIsText = segments.slice(i + 1).some(s => s.type === 'text' && s.content.trim());
                const openAttr = (forceOpen && nextIsText) ? ' open' : '';
                html += `<div class="thinking-block"><details${openAttr}><summary>💭 思考过程 #${thinkCount} (点击展开)</summary><div class="thinking-content">${renderMarkdown(c)}</div></details></div>`;
            } else {
                const c = seg.content.trim();
                if (!c) continue;
                html += `<div class="answer-content">${renderMarkdown(c)}</div>`;
            }
        }
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

    // === 0.6 DOM 元素初始化 ===
    // GPU 监控
    const vramVal = document.getElementById('vram-val');
    const vramBar = document.getElementById('vram-bar');
    const utilVal = document.getElementById('util-val');
    const utilBar = document.getElementById('util-bar');
    const tempVal = document.getElementById('temp-val');

    // AI Worker
    const workerDot = document.getElementById('worker-status-dot');
    const workerText = document.getElementById('worker-status-text');
    const workerUptime = document.getElementById('worker-uptime');
    const btnShutdown = document.getElementById('btn-shutdown');

    // 模型选择
    const selectModel = document.getElementById('select-model');
    const selectModelCategory = document.getElementById('select-model-category');
    const currentModelTag = document.getElementById('current-model-tag');

    // 总结卡片
    const btnSummarize = document.getElementById('btn-summarize');
    const meetingText = document.getElementById('meeting-text');
    const sumProgCont = document.getElementById('sum-progress-container');
    const sumStatus = document.getElementById('sum-status');
    const sumResult = document.getElementById('sum-result');

    // 转录卡片
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const transProgCont = document.getElementById('trans-progress-container');
    const transStatus = document.getElementById('trans-status');
    const transBar = document.getElementById('trans-bar');
    const downloadCont = document.getElementById('download-container');
    const btnDownload = document.getElementById('btn-download');
    const btnStartPath = document.getElementById('btn-start-path');
    const localPathInput = document.getElementById('local-video-path');

    // AI 聊天
    const chatHistory = document.getElementById('chat-history');
    const chatInput = document.getElementById('chat-input');
    const chatInputExpanded = document.getElementById('chat-input-expanded');
    const btnExpandInput = document.getElementById('btn-expand-input');
    const btnChatSend = document.getElementById('btn-chat-send');
    const btnNewChat = document.getElementById('btn-new-chat');
    const checkOptimizeSearch = document.getElementById('check-optimize-search');
    const checkAutoSpeak = document.getElementById('check-auto-speak');
    const selectTTSEngine = document.getElementById('select-tts-engine');
    const selectHistory = document.getElementById('select-history');
    const checkEnableThink = document.getElementById('check-enable-think'); // 深度思考开关
    const btnThemeToggle = document.getElementById('btn-theme-toggle'); // 主题切换按钮

    // 初始化主题
    const savedTheme = localStorage.getItem('theme') || 'dark';
    if (savedTheme === 'light') {
        document.body.classList.add('light-mode');
        if (btnThemeToggle) btnThemeToggle.innerHTML = '☀️';
    }

    // 主题切换逻辑
    if (btnThemeToggle) {
        btnThemeToggle.addEventListener('click', () => {
            const isLight = document.body.classList.toggle('light-mode');
            localStorage.setItem('theme', isLight ? 'light' : 'dark');
            btnThemeToggle.innerHTML = isLight ? '☀️' : '🌙';

            // 如果使用了 Mermaid，可能需要重新渲染（有些图表颜色是硬编码的）
            if (typeof renderMermaidDiagrams === 'function') {
                renderMermaidDiagrams();
            }
        });
    }

    // 新增图片上传相关
    const btnImageUpload = document.getElementById('btn-image-upload');
    const imageInput = document.getElementById('image-input');
    const imagePreviewContainer = document.getElementById('image-preview-container');
    const imagePreview = document.getElementById('image-preview');
    const btnRemoveImage = document.getElementById('btn-remove-image');
    let selectedImageBase64 = null;

    let currentModelId = 'qwen-general';
    let allAvailableModels = []; // 存储所有加载的模型信息
    const checkWebSearch = document.getElementById('check-web-search');  // 联网搜索开关

    // === 1. GPU 监控 (SSE) ===
    const evtSource = new EventSource('/api/gpu_stats');

    evtSource.onmessage = function (event) {
        const data = JSON.parse(event.data);
        if (vramVal) vramVal.innerText = `${data.memory_used.toFixed(1)} / ${data.memory_total.toFixed(1)} GB`;
        if (vramBar) vramBar.style.width = `${(data.memory_used / data.memory_total) * 100}%`;
        if (utilVal) utilVal.innerText = `${data.utilization}%`;
        if (utilBar) utilBar.style.width = `${data.utilization}%`;
        if (tempVal) tempVal.innerText = `${data.temperature}°C`;
    };

    // === 1.5 AI Worker 状态逻辑 (静默释放版) ===
    if (btnShutdown) {
        btnShutdown.onclick = async () => {
            btnShutdown.disabled = true;
            btnShutdown.textContent = "⌛ 正在释放...";
            try {
                // 注意：这里使用的是 /api/shutdown 或 /api/release_gpu，根据后端实际接口调整
                const response = await fetch('/api/shutdown');
                const result = await response.json();
                window.showToast("✅ 显存已成功释放");
            } catch (error) {
                window.showToast("❌ 释放失败");
            } finally {
                btnShutdown.disabled = false;
                btnShutdown.textContent = "🛑 释放显存";
            }
        };
    }

    async function loadModels() {
        try {
            const resp = await fetch('/api/models');
            const data = await resp.json();
            allAvailableModels = data.available || [];

            // 更新当前模型 ID
            if (data.current) {
                currentModelId = data.current.id;
                currentModelTag.textContent = data.current.name;
            }

            renderModelList();
        } catch (e) {
            console.error('加载模型列表失败:', e);
            if (selectModel) {
                selectModel.innerHTML = '<option value="">加载失败</option>';
            }
        }
    }

    function renderModelList() {
        if (!selectModel) return;

        const category = selectModelCategory ? selectModelCategory.value : 'all';
        selectModel.innerHTML = '';

        // 过滤模型
        const filtered = category === 'all'
            ? allAvailableModels
            : allAvailableModels.filter(m => m.category === category);

        if (filtered.length === 0) {
            selectModel.innerHTML = '<option value="">无匹配模型</option>';
            return;
        }

        // 按类别分组渲染（如果是 'all' 模式）
        if (category === 'all') {
            const groups = {
                'local': { name: '🏠 本地原生模型', options: [] },
                'ollama': { name: '🦙 Ollama 本地模型', options: [] },
                'remote': { name: '🌐 远程 API 模型', options: [] }
            };

            for (const model of filtered) {
                const cat = model.category || 'local';
                if (!groups[cat]) groups[cat] = { name: '其他模型', options: [] };
                groups[cat].options.push(model);
            }

            for (const key in groups) {
                const group = groups[key];
                if (group.options.length === 0) continue;
                const optgroup = document.createElement('optgroup');
                optgroup.label = group.name;
                group.options.forEach(model => {
                    const option = document.createElement('option');
                    option.value = model.id;
                    option.textContent = model.name;
                    if (model.id === currentModelId) option.selected = true;
                    optgroup.appendChild(option);
                });
                selectModel.appendChild(optgroup);
            }
        } else {
            // 单一类别不分组
            filtered.forEach(model => {
                const option = document.createElement('option');
                option.value = model.id;
                option.textContent = model.name;
                if (model.id === currentModelId) option.selected = true;
                selectModel.appendChild(option);
            });
        }
    }

    // 类别变化监听
    if (selectModelCategory) {
        selectModelCategory.addEventListener('change', renderModelList);
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

    // 页面加载时加载模型列表和历史记录
    loadModels();
    loadHistoryList();

    // === 1.7 图片上传处理逻辑 ===
    if (btnImageUpload) {
        btnImageUpload.addEventListener('click', () => imageInput.click());
    }

    if (imageInput) {
        imageInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (!file) return;

            if (!file.type.startsWith('image/')) {
                showToast('❌ 请选择有效的图片文件');
                return;
            }

            const reader = new FileReader();
            reader.onload = (event) => {
                selectedImageBase64 = event.target.result;
                imagePreview.src = selectedImageBase64;
                imagePreviewContainer.classList.remove('hidden');

                // 改进切换逻辑：如果当前模型不具备视觉能力，则提示或自动切换
                // 我们通过模型 ID 是否包含 'vl' 来快速判定
                if (!currentModelId.toLowerCase().includes('vl') && selectModel) {
                    // 优先寻找远程 VL 模型，如果没有再选本地
                    const remoteVLOption = Array.from(selectModel.options).find(opt => opt.value.includes('remote') && opt.value.includes('vl'));
                    const localVLOption = Array.from(selectModel.options).find(opt => opt.value === 'qwen-vl');

                    if (remoteVLOption) {
                        selectModel.value = remoteVLOption.value;
                    } else if (localVLOption) {
                        selectModel.value = localVLOption.value;
                    }
                    selectModel.dispatchEvent(new Event('change'));
                }
            };
            reader.readAsDataURL(file);
        });
    }

    if (btnRemoveImage) {
        btnRemoveImage.addEventListener('click', () => {
            selectedImageBase64 = null;
            imageInput.value = '';
            imagePreviewContainer.classList.add('hidden');
        });
    }

    setInterval(async () => {
        try {
            const resp = await fetch('/api/worker_status');
            const data = await resp.json();
            if (workerDot && workerText) {
                if (data.running) {
                    workerDot.style.background = '#4caf50';
                    workerText.textContent = '运行中';
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

    // === 辅助函数：显示浮动提示 (Toast) ===
    function showToast(message, duration = 2000) {
        let toast = document.getElementById('toast-notification');
        const isLight = document.body.classList.contains('light-mode');
        if (!toast) {
            toast = document.createElement('div');
            toast.id = 'toast-notification';
            toast.style.cssText = `
                position: fixed; bottom: 30px; left: 50%; transform: translateX(-50%);
                background: ${isLight ? 'rgba(14, 165, 233, 0.92)' : 'rgba(56, 189, 248, 0.92)'}; color: ${isLight ? '#ffffff' : '#0a0e1a'};
                padding: 10px 24px; border-radius: 50px; font-weight: bold;
                box-shadow: 0 10px 30px ${isLight ? 'rgba(14, 165, 233, 0.2)' : 'rgba(56, 189, 248, 0.3)'}; z-index: 9999;
                opacity: 0; transition: opacity 0.3s, bottom 0.3s; pointer-events: none;
                font-family: 'Inter', -apple-system, sans-serif;
            `;
            document.body.appendChild(toast);
        }
        toast.textContent = message;
        toast.style.opacity = '1';
        toast.style.bottom = '40px';

        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.bottom = '30px';
        }, duration);
    }

    // === 2. 交互逻辑初始化 ===
    const btnRefreshDevices = document.getElementById('btn-refresh-devices');
    const devicePanel = document.getElementById('device-list-panel');
    const deviceContainer = document.getElementById('device-items-container');
    const deviceClose = document.getElementById('device-close');

    if (btnRefreshDevices) {
        btnRefreshDevices.addEventListener('click', async () => {
            btnRefreshDevices.textContent = '🔄 正在查询...';
            btnRefreshDevices.disabled = true;

            try {
                const response = await fetch('/api/audio_devices');
                const data = await response.json();

                if (data.devices && data.devices.length > 0) {
                    const isLight = document.body.classList.contains('light-mode');
                    let html = `
                        <table style="width: 100%; border-collapse: collapse; color: ${isLight ? '#475569' : '#94a3b8'}; font-size: 0.88em;">
                            <thead>
                                <tr style="border-bottom: 2px solid rgba(56, 189, 248, 0.2); text-align: left;">
                                    <th style="padding: 8px; color: #38bdf8;">ID</th>
                                    <th style="padding: 8px; color: #38bdf8;">驱动类型</th>
                                    <th style="padding: 8px; color: #38bdf8;">设备名称</th>
                                </tr>
                            </thead>
                            <tbody>
                    `;

                    data.devices.forEach(dev => {
                        const apiMap = { 0: 'MME', 1: 'DirectSound', 2: 'WASAPI', 3: 'WDM-KS' };
                        const apiName = apiMap[dev.hostapi] || 'Unknown';
                        const isRecommended = apiName === 'WASAPI';
                        const isVirtual = dev.name.toLowerCase().includes('cable') || dev.name.toLowerCase().includes('streaming');
                        const icon = isVirtual ? '🔌' : '🎙️';

                        html += `
                            <tr style="border-bottom: 1px solid ${isLight ? 'rgba(0,0,0,0.06)' : 'rgba(255,255,255,0.05)'}; cursor: pointer;" onclick="navigator.clipboard.writeText('${dev.id}'); window.showToast('✅ 已成功复制 ID: ${dev.id}')">
                                <td style="padding: 8px; font-weight: bold; color: ${isRecommended ? '#38bdf8' : (isLight ? '#475569' : '#94a3b8')};">${dev.id}</td>
                                <td style="padding: 8px;"><span style="font-size: 0.8em; padding: 2px 6px; border-radius: 4px; background: ${isRecommended ? 'rgba(56, 189, 248, 0.12)' : (isLight ? 'rgba(0,0,0,0.04)' : 'rgba(255,255,255,0.05)')};">${apiName}</span></td>
                                <td style="padding: 8px; color: ${isVirtual ? '#64748b' : (isLight ? '#0f172a' : '#e2e8f0')};">${icon} ${dev.name}</td>
                            </tr>
                        `;
                    });

                    html += `</tbody></table>
                            <div style="font-size: 0.78em; color: #64748b; margin-top: 10px; text-align: center;">💡 提示：点击行可直接复制 ID。推荐优先使用 <span style="color: #38bdf8;">WASAPI</span> 驱动。</div>`;
                    deviceContainer.innerHTML = html;
                    devicePanel.classList.remove('hidden');
                } else {
                    deviceContainer.innerHTML = '<div style="color: #f87171;">未发现输入设备</div>';
                    devicePanel.classList.remove('hidden');
                }
            } catch (error) {
                console.error('Failed to fetch devices:', error);
                window.showToast('❌ 查询失败');
            } finally {
                btnRefreshDevices.textContent = '🔍 查询设备 ID';
                btnRefreshDevices.disabled = false;
            }
        });
    }

    // 暴露给 window 方便在 HTML onclick 中调用
    window.showToast = showToast;

    if (deviceClose) {
        deviceClose.addEventListener('click', () => {
            devicePanel.classList.add('hidden');
        });
    }

    // === 2. 智库摘要逻辑 ===

    // 语言选择下拉框控制（仅翻译模式显示）
    const promptTypeSelect = document.getElementById('prompt-type');
    const targetLangSelect = document.getElementById('target-lang');

    if (promptTypeSelect && targetLangSelect) {
        // 初始化：根据当前选择显示/隐藏
        targetLangSelect.classList.toggle('hidden', promptTypeSelect.value !== 'translate');
        
        // 监听变化
        promptTypeSelect.addEventListener('change', () => {
            targetLangSelect.classList.toggle('hidden', promptTypeSelect.value !== 'translate');
        });
    }

    if (btnSummarize) {
        btnSummarize.addEventListener('click', async () => {
            const text = meetingText.value.trim();
            if (!text) return alert("请先粘贴文本内容！");
            meetingText.classList.add('hidden');
            btnSummarize.classList.add('hidden');
            sumProgCont.classList.remove('hidden');
            sumResult.classList.remove('hidden');
            sumResult.innerText = "";
            
            const promptType = document.getElementById('prompt-type').value;
            const targetLang = targetLangSelect && promptType === 'translate' ? targetLangSelect.value : null;
            
            const requestBody = { text: text, prompt_type: promptType };
            if (targetLang) requestBody.target_lang = targetLang;
            
            try {
                const response = await fetch('/api/summarize', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(requestBody)
                });
                const reader = response.body.getReader();
                const decoder = new TextDecoder('utf-8');
                let fullText = '';  // 累积流式文本（含 thinking 标签）
                // 切换为 Markdown 渲染模式
                sumResult.classList.add('markdown-mode');
                sumResult.innerText = '';
                
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
                            } else if (data.status === 'streaming' && data.delta) {
                                // 流式增量渲染
                                fullText += data.delta;
                                
                                // 使用 renderWithThinking 渲染，生成中强制展开思考块
                                // summarizer.py 已将 Ollama reasoning_content 包裹为 <think>...</think>
                                // parseThinking() 自动识别这两个标签，无需额外检测
                                sumResult.innerHTML = renderWithThinking(fullText, true);
                                
                                // 自动滚动到底部
                                sumResult.scrollTop = sumResult.scrollHeight;
                            } else if (data.status === 'done') {
                                sumProgCont.classList.add('hidden');
                                // 最终渲染：思考块折叠，正文 Markdown 渲染
                                sumResult.innerHTML = renderWithThinking(data.result, false);
                                // 触发 Mermaid 图表渲染
                                setTimeout(() => {
                                    document.querySelectorAll('#sum-result .mermaid-container').forEach(el => {
                                        try {
                                            const code = decodeURIComponent(el.dataset.mermaidCode);
                                            mermaid.render(`mermaid-svg-${Date.now()}`, code).then(svg => {
                                                el.innerHTML = svg;
                                            });
                                        } catch (e) { el.innerHTML = '<pre>' + code + '</pre>'; }
                                    });
                                }, 100);
                            } else if (data.status === 'error') {
                                sumProgCont.classList.add('hidden');
                                sumResult.innerText = "❌ " + data.message;
                            }
                        } catch (e) { }
                    }
                }
            } catch (error) {
                sumProgCont.classList.add('hidden');
                sumStatus.innerText = "处理出错: " + error.message;
            }
        });
    }

    // 初始化搜索优化设置 (主界面开关)
    const savedOptimize = localStorage.getItem('optimize_search');
    if (savedOptimize !== null && checkOptimizeSearch) {
        checkOptimizeSearch.checked = savedOptimize === 'true';
    }

    if (checkOptimizeSearch) {
        checkOptimizeSearch.addEventListener('change', () => {
            localStorage.setItem('optimize_search', checkOptimizeSearch.checked);
        });
    }

    // === 3. 转录上传逻辑 (文件拖拽) ===

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

    let isInputExpanded = false;

    // 输入框展开/收起逻辑
    if (btnExpandInput) {
        btnExpandInput.addEventListener('click', () => {
            isInputExpanded = !isInputExpanded;
            if (isInputExpanded) {
                chatInput.classList.add('hidden');
                chatInputExpanded.classList.remove('hidden');
                chatInputExpanded.value = chatInput.value;
                chatInputExpanded.focus();
                btnExpandInput.innerHTML = '📓';
                btnExpandInput.title = '收起为单行';
            } else {
                chatInput.classList.remove('hidden');
                chatInputExpanded.classList.add('hidden');
                chatInput.value = chatInputExpanded.value;
                chatInput.focus();
                btnExpandInput.innerHTML = '📝';
                btnExpandInput.title = '展开多行输入';
            }
        });
    }

    // 多行输入的键盘事件
    if (chatInputExpanded) {
        chatInputExpanded.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendChatMessage();
            }
        });
    }

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
        btnNewChat.addEventListener('click', async () => {
            // 如果当前有对话内容（不仅仅是默认的第一条），则尝试保存
            if (messages.length > 1) {
                const originalText = btnNewChat.innerHTML;
                btnNewChat.innerHTML = '💾 保存中...';
                btnNewChat.disabled = true;

                try {
                    await saveCurrentChat();
                } catch (e) {
                    console.error('保存历史失败:', e);
                } finally {
                    btnNewChat.innerHTML = originalText;
                    btnNewChat.disabled = false;
                }
            }

            messages = [{ "role": "assistant", "content": "你好！我是你的本地 AI 助理。" }];
            chatHistory.innerHTML = "";
            appendMessage('assistant', messages[0].content);
            streamingAudioQueue.clear();
        });
    }

    // === 5.1 对话历史管理逻辑 ===

    async function loadHistoryList() {
        if (!selectHistory) return;
        try {
            const resp = await fetch('/api/history/list');
            const list = await resp.json();

            // 保留第一项默认项
            selectHistory.innerHTML = '<option value="">📜 历史对话</option>';
            list.forEach(item => {
                const opt = document.createElement('option');
                opt.value = item.path;
                opt.textContent = item.title;
                selectHistory.appendChild(opt);
            });
        } catch (e) {
            console.error('加载历史列表失败:', e);
        }
    }

    async function saveCurrentChat() {
        if (messages.length <= 1) return;

        // 1. 获取第一条用户消息作为标题基础
        const firstUserMsg = messages.find(m => m.role === 'user')?.content || "新对话";
        let title = firstUserMsg.substring(0, 10);

        // 2. 尝试让 AI 生成一个更智能的标题 (非流式请求)
        try {
            const titlePrompt = `请为以下对话生成一个5字以内的简短标题。对话内容：${firstUserMsg.substring(0, 100)}`;
            const resp = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    messages: [{ role: 'user', content: titlePrompt }],
                    model_id: currentModelId
                })
            });
            const data = await resp.json();
            if (data.response) {
                title = data.response.replace(/[#"'\n\r]/g, '').substring(0, 15);
            }
        } catch (e) {
            console.warn('AI 生成标题失败，使用默认标题');
        }

        // 3. 提交保存
        const saveResp = await fetch('/api/history/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title: title,
                messages: messages
            })
        });
        const saveResult = await saveResp.json();
        if (saveResult.status === 'success') {
            loadHistoryList(); // 刷新列表
        }
    }

    if (selectHistory) {
        selectHistory.addEventListener('change', async (e) => {
            const path = e.target.value;
            if (!path) return;

            try {
                const resp = await fetch(`/api/history/load?path=${encodeURIComponent(path)}`);
                const data = await resp.json();
                if (data.messages) {
                    // 清空并重新加载消息
                    messages = data.messages;
                    chatHistory.innerHTML = "";
                    messages.forEach(msg => {
                        appendMessage(msg.role, msg.content);
                    });
                    showToast(`📂 已加载历史: ${data.title}`);
                }
            } catch (e) {
                showToast('❌ 加载失败: ' + e.message);
            } finally {
                selectHistory.value = ""; // 重置下拉框
            }
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
        // 从当前活动的输入框获取文本
        const activeInput = isInputExpanded ? chatInputExpanded : chatInput;
        const text = activeInput.value.trim();
        if (!text) return;
        if (isInputExpanded) chatInput.value = "";
        else chatInputExpanded.value = "";

        // 构建消息内容
        let messageContent;
        if (selectedImageBase64) {
            // 多模态消息格式
            messageContent = [
                {
                    type: 'image',
                    image: selectedImageBase64,
                    // 针对 8GB 显存进行优化，限制最大像素点，防止 OOM
                    max_pixels: 600 * 600
                },
                { type: 'text', text: text }
            ];
            // 在对话历史中显示图片
            const userMsgSpan = appendMessage('user', text);
            const img = document.createElement('img');
            img.src = selectedImageBase64;
            img.className = 'chat-image';
            img.onclick = () => window.open(img.src, '_blank');
            userMsgSpan.parentElement.insertBefore(img, userMsgSpan);

            // 清理图片预览
            btnRemoveImage.click();
        } else {
            // 纯文本消息格式
            messageContent = text;
            appendMessage('user', text);
        }

        messages.push({ "role": "user", "content": messageContent });
        const loadingMsg = appendMessage('assistant', '');

        // 显示“正在思考...”动画
        loadingMsg.innerHTML = '<span class="thinking-dots">正在思考<span class="dot dot-1">.</span><span class="dot dot-2">.</span><span class="dot dot-3">.</span></span>';

        // 重置流式 TTS 状态
        streamingAudioQueue.clear();
        ttsPointer = 0;
        const useStreamingTTS = checkAutoSpeak && checkAutoSpeak.checked;

        // 联网搜索及优化参数
        const isSearchEnabled = checkWebSearch && checkWebSearch.checked;
        const isOptimizeEnabled = checkOptimizeSearch && checkOptimizeSearch.checked;
        const isThinkEnabled = checkEnableThink && checkEnableThink.checked;

        console.log(`📡 [Network] 发送请求: search=${isSearchEnabled}, optimize=${isOptimizeEnabled}, think=${isThinkEnabled}`);

        try {
            const response = await fetch('/api/chat_stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    messages: messages,
                    model_id: currentModelId,
                    enable_search: isSearchEnabled,
                    optimize_search: isOptimizeEnabled,
                    enable_think: isThinkEnabled
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
                                // 流式更新：渲染 Markdown，生成时保持思考过程展开
                                loadingMsg.innerHTML = renderWithThinking(fullResponse, true);
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

            // 生成结束，进行最后一次渲染（允许折叠）
            loadingMsg.innerHTML = renderWithThinking(fullResponse, false);

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

        // 创建消息气泡容器
        const contentDiv = document.createElement('div');
        contentDiv.className = `msg-content ${role}`;

        // 创建实际消息体 (使用 div 替代 span，以支持内部包含思考块等块级元素)
        const messageBody = document.createElement('div');

        if (role === 'assistant') {
            // 助手消息：渲染 Markdown
            messageBody.className = 'markdown-content';
            messageBody.innerHTML = renderWithThinking(text, false);
            // 异步渲染 Mermaid 图表
            setTimeout(renderMermaidDiagrams, 50);
        } else {
            // 用户消息：纯文本
            messageBody.innerText = text;
        }

        contentDiv.appendChild(messageBody);
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
                await navigator.clipboard.writeText(messageBody.innerText);
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
            speakBtn.onclick = () => playTTS(messageBody.innerText, speakBtn);
            toolbar.appendChild(speakBtn);
        }

        wrapper.appendChild(toolbar);

        chatHistory.appendChild(wrapper);
        chatHistory.scrollTop = chatHistory.scrollHeight;
        return messageBody;
    }

    if (btnChatSend) btnChatSend.addEventListener('click', sendChatMessage);
    if (chatInput) chatInput.addEventListener('keypress', (e) => { if (e.key === 'Enter') sendChatMessage(); });

    // === 6. 释放显存（终止 AI Worker 子进程） ===
    const btnRelease = document.getElementById('btn-shutdown');
    if (btnRelease) {
        btnRelease.addEventListener('click', async () => {
            console.log('[ReleaseGPU] Button clicked');
            btnRelease.disabled = true;
            btnRelease.innerText = "正在终止...";
            btnRelease.style.backgroundColor = "#ff5252";
            try {
                const resp = await fetch('/api/release_gpu', { method: 'POST' });
                const data = await resp.json();
                console.log('[ReleaseGPU] Response:', data);
                btnRelease.innerText = "已释放";
                btnRelease.style.backgroundColor = "#4caf50";
                showToast("✅ AI 进程已终止，显存已完全释放（含 CUDA context）");
                // 3秒后恢复按钮
                setTimeout(() => {
                    btnRelease.disabled = false;
                    btnRelease.innerText = "🛑 释放显存";
                    btnRelease.style.backgroundColor = "";
                }, 3000);
            } catch (e) {
                console.error('[ReleaseGPU] Error:', e);
                btnRelease.innerText = "释放失败";
                btnRelease.style.backgroundColor = "#f44336";
                setTimeout(() => {
                    btnRelease.disabled = false;
                    btnRelease.innerText = "🛑 释放显存";
                    btnRelease.style.backgroundColor = "";
                }, 2000);
            }
        });
    } else {
        console.error('[ReleaseGPU] Button not found!');
    }

    function showToast(message) {
        const toast = document.createElement('div');
        const isLight = document.body.classList.contains('light-mode');
        toast.style.cssText = `
            position: fixed; top: 20px; left: 50%; transform: translateX(-50%);
            background: ${isLight ? 'rgba(255, 255, 255, 0.95)' : 'rgba(15, 23, 42, 0.92)'}; color: ${isLight ? '#0f172a' : '#e2e8f0'}; padding: 12px 24px;
            border-radius: 8px; z-index: 10000; font-family: 'Inter', -apple-system, sans-serif;
            border: 1px solid ${isLight ? 'rgba(0, 0, 0, 0.1)' : 'rgba(56, 189, 248, 0.2)'}; box-shadow: 0 8px 24px ${isLight ? 'rgba(0,0,0,0.1)' : 'rgba(0,0,0,0.4)'};
        `;
        toast.textContent = message;
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 3000);
    }
});
