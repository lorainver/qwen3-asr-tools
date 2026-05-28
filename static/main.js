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

    // 增量 Markdown 解析段落缓存
    let paragraphsCache = [];

    /**
     * 高性能增量防抖 Markdown 解析渲染引擎
     * 对未闭合的代码块和公式提供精美的高科技防抖包裹效果，其余部分使用增量缓存渲染
     */
    function renderParagraphsIncremental(text, isGenerating) {
        if (!text) return '';
        
        // 分割段落
        const paragraphs = text.split('\n\n');
        let answerHtml = '';

        // 比对并更新缓存
        for (let i = 0; i < paragraphs.length; i++) {
            const pText = paragraphs[i];
            const isLast = i === paragraphs.length - 1;

            if (!isLast) {
                // 历史段落：查表缓存
                if (paragraphsCache[i] && paragraphsCache[i].raw === pText) {
                    answerHtml += paragraphsCache[i].rendered;
                } else {
                    const rendered = `<div class="p-markdown">${renderMarkdown(pText)}</div>`;
                    paragraphsCache[i] = { raw: pText, rendered: rendered };
                    answerHtml += rendered;
                }
            } else {
                // 活跃段落（最后一段）：频繁变动，不存长期缓存，直接实时防抖渲染
                let renderedLast = '';
                if (isGenerating) {
                    const codeBlockCount = (pText.match(/```/g) || []).length;
                    const isCodeBlockUnclosed = codeBlockCount % 2 === 1;

                    const mathBlockCount = (pText.match(/\$\$/g) || []).length;
                    const isMathBlockUnclosed = mathBlockCount % 2 === 1;

                    if (isCodeBlockUnclosed) {
                        const lastCodeIndex = pText.lastIndexOf('```');
                        const preCodeText = pText.substring(0, lastCodeIndex);
                        const codeBlockText = pText.substring(lastCodeIndex + 3);
                        
                        const matchLang = codeBlockText.match(/^([a-zA-Z0-9+#-]+)?\n?/);
                        const lang = matchLang ? (matchLang[1] || '') : '';
                        const codeContent = codeBlockText.substring(lang.length).replace(/^\n/, '');

                        const renderedPre = renderMarkdown(preCodeText);
                        renderedLast = `<div class="p-markdown">${renderedPre}</div>` +
                            `<div class="incremental-code-block">` +
                                `<div class="code-block-header">` +
                                    `<span class="code-lang-tag">${(lang || 'CODE').toUpperCase()}</span>` +
                                    `<span class="pulse-dot"></span>` +
                                    `<span class="status-text">⚙️ 正在输出代码...</span>` +
                                `</div>` +
                                `<pre class="hljs"><code>${escapeHtmlForCode(codeContent)}</code></pre>` +
                            `</div>`;
                    } else if (isMathBlockUnclosed) {
                        const lastMathIndex = pText.lastIndexOf('$$');
                        const preMathText = pText.substring(0, lastMathIndex);
                        const mathContent = pText.substring(lastMathIndex + 2);

                        const renderedPre = renderMarkdown(preMathText);
                        renderedLast = `<div class="p-markdown">${renderedPre}</div>` +
                            `<div class="incremental-math-block">` +
                                `<div class="math-block-header">⚙️ 正在输出数学公式...</div>` +
                                `<div class="math-preview-content">$$ ${escapeHtmlForCode(mathContent)}</div>` +
                            `</div>`;
                    } else {
                        renderedLast = `<div class="p-markdown">${renderMarkdown(pText)}</div>`;
                    }
                } else {
                    renderedLast = `<div class="p-markdown">${renderMarkdown(pText)}</div>`;
                }
                answerHtml += renderedLast;
            }
        }
        
        // 缓存截断，防多余段落堆积
        if (paragraphsCache.length > paragraphs.length - 1) {
            paragraphsCache.length = Math.max(0, paragraphs.length - 1);
        }

        return answerHtml;
    }

    function escapeHtmlForCode(text) {
        if (!text) return '';
        return text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    /**
     * 渲染 Markdown 文本为 HTML
     * 支持:标准 Markdown + KaTeX 数学公式 + Mermaid 图表
     * @param {string} text - 原始 Markdown 文本
     * @returns {string} 渲染后的 HTML
     */
    function renderMarkdown(text) {
        if (!text) return '';

        // 1. 保护 Mermaid 代码块,避免被 marked 解析
        const mermaidBlocks = [];
        text = text.replace(/```mermaid\n([\s\S]*?)```/g, (match, code) => {
            const placeholder = `%%MERMAID_${mermaidBlocks.length}%%`;
            mermaidBlocks.push(code.trim());
            return placeholder;
        });

        // 2. 保护数学公式,避免被 marked 解析
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

        // 5. 还原 Mermaid 占位符为容器(异步渲染)
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
     * 解析 <think>...</think> 标签,返回 { thinking, answer }
     */
    /**
     * 解析所有思考标签,返回分段数组(支持多思考块交替)
     * 如分块翻译时每块都有思考过程:text, thinking, text, thinking, text...
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
     * 渲染包含思考过程的消息(支持多思考块交替)
     * @param {string} text - 原始文本(含 <think> 标签)
     * @param {boolean} forceOpen - 生成中强制展开思考块
     * @param {object} counterRef - 可选的计数器引用 { value: number }。用于在多段分块渲染时保持全局连续的思考序号递增计数。
     */
    function renderWithThinking(text, forceOpen = false, counterRef = null) {
        const segments = parseThinking(text);
        if (!segments.length) return '';

        let html = '';
        // 如果外部传入了 counterRef，则累加外部计数器，否则使用内部独立的局部计数器
        let localCounter = counterRef || { value: 0 };

        for (let i = 0; i < segments.length; i++) {
            const seg = segments[i];

            if (seg.type === 'thinking') {
                const c = seg.content.trim();
                if (!c) continue;
                localCounter.value++;
                const openAttr = forceOpen ? ' open' : '';
                html += `<div class="thinking-block"><details${openAttr}><summary>💭 思考过程 #${localCounter.value} (点击展开)</summary><div class="thinking-content">${renderMarkdown(c)}</div></details></div>`;
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

    // Ollama Status
    const ollamaDot = document.getElementById('ollama-status-dot');
    const ollamaText = document.getElementById('ollama-status-text');
    const ollamaDetails = document.getElementById('ollama-details');
    const ollamaModelName = document.getElementById('ollama-model-name');
    const ollamaVramRatio = document.getElementById('ollama-vram-ratio');
    const ollamaRamInfo = document.getElementById('ollama-ram-info');
    const ollamaVramBar = document.getElementById('ollama-vram-bar');

    // 模型选择
    const selectModel = document.getElementById('select-model');
    const selectModelCategory = document.getElementById('select-model-category');
    const currentModelTag = document.getElementById('current-model-tag');

    // 总结卡片
    const btnSummarize = document.getElementById('btn-summarize');
    const btnNewTask = document.getElementById('btn-new-task');
    const meetingText = document.getElementById('meeting-text');
    const sumProgCont = document.getElementById('sum-progress-container');
    const sumStatus = document.getElementById('sum-status');
    const sumResult = document.getElementById('sum-result');
    const sumAnalyticsBar = document.getElementById('sum-analytics-bar');
    const sumAnalyticsText = document.getElementById('sum-analytics-text');
    const sumAnalyticsFill = document.getElementById('sum-analytics-fill');

    // 声音设计水晶播放器 DOM 元素
    const voiceAudio = document.getElementById('voice-audio');
    const btnVoicePlayPause = document.getElementById('btn-voice-play-pause');
    const voiceProgressContainer = document.getElementById('voice-progress-container');
    const voiceProgressFill = document.getElementById('voice-progress-fill');
    const voiceTimeDisplay = document.getElementById('voice-time-display');

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
    const transLanguage = document.getElementById('trans-language');
    const transModelSize = document.getElementById('trans-model-size');

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
    // 精致侧滑历史抽屉 DOM
    const btnToggleHistory = document.getElementById('btn-toggle-history');
    const btnSaveChat = document.getElementById('btn-save-chat');
    const historyDrawer = document.getElementById('history-drawer');
    const drawerOverlay = document.getElementById('drawer-overlay');
    const drawerContent = document.getElementById('drawer-content');
    const btnCloseDrawer = document.getElementById('btn-close-drawer');
    const drawerSearch = document.getElementById('drawer-search');
    const drawerHistoryList = document.getElementById('drawer-history-list');
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

            // 如果使用了 Mermaid,可能需要重新渲染(有些图表颜色是硬编码的)
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
                // 注意:这里使用的是 /api/shutdown 或 /api/release_gpu,根据后端实际接口调整
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

        // 按类别分组渲染(如果是 'all' 模式)
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

                // 改进切换逻辑:如果当前模型不具备视觉能力,则提示或自动切换
                // 我们通过模型 ID 是否包含 'vl' 来快速判定
                if (!currentModelId.toLowerCase().includes('vl') && selectModel) {
                    // 优先寻找远程 VL 模型,如果没有再选本地
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
        // 1. 轮询 AI Worker 状态
        try {
            const resp = await fetch('/api/worker_status');
            const data = await resp.json();
            if (workerDot && workerText) {
                if (data.respawning) {
                    workerDot.style.background = '#ff9800'; // 橙色警告
                    workerText.textContent = '自动恢复中';
                    workerText.style.color = '#ff9800';
                    if (workerUptime) {
                        workerUptime.textContent = '后端异常，自动拉起中...';
                        workerUptime.style.color = '#ff9800';
                    }
                    if (!window.lastRespawning) {
                        window.lastRespawning = true;
                        showToast("⚠️ 检测到后端 AI 服务异常，正在自动拉起...", 4000);
                    }
                } else if (data.running) {
                    workerDot.style.background = '#4caf50';
                    workerText.textContent = '运行中';
                    workerText.style.color = '#4caf50';
                    if (workerUptime) {
                        const mins = Math.floor(data.uptime_seconds / 60);
                        const secs = data.uptime_seconds % 60;
                        workerUptime.textContent = `已运行 ${mins}分${secs}秒`;
                        workerUptime.style.color = '';
                    }
                    if (window.lastRespawning) {
                        window.lastRespawning = false;
                        showToast("✅ 后端 AI 服务已自动恢复成功！", 3000);
                    }
                } else {
                    workerDot.style.background = '#555';
                    workerText.textContent = '○ 未启动';
                    workerText.style.color = '#aaa';
                    if (workerUptime) {
                        workerUptime.textContent = data.respawn_message || '';
                        workerUptime.style.color = '#ef4444';
                    }
                    if (window.lastRespawning) {
                        window.lastRespawning = false;
                        showToast("❌ 后端 AI 服务多次拉起失败，请释放显存后重试", 4000);
                    }
                }
            }
        } catch (e) {
            // 忽略轮询错误
        }

        // 2. 轮询 Ollama 运行状态与模型分配
        try {
            const resp = await fetch('/api/ollama_status');
            const data = await resp.json();
            if (ollamaDot && ollamaText) {
                if (data.running) {
                    ollamaDot.style.background = '#0ea5e9'; // 在线天蓝色
                    ollamaText.textContent = data.has_model ? '模型运行中' : '服务在线 (空闲)';
                    ollamaText.style.color = '#0ea5e9';

                    if (data.has_model && data.models && data.models.length > 0) {
                        if (ollamaDetails) ollamaDetails.style.display = 'block';
                        const firstModel = data.models[0];
                        if (ollamaModelName) ollamaModelName.textContent = firstModel.name;
                        if (ollamaVramRatio) ollamaVramRatio.textContent = `${firstModel.vram_percent}%`;
                        if (ollamaRamInfo) ollamaRamInfo.textContent = `CPU: ${firstModel.ram_gb.toFixed(1)}G / GPU: ${firstModel.vram_gb.toFixed(1)}G`;
                        if (ollamaVramBar) ollamaVramBar.style.width = `${firstModel.vram_percent}%`;
                    } else {
                        if (ollamaDetails) ollamaDetails.style.display = 'none';
                    }
                } else {
                    ollamaDot.style.background = '#555'; // 未启动灰色
                    ollamaText.textContent = '○ 未启动';
                    ollamaText.style.color = '#aaa';
                    if (ollamaDetails) ollamaDetails.style.display = 'none';
                }
            }
        } catch (e) {
            // 忽略轮询错误
        }
    }, 2000);

    // === 辅助函数:显示浮动提示 (Toast) ===
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
                            <div style="font-size: 0.78em; color: #64748b; margin-top: 10px; text-align: center;">💡 提示:点击行可直接复制 ID。推荐优先使用 <span style="color: #38bdf8;">WASAPI</span> 驱动。</div>`;
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

    // 语言选择下拉框控制(仅翻译模式显示)
    const promptTypeSelect = document.getElementById('prompt-type');
    const targetLangSelect = document.getElementById('target-lang');

    if (promptTypeSelect && targetLangSelect) {
        // 初始化:根据当前选择显示/隐藏
        targetLangSelect.classList.toggle('hidden', promptTypeSelect.value !== 'translate');

        // 监听变化
        promptTypeSelect.addEventListener('change', () => {
            targetLangSelect.classList.toggle('hidden', promptTypeSelect.value !== 'translate');
        });
    }

    if (btnSummarize) {
        btnSummarize.addEventListener('click', async () => {
            const text = meetingText.value.trim();
            if (!text) return alert("请先粘贴文本内容!");

            const promptType = document.getElementById('prompt-type').value;
            if (promptType === 'voice_design') {
                const voicePrompt = document.getElementById('prompt-preview').value.trim();
                if (!voicePrompt) return alert("声音提示词不能为空!");
                
                meetingText.classList.add('hidden');
                btnSummarize.classList.add('hidden');
                sumProgCont.classList.remove('hidden');
                sumStatus.innerText = "🎙️ 正在进行零样本声音设计与语音合成，请稍候...";
                
                // 清理可能存在的上一次复制按钮，隐藏结果框与分析条
                const existCopyBtn = sumResult.parentNode.querySelector('.btn-copy-result');
                if (existCopyBtn) existCopyBtn.remove();
                sumResult.classList.add('hidden');
                sumResult.innerHTML = '';
                if (sumAnalyticsBar) sumAnalyticsBar.classList.add('hidden');
                
                // 隐藏上一次生成的播放面板
                const voicePlayerPanel = document.getElementById('voice-player-panel');
                if (voicePlayerPanel) voicePlayerPanel.classList.add('hidden');
                
                try {
                    const response = await fetch('/api/voice_design', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ voice_prompt: voicePrompt, text: text })
                    });
                    const result = await response.json();
                    
                    sumProgCont.classList.add('hidden');
                    
                    if (result.status === 'success') {
                        if (voicePlayerPanel) {
                            voicePlayerPanel.classList.remove('hidden');
                            const voiceAudio = document.getElementById('voice-audio');
                            const btnDownloadVoice = document.getElementById('btn-download-voice');
                            if (voiceAudio) {
                                voiceAudio.src = result.url;
                                voiceAudio.play().catch(e => console.log("自动播放被浏览器拦截:", e));
                            }
                            if (btnDownloadVoice) {
                                btnDownloadVoice.href = result.url;
                            }
                        }
                        btnNewTask.classList.remove('hidden');
                    } else {
                        alert("❌ 声音合成失败: " + result.message);
                        meetingText.classList.remove('hidden');
                        btnSummarize.classList.remove('hidden');
                    }
                } catch (error) {
                    sumProgCont.classList.add('hidden');
                    alert("🚨 声音合成请求出错: " + error.message);
                    meetingText.classList.remove('hidden');
                    btnSummarize.classList.remove('hidden');
                }
                return; // 拦截常规总结流程
            }

            meetingText.classList.add('hidden');
            btnSummarize.classList.add('hidden');
            sumProgCont.classList.remove('hidden');
            sumResult.classList.remove('hidden');
            sumResult.innerText = "";
            if (sumAnalyticsBar) sumAnalyticsBar.classList.add('hidden');

            const targetLang = targetLangSelect && promptType === 'translate' ? targetLangSelect.value : null;
            const parallel = document.getElementById('sum-parallel')?.checked || false;

            const requestBody = { text: text, prompt_type: promptType, parallel: parallel };
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
                let chunkResults = [];  // 分块处理：每段独立累积
                let currentChunkText = '';  // 当前分块的流式文本
                // 切换为 Markdown 渲染模式
                sumResult.classList.add('markdown-mode');
                sumResult.classList.add('markdown-content');
                sumResult.innerText = '';

                let buffer = ''; // 缓存未接收完整的行
                while (true) {
                    const { value, done } = await reader.read();
                    if (done) {
                        if (buffer.trim()) {
                            try {
                                const data = JSON.parse(buffer.trim());
                                processLine(data);
                            } catch (e) {
                                console.error('流结束时的残留数据解析失败:', e);
                            }
                        }
                        break;
                    }
                    
                    buffer += decoder.decode(value, { stream: true });
                    let boundary = buffer.indexOf('\n');
                    while (boundary !== -1) {
                        const line = buffer.substring(0, boundary).trim();
                        buffer = buffer.substring(boundary + 1);
                        if (line) {
                            try {
                                const data = JSON.parse(line);
                                processLine(data);
                            } catch (e) {
                                console.error('行 JSON 解析失败:', e, line);
                            }
                        }
                        boundary = buffer.indexOf('\n');
                    }
                }
                
                function processLine(data) {
                    if (data.status === 'processing') {
                        sumStatus.innerText = data.message;
                    } else if (data.status === 'streaming' && data.delta) {
                        // 流式增量渲染
                        fullText += data.delta;
                        currentChunkText += data.delta;
                        sumResult.dataset.rawContent = fullText;
                        
                        // 分块处理：已完成的段 + 当前正在流的段
                        if (chunkResults.length > 0) {
                            // 有已完成的段，分段渲染
                            let html = '';
                            let globalCounter = { value: 0 };
                            chunkResults.forEach(r => {
                                html += `<div class="translate-chunk">${renderWithThinking(r, false, globalCounter)}</div>`;
                            });
                            html += `<div class="translate-chunk active">${renderWithThinking(currentChunkText, true, globalCounter)}</div>`;
                            sumResult.innerHTML = html;
                        } else {
                            // 第一段，直接渲染
                            sumResult.innerHTML = renderWithThinking(fullText, true);
                        }
                        
                        // 自动滚动到底部
                        sumResult.scrollTop = sumResult.scrollHeight;
                    } else if (data.status === 'chunk_complete') {
                        // 一段处理完成，存入已完成列表
                        chunkResults.push(data.chunk_result || currentChunkText);
                        currentChunkText = '';
                    } else if (data.status === 'done') {
                        sumProgCont.classList.add('hidden');
                        // 最终渲染：分段渲染每段翻译
                        if (chunkResults.length > 0) {
                            // 有分块：每段独立渲染
                            // 如果有残余 of currentChunkText，加入最后一段
                            if (currentChunkText.trim()) {
                                chunkResults.push(currentChunkText);
                            }
                            let html = '';
                            let globalCounter = { value: 0 };
                            chunkResults.forEach((r, idx) => {
                                html += `<div class="translate-chunk"><div class="translate-chunk-label">第 ${idx+1}/${chunkResults.length} 段</div>${renderWithThinking(r, false, globalCounter)}</div>`;
                            });
                            sumResult.innerHTML = html;
                            sumResult.dataset.rawContent = chunkResults.join('\n\n');
                        } else {
                            // 无分块：直接渲染
                            sumResult.innerHTML = renderWithThinking(data.result, false);
                            sumResult.dataset.rawContent = data.result || fullText;
                        }

                        // 计算并展示摘要统计看板
                        let copyText = '';
                        try {
                            const answerEls = sumResult.querySelectorAll('.answer-content');
                            copyText = Array.from(answerEls)
                                .map(el => el.innerText.trim())
                                .filter(t => t)
                                .join('\n\n');
                        } catch (e) {}
                        if (!copyText) {
                            copyText = sumResult.innerText.trim();
                        }

                        if (sumAnalyticsBar && sumAnalyticsText && sumAnalyticsFill) {
                            const inputLen = text.length;
                            const outputLen = copyText.length;
                            
                            function getEstTokens(str) {
                                if (!str) return 0;
                                let zh = 0;
                                for (let i = 0; i < str.length; i++) {
                                    if (str.charCodeAt(i) >= 0x4e00 && str.charCodeAt(i) <= 0x9fff) {
                                        zh++;
                                    }
                                }
                                const other = str.length - zh;
                                return Math.round(zh * 1.5 + other / 4);
                            }

                            const inputTokens = getEstTokens(text);
                            const outputTokens = getEstTokens(copyText);

                            const compressRatio = (inputLen / Math.max(1, outputLen)).toFixed(1);
                            const compressPct = Math.max(0, Math.min(100, (1 - outputLen / inputLen) * 100)).toFixed(1);

                            sumAnalyticsText.innerHTML = `输入: <strong>${(inputLen/1000).toFixed(1)}K</strong> 字 (${(inputTokens/1000).toFixed(1)}K Token) ➜ 摘要: <strong>${(outputLen/1000).toFixed(1)}K</strong> 字 (${(outputTokens/1000).toFixed(1)}K Token) | 提炼率: <strong>${compressPct}%</strong> (约 <strong>${compressRatio}x</strong> 压缩)`;
                            sumAnalyticsFill.style.width = `${compressPct}%`;
                            sumAnalyticsBar.title = `智库摘要内容精炼指标：为您压缩了 ${compressPct}% 的文章篇幅，提炼出核心骨架。`;
                            sumAnalyticsBar.classList.remove('hidden');
                        }

                        // 添加复制按钮（只复制正文，不含思考块）
                        const sumCopyBtn = document.createElement('button');
                        sumCopyBtn.className = 'btn-icon btn-copy-result';
                        sumCopyBtn.innerHTML = '📋 复制';
                        sumCopyBtn.onclick = async () => {
                            try {
                                let toCopyText = '';
                                const rawMarkdown = sumResult.dataset.rawContent || '';
                                if (rawMarkdown) {
                                    // 完美剥离 <think>...</think> 标签，保留最纯正的原始 Markdown
                                    toCopyText = rawMarkdown.replace(/<think>[\s\S]*?<\/think>/gi, '').trim();
                                } else {
                                    const answerEls = sumResult.querySelectorAll('.answer-content');
                                    toCopyText = Array.from(answerEls)
                                        .map(el => el.innerText.trim())
                                        .filter(t => t)
                                        .join('\n\n') || sumResult.innerText.trim();
                                }
                                await navigator.clipboard.writeText(toCopyText);
                                sumCopyBtn.innerHTML = '✅ 已复制';
                                sumCopyBtn.classList.add('copied');
                                setTimeout(() => {
                                    sumCopyBtn.innerHTML = '📋 复制';
                                    sumCopyBtn.classList.remove('copied');
                                }, 2000);
                            } catch (e) {
                                console.error('复制失败:', e);
                            }
                        };
                        sumResult.parentNode.appendChild(sumCopyBtn);
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
                        // 显示「新建任务」按钮
                        btnNewTask.classList.remove('hidden');
                    } else if (data.status === 'error') {
                        sumProgCont.classList.add('hidden');
                        sumResult.innerText = "❌ " + data.message;
                        btnNewTask.classList.remove('hidden');
                    }
                }
            } catch (error) {
                sumProgCont.classList.add('hidden');
                sumStatus.innerText = "处理出错: " + error.message;
                btnNewTask.classList.remove('hidden');
            }
        });
    }

    // 新建任务按钮：恢复输入区
    if (btnNewTask) {
        btnNewTask.addEventListener('click', () => {
            sumResult.classList.add('hidden');
            sumResult.innerHTML = '';
            // 清理可能存在的复制按钮
            const existCopyBtn = sumResult.parentNode.querySelector('.btn-copy-result');
            if (existCopyBtn) existCopyBtn.remove();
            if (sumAnalyticsBar) sumAnalyticsBar.classList.add('hidden');
            sumProgCont.classList.add('hidden');
            btnNewTask.classList.add('hidden');

            // 隐藏声音播放器并重置
            const voicePlayerPanel = document.getElementById('voice-player-panel');
            if (voicePlayerPanel) {
                voicePlayerPanel.classList.add('hidden');
                const voiceAudio = document.getElementById('voice-audio');
                if (voiceAudio) {
                    voiceAudio.pause();
                    voiceAudio.src = '';
                }
            }

            meetingText.classList.remove('hidden');
            btnSummarize.classList.remove('hidden');
            meetingText.focus();
        });
    }

    // === 2.5 声音设计水晶播放器控制逻辑 ===
    if (voiceAudio && btnVoicePlayPause) {
        // 播放与暂停切换
        btnVoicePlayPause.addEventListener('click', () => {
            if (voiceAudio.paused) {
                voiceAudio.play().catch(e => console.log("播放失败:", e));
            } else {
                voiceAudio.pause();
            }
        });

        // 监听播放状态更改按钮图标
        voiceAudio.addEventListener('play', () => {
            btnVoicePlayPause.innerHTML = '❚❚';
            btnVoicePlayPause.title = '暂停';
        });

        voiceAudio.addEventListener('pause', () => {
            btnVoicePlayPause.innerHTML = '▶';
            btnVoicePlayPause.title = '播放';
        });

        // 辅助时间格式化函数 (e.g. 75 -> "01:15")
        function formatAudioTime(secs) {
            if (isNaN(secs) || secs === Infinity) return "00:00";
            const m = Math.floor(secs / 60).toString().padStart(2, '0');
            const s = Math.floor(secs % 60).toString().padStart(2, '0');
            return `${m}:${s}`;
        }

        // 监听音频加载，显示总时长
        voiceAudio.addEventListener('loadedmetadata', () => {
            if (voiceTimeDisplay) {
                voiceTimeDisplay.textContent = `00:00 / ${formatAudioTime(voiceAudio.duration)}`;
            }
        });

        // 监听播放进度实时流动进度条与时间显示
        voiceAudio.addEventListener('timeupdate', () => {
            if (!voiceAudio.duration) return;
            const pct = (voiceAudio.currentTime / voiceAudio.duration) * 100;
            if (voiceProgressFill) {
                voiceProgressFill.style.width = `${pct}%`;
            }
            if (voiceTimeDisplay) {
                voiceTimeDisplay.textContent = `${formatAudioTime(voiceAudio.currentTime)} / ${formatAudioTime(voiceAudio.duration)}`;
            }
        });

        // 播放结束自动复位
        voiceAudio.addEventListener('ended', () => {
            if (voiceProgressFill) {
                voiceProgressFill.style.width = '0%';
            }
            if (voiceTimeDisplay) {
                voiceTimeDisplay.textContent = `00:00 / ${formatAudioTime(voiceAudio.duration)}`;
            }
            btnVoicePlayPause.innerHTML = '▶';
        });

        // 进度条可点击/拖拽调整进度
        if (voiceProgressContainer) {
            voiceProgressContainer.addEventListener('click', (e) => {
                if (!voiceAudio.duration) return;
                const rect = voiceProgressContainer.getBoundingClientRect();
                const clickX = e.clientX - rect.left;
                const width = rect.width;
                const pct = Math.max(0, Math.min(1, clickX / width));
                voiceAudio.currentTime = pct * voiceAudio.duration;
            });
        }
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
        if (document.querySelector('.trans-options')) document.querySelector('.trans-options').classList.add('hidden');
        dropZone.classList.add('hidden');
        transProgCont.classList.remove('hidden');
        transStatus.innerText = "正在上传并启动模型...";
        transBar.style.width = "5%";
        const formData = new FormData();
        formData.append('file', file);
        if (transLanguage) formData.append('language', transLanguage.value);
        if (transModelSize) formData.append('model_size', transModelSize.value);
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
            if (!path) return alert("请输入完整路径!");
            if (document.querySelector('.path-input-mode')) document.querySelector('.path-input-mode').classList.add('hidden');
            if (document.querySelector('.trans-options')) document.querySelector('.trans-options').classList.add('hidden');
            dropZone.classList.add('hidden');
            transProgCont.classList.remove('hidden');
            transStatus.innerText = "正在定位文件并启动...";
            transBar.style.width = "5%";
            const formData = new FormData();
            formData.append('path', path);
            if (transLanguage) formData.append('language', transLanguage.value);
            if (transModelSize) formData.append('model_size', transModelSize.value);
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
        let buffer = '';
        while (true) {
            const { value, done } = await reader.read();
            if (done) {
                if (buffer.trim()) {
                    try {
                        const data = JSON.parse(buffer.trim());
                        processTranscribeLine(data);
                    } catch (e) { }
                }
                break;
            }
            
            buffer += decoder.decode(value, { stream: true });
            let boundary = buffer.indexOf('\n');
            while (boundary !== -1) {
                const line = buffer.substring(0, boundary).trim();
                buffer = buffer.substring(boundary + 1);
                if (line) {
                    try {
                        const data = JSON.parse(line);
                        processTranscribeLine(data);
                    } catch (e) {
                        console.error('ASR 行 JSON 解析失败:', e, line);
                    }
                }
                boundary = buffer.indexOf('\n');
            }
        }

        function processTranscribeLine(data) {
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

    let messages = [];
    let currentChatPath = null; // 【新增】当前长对话的历史 JSON 文件路径，用于原地覆盖式增量保存
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
            paragraphsCache = []; // 清空增量 Markdown 解析缓存
            // 如果当前有对话内容，在后台静默备份保存，绝对不让 UI 等待 AI 标题生成
            if (messages.length > 1) {
                // 深度复制 messages，防止在保存过程中被 messages = [] 瞬间清空导致上传空数据
                const backupMessages = JSON.parse(JSON.stringify(messages));
                const backupPath = currentChatPath;
                const backupTitle = currentChatTitle;
                
                // 启动后台静默备份
                (async () => {
                    try {
                        // 提取用户首条消息
                        const firstUserMsgObj = backupMessages.find(m => m.role === 'user')?.content || "新对话";
                        let userText = "新对话";
                        if (Array.isArray(firstUserMsgObj)) {
                            const textPart = firstUserMsgObj.find(part => part.type === 'text');
                            if (textPart) userText = textPart.text;
                        } else {
                            userText = firstUserMsgObj;
                        }
                        
                        let saveTitle = backupTitle;
                        if (!backupPath || backupTitle === "新对话") {
                            saveTitle = userText.substring(0, 10) || "新对话";
                        }
                        
                        // 1. 初次落盘
                        const saveResp = await fetch('/api/history/save', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                title: saveTitle,
                                messages: backupMessages,
                                path: backupPath || undefined
                            })
                        });
                        const saveResult = await saveResp.json();
                        
                        // 2. 如果是新建对话且保存成功，且原本没有智能标题，后台继续顺便生成个智能标题
                        if (saveResult.status === 'success' && (!backupPath || backupTitle === "新对话")) {
                            const savedPath = saveResult.path;
                            try {
                                const titlePrompt = `请为以下对话生成一个5字以内的简短标题。对话内容:${userText.substring(0, 100)}`;
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
                                    const generatedTitle = data.response.replace(/[#"'\n\r]/g, '').substring(0, 15).trim() || saveTitle;
                                    await fetch('/api/history/save', {
                                        method: 'POST',
                                        headers: { 'Content-Type': 'application/json' },
                                        body: JSON.stringify({
                                            title: generatedTitle,
                                            messages: backupMessages,
                                            path: savedPath
                                        })
                                    });
                                }
                            } catch (e) {
                                console.warn('后台备份生成智能标题失败:', e);
                            }
                        }
                    } catch (e) {
                        console.error('后台静默备份失败:', e);
                    }
                })();
                
                showToast("🧹 已开启全新对话 (历史已在后台备份)");
            }

            // 0ms 瞬间清空重置界面与状态
            messages = [];
            currentChatPath = null;
            currentChatTitle = "新对话";
            chatHistory.innerHTML = "";
            appendMessage('assistant', "你好！我是你的本地 AI 助理。你可以问我任何问题，或者让我帮你分析处理过的文本。");
            streamingAudioQueue.clear();
            
            // 重置上下文指示器
            updateContextIndicator(0, 0, 0);
        });
    }

    // === 5.1 侧滑历史对话抽屉管理逻辑 ===

    // 打开/收起侧滑面板
    if (btnToggleHistory) {
        btnToggleHistory.addEventListener('click', () => {
            const isActive = historyDrawer.classList.toggle('active');
            if (isActive) {
                drawerContent.classList.add('active');
                // 打开时加载列表
                loadHistoryList(drawerSearch ? drawerSearch.value.trim() : '');
            } else {
                drawerContent.classList.remove('active');
            }
        });
    }

    // 点击遮罩层关闭抽屉
    if (drawerOverlay) {
        drawerOverlay.addEventListener('click', () => {
            historyDrawer.classList.remove('active');
            drawerContent.classList.remove('active');
        });
    }

    // 点击关闭按钮关闭抽屉
    if (btnCloseDrawer) {
        btnCloseDrawer.addEventListener('click', () => {
            historyDrawer.classList.remove('active');
            drawerContent.classList.remove('active');
        });
    }

    // 主动手动保存当前对话
    if (btnSaveChat) {
        btnSaveChat.addEventListener('click', async () => {
            if (messages.length <= 1) {
                showToast("⚠️ 当前对话为空，无需保存");
                return;
            }
            const originalText = btnSaveChat.innerHTML;
            btnSaveChat.innerHTML = '💾 保存中...';
            btnSaveChat.disabled = true;
            try {
                await saveCurrentChat(false, false);
            } finally {
                btnSaveChat.innerHTML = originalText;
                btnSaveChat.disabled = false;
            }
        });
    }

    // 抽屉内历史搜索框 (防抖检索过滤)
    if (drawerSearch) {
        let searchDebounce = null;
        drawerSearch.addEventListener('input', (e) => {
            clearTimeout(searchDebounce);
            searchDebounce = setTimeout(() => {
                loadHistoryList(e.target.value.trim());
            }, 300);
        });
    }

    // 动态渲染历史卡片列表
    async function loadHistoryList(searchQuery = '') {
        if (!drawerHistoryList) return;
        try {
            const params = new URLSearchParams({ limit: '100', offset: '0' });
            if (searchQuery) params.set('query', searchQuery);
            const resp = await fetch(`/api/history/list?${params}`);
            const data = await resp.json();
            const list = data.items || data; // 兼容旧格式及分页格式

            drawerHistoryList.innerHTML = '';

            if (!list || list.length === 0) {
                // 优雅的占位图/文
                drawerHistoryList.innerHTML = `
                    <div class="history-empty">
                        <div class="empty-icon">📭</div>
                        <div class="empty-text">无相关对话历史</div>
                    </div>
                `;
                return;
            }

            list.forEach(item => {
                const isCurrent = item.path === currentChatPath;
                
                // 创建卡片容器
                const card = document.createElement('div');
                card.className = `history-card${isCurrent ? ' active-chat' : ''}`;
                card.dataset.path = item.path;
                card.dataset.title = item.title;

                // 卡片主内容区
                const info = document.createElement('div');
                info.className = 'card-info';

                const titleEl = document.createElement('div');
                titleEl.className = 'card-title';
                titleEl.textContent = item.title;

                const metaEl = document.createElement('div');
                metaEl.className = 'card-meta';
                // 格式化一下时间（如果有）
                let timeStr = '';
                if (item.timestamp) {
                    try {
                        const date = new Date(item.timestamp);
                        timeStr = date.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
                    } catch (e) {
                        timeStr = item.timestamp;
                    }
                } else if (item.modified_str) {
                    timeStr = item.modified_str;
                }
                metaEl.textContent = `💬 ${item.msg_count || 0} 轮对话  ·  ${timeStr}`;

                info.appendChild(titleEl);
                info.appendChild(metaEl);
                card.appendChild(info);

                // 垃圾桶按钮 (悬浮淡入)
                const deleteBtn = document.createElement('button');
                deleteBtn.className = 'btn-delete-card';
                deleteBtn.innerHTML = '🗑️';
                deleteBtn.title = '删除此对话';
                deleteBtn.addEventListener('click', async (e) => {
                    e.stopPropagation(); // 阻止事件冒泡到卡片点击加载
                    
                    if (!confirm(`确定彻底删除此对话？\n《${item.title}》`)) return;

                    try {
                        const delResp = await fetch(`/api/history/delete?path=${encodeURIComponent(item.path)}`, { method: 'DELETE' });
                        const result = await delResp.json();
                        if (result.status === 'success') {
                            showToast('🗑️ 对话已删除');
                            // 如果删除了当前正在聊天的文件，重置全局路径
                            if (isCurrent) {
                                currentChatPath = null;
                                currentChatTitle = "新对话";
                            }
                            // 静默刷新列表
                            loadHistoryList(drawerSearch ? drawerSearch.value.trim() : '');
                        } else {
                            showToast('❌ 删除失败: ' + result.message);
                        }
                    } catch (err) {
                        showToast('❌ 删除失败: ' + err.message);
                    }
                });
                card.appendChild(deleteBtn);

                // 点击卡片：加载历史
                card.addEventListener('click', async () => {
                    try {
                        card.style.opacity = '0.7'; // 给予点击反馈
                        const loadResp = await fetch(`/api/history/load?path=${encodeURIComponent(item.path)}`);
                        const loadData = await loadResp.json();
                        if (loadData.messages) {
                            paragraphsCache = []; // 重新加载历史，必须完全重置段落解析缓存
                            messages = loadData.messages;
                            currentChatPath = item.path;
                            currentChatTitle = loadData.title || item.title;
                            
                            // 渲染消息
                            chatHistory.innerHTML = "";
                            messages.forEach(msg => {
                                appendMessage(msg.role, msg.content);
                            });
                            showToast(`📂 已加载: ${currentChatTitle}`);
                            
                            // 关闭侧滑抽屉
                            historyDrawer.classList.remove('active');
                            drawerContent.classList.remove('active');
                        }
                    } catch (err) {
                        showToast('❌ 加载失败: ' + err.message);
                        card.style.opacity = '1';
                    }
                });

                drawerHistoryList.appendChild(card);
            });
        } catch (e) {
            console.error('加载历史列表失败:', e);
            if (drawerHistoryList) {
                drawerHistoryList.innerHTML = '<div class="history-empty"><div class="empty-text">⚠️ 列表加载失败</div></div>';
            }
        }
    }

    /**
     * 保存当前对话到本地磁盘。
     * 支持覆盖式增量自动保存，防止对话碎片文件泛滥。
     * @param {boolean} isAuto - 是否是后台自动保存
     * @param {boolean} silent - 是否静默，不弹出 Toast
     */
    async function saveCurrentChat(isAuto = false, silent = false) {
        if (messages.length <= 1) return;

        // 1. 获取用户首条消息作为标题基础
        const firstUserMsgObj = messages.find(m => m.role === 'user')?.content || "新对话";
        let userText = "新对话";
        if (Array.isArray(firstUserMsgObj)) {
            const textPart = firstUserMsgObj.find(part => part.type === 'text');
            if (textPart) userText = textPart.text;
        } else {
            userText = firstUserMsgObj;
        }

        // 2. 确定本次保存的标题
        // 如果是全新对话（currentChatPath 为空），我们先生成一个临时的前10个字的标题并进行初次落盘，
        // 然后再异步去请求 AI 生成智能标题。这样能彻底打通“秒清无卡顿”。
        let isFirstSave = !currentChatPath;
        if (isFirstSave) {
            currentChatTitle = userText.substring(0, 10) || "新对话";
        }

        try {
            // 3. 提交保存
            const saveResp = await fetch('/api/history/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    title: currentChatTitle,
                    messages: messages,
                    path: currentChatPath || undefined
                })
            });
            const saveResult = await saveResp.json();
            if (saveResult.status === 'success') {
                currentChatPath = saveResult.path; // 记录/更新当前 JSON 路径
                if (!silent) {
                    showToast(isAuto ? "💾 已自动保存草稿" : "💾 对话保存成功");
                }
                
                // 如果是第一次保存，我们在后台默默向 AI 请求个智能标题并覆盖更新
                if (isFirstSave) {
                    // 异步请求标题生成，绝不阻塞 UI
                    (async () => {
                        try {
                            const titlePrompt = `请为以下对话生成一个5字以内的简短标题。对话内容:${userText.substring(0, 100)}`;
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
                                const generatedTitle = data.response.replace(/[#"'\n\r]/g, '').substring(0, 15).trim() || currentChatTitle;
                                currentChatTitle = generatedTitle;
                                
                                // 得到 AI 标题后，默默覆盖保存一次
                                await fetch('/api/history/save', {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({
                                        title: currentChatTitle,
                                        messages: messages,
                                        path: currentChatPath
                                    })
                                });
                                // 刷新可能正处于打开状态的历史抽屉列表
                                if (historyDrawer && historyDrawer.classList.contains('active')) {
                                    loadHistoryList(drawerSearch ? drawerSearch.value.trim() : '');
                                }
                            }
                        } catch (err) {
                            console.warn('AI 生成标题失败:', err);
                        }
                    })();
                } else {
                    // 如果不是第一次保存，也静默刷新一下列表
                    if (historyDrawer && historyDrawer.classList.contains('active')) {
                        loadHistoryList(drawerSearch ? drawerSearch.value.trim() : '');
                    }
                }
            }
        } catch (e) {
            console.error('保存当前对话失败:', e);
            if (!silent) showToast("❌ 保存失败: " + e.message);
        }
    }

    // === 流式语音队列(带预加载) ===
    const streamingAudioQueue = {
        queue: [],         // [{sentence, audio, audioPromise}]
        isPlaying: false,
        currentAudio: null,

        enqueue(sentence) {
            if (!sentence.trim()) return;
            // 立即开始预加载音频(不等播放)
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
                // 等音频加载完(预加载已提前开始,通常立即可用)
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
    const SENTENCE_ENDS = '。!?.!?\n';
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

    // ========== 上下文 Token 指示器 ==========
    let contextMaxTokens = 24576; // 默认值，从后端 context 事件中动态更新

    function updateContextIndicator(currentTokens, originalTokens, trimmedCount, maxTokens) {
        const textEl = document.getElementById('context-token-text');
        const barEl = document.getElementById('context-bar-fill');
        const indicator = document.getElementById('context-indicator');
        if (!textEl || !barEl) return;

        // 后端可推送 max_tokens 配置
        if (maxTokens) contextMaxTokens = maxTokens;

        const displayTokens = currentTokens || 0;
        const pct = Math.min(100, (displayTokens / contextMaxTokens) * 100);
        const kLabel = (displayTokens / 1024).toFixed(1);
        const maxLabel = (contextMaxTokens / 1024).toFixed(0);

        textEl.textContent = `${kLabel}K / ${maxLabel}K`;
        barEl.style.width = pct + '%';

        // 颜色分级
        barEl.className = 'context-bar-fill';
        if (pct > 90) {
            barEl.classList.add('danger');
        } else if (pct > 70) {
            barEl.classList.add('warning');
        }

        // 截断提示
        if (trimmedCount > 0) {
            indicator.title = `上下文已截断 ${trimmedCount} 条旧消息 (${originalTokens}→${displayTokens} tokens)`;
        } else {
            indicator.title = `对话上下文 Token 用量`;
        }
    }

    async function sendChatMessage() {
        paragraphsCache = []; // 清空增量 Markdown 解析缓存
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
                    // 针对 8GB 显存进行优化,限制最大像素点,防止 OOM
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

        // 初始化思考容器与正文容器（双轨渲染引擎底座）
        loadingMsg.innerHTML = '<div class="thinking-container"><span class="thinking-dots">正在思考<span class="dot dot-1">.</span><span class="dot dot-2">.</span><span class="dot dot-3">.</span></span></div><div class="answer-container"></div>';
        const thinkingContainer = loadingMsg.querySelector('.thinking-container');
        const answerContainer = loadingMsg.querySelector('.answer-container');

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
            let displayedResponse = ''; // 打字机实际渲染呈现出的字符内容
            let typingQueue = [];       // 平滑打字渲染排队缓冲区
            let streamFinished = false; // 标记网络流是否已经接收完毕

            // 局部虚拟 DOM 比对双轨更新器，完全杜绝 <details> 节点在打印正文时的撕裂与重绘
            /**
             * 双轨渲染器：思考块 + 正文分离渲染
             * @param {string} text - 当前累积文本
             * @param {boolean} isGenerating - 是否处于生成中（决定思考块展开状态）
             * @param {boolean} lightweight - 轻量模式（流式中跳过 Markdown 渲染，仅做基本转义）
             */
            function updateDoubleTracks(text, isGenerating, lightweight = false) {
                const segments = parseThinking(text);
                
                // 【修复问题 2】当 parseThinking 返回空数组时，不清空容器，保留原有动画
                if (segments.length === 0) {
                    // 如果文本非空但解析不出段落（如只有 ◂think▸ 开始标签），保持现状
                    // thinking dots 动画继续显示，等后续内容到达后再更新
                    return;
                }
                
                let thinkingHtml = '';
                let answerHtml = '';
                let localCounter = 0;

                for (const seg of segments) {
                    if (seg.type === 'thinking') {
                        const c = seg.content.trim();
                        if (c) {
                            localCounter++;
                            const openAttr = isGenerating ? ' open' : '';
                            // 思考过程内容，仍可使用 light/full 渲染
                            const contentHtml = lightweight ? escapeHtml(c) : renderMarkdown(c);
                            thinkingHtml += `<div class="thinking-block"><details${openAttr}><summary>💭 思考过程 #${localCounter} (点击展开)</summary><div class="thinking-content">${contentHtml}</div></details></div>`;
                        }
                    } else {
                        // 思考之外的正文，流式期间使用我们的高性能增量防抖 Markdown 解析渲染引擎
                        const contentHtml = renderParagraphsIncremental(seg.content, isGenerating);
                        answerHtml += `<div class="answer-content">${contentHtml}</div>`;
                    }
                }

                // 核心优化：仅在 HTML 结构发生绝对变化时，才触动 innerHTML 重绘
                if (thinkingContainer.innerHTML !== thinkingHtml) {
                    thinkingContainer.innerHTML = thinkingHtml;
                }
                if (answerContainer.innerHTML !== answerHtml) {
                    answerContainer.innerHTML = answerHtml;
                }
            }
            
            /**
             * 基本HTML转义（轻量模式用）
             */
            function escapeHtml(text) {
                if (!text) return '';
                return text
                    .replace(/&/g, '&amp;')
                    .replace(/</g, '&lt;')
                    .replace(/>/g, '&gt;')
                    .replace(/"/g, '&quot;')
                    .replace(/'/g, '&#039;')
                    .replace(/\n/g, '<br>');
            }

            let typingRAF = null;
            
            function processTyping() {
                typingRAF = null;
                const queueLength = typingQueue.length;
                if (queueLength > 0) {
                    // 超频自适应打字消费算法，从物理上杜绝队列积压卡顿
                    let batchSize = 1;
                    if (queueLength > 150) {
                        // 极其严重积压，直接一次吞噬全部，瞬间追平网络
                        batchSize = queueLength;
                    } else if (queueLength > 80) {
                        // 严重积压，按 1/3 速度吞噬
                        batchSize = Math.max(8, Math.floor(queueLength / 3));
                    } else if (queueLength > 30) {
                        // 中度积压，按 1/5 速度吞噬
                        batchSize = Math.max(4, Math.floor(queueLength / 5));
                    } else if (queueLength > 10) {
                        // 轻度积压，每次出 2-3 个字
                        batchSize = 2;
                    } else {
                        // 无积压，单字精致吐墨
                        batchSize = 1;
                    }

                    const chunk = typingQueue.splice(0, batchSize).join('');
                    displayedResponse += chunk;

                    // 禁用 lightweight，采用增量防抖引擎进行高质量渲染，Markdown 实时完美展现
                    updateDoubleTracks(displayedResponse, true, false);
                    chatHistory.scrollTop = chatHistory.scrollHeight;

                    // 用 requestAnimationFrame 对齐屏幕刷新，避免 setTimeout 累积延迟
                    if (!typingRAF) {
                        typingRAF = requestAnimationFrame(processTyping);
                    }
                } else {
                    // 打字队列空了：如果流已结束则收尾
                    if (streamFinished) {
                        finalizeChat();
                    }
                }
            }

            let buffer = '';
            while (true) {
                const { value, done } = await reader.read();
                if (done) {
                    if (buffer.trim()) {
                        processChatLine(buffer.trim());
                    }
                    break;
                }

                buffer += decoder.decode(value, { stream: true });
                let boundary = buffer.indexOf('\n');
                while (boundary !== -1) {
                    const line = buffer.substring(0, boundary).trim();
                    buffer = buffer.substring(boundary + 1);
                    if (line) {
                        processChatLine(line);
                    }
                    boundary = buffer.indexOf('\n');
                }
            }

            function processChatLine(line) {
                if (line.startsWith('data: ')) {
                    const data = line.slice(6);
                    if (data === '[DONE]') {
                        return;
                    }
                    try {
                        const json = JSON.parse(data);
                        // 处理上下文 token 信息
                        if (json.type === 'context') {
                            updateContextIndicator(json.trimmed_tokens, json.original_tokens, json.trimmed_count, json.max_tokens);
                            return;
                        }
                        if (json.token) {
                            fullResponse += json.token;
                            
                            // 保护控制标签，绝不将其大卸八块为单字打字以防渲染状态闪烁
                            const tokenTrimmed = json.token.trim();
                            if (tokenTrimmed === '<think>' || tokenTrimmed === '</think>' || (tokenTrimmed.startsWith('<') && tokenTrimmed.endsWith('>'))) {
                                typingQueue.push(json.token);
                            } else {
                                typingQueue.push(...json.token.split(''));
                            }
                            
                            // 启动打字器运行
                            if (!typingRAF) {
                                typingRAF = requestAnimationFrame(processTyping);
                            }

                            // 流式语音:检测到完整句子立即送 TTS（基于 fullResponse，零延迟触发）
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

            // 标记网络流已全部加载完
            streamFinished = true;
            
            // 如果此时打字缓冲队列已无数据，立即收尾；否则等待打字完毕后在 processTyping 中收尾
            if (!typingRAF) {
                finalizeChat();
            }

            function finalizeChat() {
                // 收尾更新，强制让 details 闭合（不传 isGenerating，即 details 不带 open）
                updateDoubleTracks(fullResponse, false, false);
                loadingMsg.dataset.rawContent = fullResponse;

                // 完成后将回复加入消息历史
                messages.push({ "role": "assistant", "content": fullResponse });

                // 渲染 Mermaid 图表(流式结束后可能有未渲染 of 图表)
                renderMermaidDiagrams();

                // 流式 TTS:刷入剩余未完句子
                if (useStreamingTTS && fullResponse.substring(ttsPointer).trim()) {
                    streamingAudioQueue.enqueue(fullResponse.substring(ttsPointer).trim());
                }

                // 覆盖式增量自动保存：每一轮流式响应结束，后台静默自动保存草稿
                saveCurrentChat(true, true);
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

        // 创建实际消息体 (使用 div 替代 span,以支持内部包含思考块等块级元素)
        const messageBody = document.createElement('div');
        messageBody.dataset.rawContent = text;

        if (role === 'assistant') {
            // 助手消息:渲染 Markdown
            messageBody.className = 'markdown-content';
            messageBody.innerHTML = renderWithThinking(text, false);
            // 异步渲染 Mermaid 图表
            setTimeout(renderMermaidDiagrams, 50);
        } else {
            // 用户消息:纯文本
            messageBody.innerText = text;
        }

        contentDiv.appendChild(messageBody);
        wrapper.appendChild(contentDiv);

        // 添加工具栏(复制按钮 + 朗读按钮)
        const toolbar = document.createElement('div');
        toolbar.className = 'msg-toolbar';

        // 复制按钮 - 只复制正文内容(不含思考块)
        const copyBtn = document.createElement('button');
        copyBtn.className = 'btn-icon btn-copy-inline';
        copyBtn.innerHTML = '📋 复制';
        copyBtn.onclick = async () => {
            try {
                let copyText;
                if (role === 'assistant') {
                    const rawMarkdown = messageBody.dataset.rawContent || '';
                    if (rawMarkdown) {
                        // 只提取正文部分，自适应剥离 <think>...</think> 标签，保留完美原始 Markdown
                        copyText = rawMarkdown.replace(/<think>[\s\S]*?<\/think>/gi, '').trim();
                    } else {
                        // 降级：只提取 .answer-content 的纯文本
                        const answerEls = messageBody.querySelectorAll('.answer-content');
                        copyText = Array.from(answerEls)
                            .map(el => el.innerText.trim())
                            .filter(t => t)
                            .join('\n\n');
                    }
                } else {
                    copyText = messageBody.dataset.rawContent || messageBody.innerText;
                }
                await navigator.clipboard.writeText(copyText);
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
            speakBtn.onclick = () => {
                // 朗读也只读正文
                const answerEls = messageBody.querySelectorAll('.answer-content');
                const speakText = Array.from(answerEls)
                    .map(el => el.innerText.trim())
                    .filter(t => t)
                    .join('\n\n');
                playTTS(speakText, speakBtn);
            };
            toolbar.appendChild(speakBtn);
        }

        wrapper.appendChild(toolbar);

        chatHistory.appendChild(wrapper);
        chatHistory.scrollTop = chatHistory.scrollHeight;
        return messageBody;
    }

    if (btnChatSend) btnChatSend.addEventListener('click', sendChatMessage);
    if (chatInput) chatInput.addEventListener('keypress', (e) => { if (e.key === 'Enter') sendChatMessage(); });

    // === 5.5 一键复制最新回答的正文(不含思考块)===
    const btnCopyLast = document.getElementById('btn-copy-last-answer');
    if (btnCopyLast) {
        btnCopyLast.addEventListener('click', async () => {
            const allAssistantMsgs = chatHistory.querySelectorAll('.msg-wrapper.assistant');
            if (!allAssistantMsgs.length) {
                btnCopyLast.textContent = '⚠️ 无内容';
                setTimeout(() => { btnCopyLast.textContent = '📋 复制正文'; }, 2000);
                return;
            }
            // 取最新一条助手消息
            const lastMsg = allAssistantMsgs[allAssistantMsgs.length - 1];
            const body = lastMsg.querySelector('.markdown-content');
            let text = '';
            if (body) {
                const rawMarkdown = body.dataset.rawContent || '';
                if (rawMarkdown) {
                    // 自适应剔除思考块并提取完美 Markdown
                    text = rawMarkdown.replace(/<think>[\s\S]*?<\/think>/gi, '').trim();
                } else {
                    const answerEls = body.querySelectorAll('.answer-content');
                    text = Array.from(answerEls)
                        .map(el => el.innerText.trim())
                        .filter(t => t)
                        .join('\n\n');
                }
            }
            if (!text) {
                btnCopyLast.textContent = '⚠️ 无正文';
                setTimeout(() => { btnCopyLast.textContent = '📋 复制正文'; }, 2000);
                return;
            }
            try {
                await navigator.clipboard.writeText(text);
                btnCopyLast.textContent = '✅ 已复制';
                btnCopyLast.style.backgroundColor = '#4caf50';
                setTimeout(() => {
                    btnCopyLast.textContent = '📋 复制正文';
                    btnCopyLast.style.backgroundColor = '';
                }, 2000);
            } catch (e) {
                btnCopyLast.textContent = '❌ 失败';
                setTimeout(() => { btnCopyLast.textContent = '📋 复制正文'; }, 2000);
            }
        });
    }

    // === 6. 释放显存(终止 AI Worker 子进程) ===
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
                showToast("✅ AI 进程已终止,显存已完全释放(含 CUDA context)");
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

    // === 文档浏览功能 ===
    const docsFileList = document.getElementById('docs-file-list');
    const docsEmptyState = document.getElementById('docs-empty-state');
    const docsViewerContainer = document.getElementById('docs-viewer-container');
    const docsViewerTitle = document.getElementById('docs-viewer-title');
    const docsRendered = document.getElementById('docs-rendered');
    const docsIframe = document.getElementById('docs-iframe');
    const docsRawContent = document.getElementById('docs-raw-content');
    const docsToc = document.getElementById('docs-toc');
    const docsSearch = document.getElementById('docs-search');
    const docsSortSelect = document.getElementById('docs-sort');
    const btnDocsRefresh = document.getElementById('btn-docs-refresh');
    const btnDocsCopy = document.getElementById('btn-docs-copy');
    const btnDocsView = document.getElementById('btn-docs-view');
    const btnDocsRaw = document.getElementById('btn-docs-raw');
    
    let docsCurrentFile = null;  // 当前查看的文件信息
    let docsRawContent_text = '';  // 当前文件的原始内容
    let docsShowRaw = false;  // 是否显示源码
    let _allDocsFiles = [];  // 缓存完整文件列表（用于搜索/排序）
    
    async function loadDocsList() {
        docsFileList.innerHTML = '<div class="docs-loading">加载中...</div>';
        try {
            const resp = await fetch('/api/docs/list');
            const data = await resp.json();
            if (!data.files || data.files.length === 0) {
                docsFileList.innerHTML = '<div class="docs-no-files">暂无 HTML/MD 文档</div>';
                _allDocsFiles = [];
                return;
            }
            _allDocsFiles = data.files;  // 缓存完整列表
            renderDocsList();  // 渲染（带搜索/排序）
        } catch (e) {
            docsFileList.innerHTML = '<div class="docs-no-files">加载失败</div>';
        }
    }
    
    function renderDocsList() {
        const query = (docsSearch ? docsSearch.value.toLowerCase() : '').trim();
        const sort = docsSortSelect ? docsSortSelect.value : 'time-desc';
        let files = [..._allDocsFiles];
        
        // 搜索过滤
        if (query) {
            files = files.filter(f => f.name.toLowerCase().includes(query) || f.path.toLowerCase().includes(query));
        }
        
        // 排序
        if (sort === 'time-desc') files.sort((a, b) => b.modified - a.modified);
        else if (sort === 'time-asc') files.sort((a, b) => a.modified - b.modified);
        else if (sort === 'name-asc') files.sort((a, b) => a.name.localeCompare(b.name));
        else if (sort === 'name-desc') files.sort((a, b) => b.name.localeCompare(a.name));
        else if (sort === 'size-desc') files.sort((a, b) => b.size - a.size);
        else if (sort === 'size-asc') files.sort((a, b) => a.size - b.size);
        
        docsFileList.innerHTML = '';
        if (files.length === 0) {
            docsFileList.innerHTML = '<div class="docs-no-files">无匹配文件</div>';
            return;
        }
        files.forEach(f => {
            const item = document.createElement('div');
            item.className = 'docs-file-item';
            item.dataset.path = f.path;
            const icon = f.type === 'html' ? '🌐' : '📝';
            item.innerHTML = `
                <span class="docs-file-icon">${icon}</span>
                <div class="docs-file-info">
                    <div class="docs-file-name" title="${f.path}">${f.name}</div>
                    <div class="docs-file-meta">${f.size_str} · ${f.modified_str}</div>
                </div>
            `;
            item.addEventListener('click', () => openDoc(f, item));
            docsFileList.appendChild(item);
        });
    }
    
    async function openDoc(fileInfo, itemEl) {
        // 更新选中状态
        docsFileList.querySelectorAll('.docs-file-item').forEach(el => el.classList.remove('active'));
        if (itemEl) itemEl.classList.add('active');
        
        docsCurrentFile = fileInfo;
        docsViewerTitle.textContent = fileInfo.name;
        docsShowRaw = false;
        btnDocsRaw.textContent = '🔤 源码';
        
        // 【优化】此处移除了原有的自动 window.open() 跳转逻辑。
        // 这样点击左侧文件项时仅会在右侧加载预览和绑定当前文件，不会再频繁弹出新窗口。
        // 若用户需要跳转至新标签页打开，可以通过点击右侧操作区的“🌐 打开”按钮来手动触发。
        
        // 同时在右侧小窗加载预览（方便快速浏览）
        try {
            const resp = await fetch(`/api/docs/read?path=${encodeURIComponent(fileInfo.path)}`);
            const data = await resp.json();
            if (data.error) {
                docsRendered.innerHTML = `<p style="color: #ef4444;">读取失败: ${data.error}</p>`;
                showDocsViewer('markdown');
                return;
            }
            
            docsRawContent_text = data.content;
            
            if (data.type === 'html') {
                showDocsViewer('html');
                docsIframe.srcdoc = data.content;
            } else {
                showDocsViewer('markdown');
                const rendered = renderMarkdown(data.content);
                docsRendered.innerHTML = rendered;
                // 为标题添加 id（支持 TOC 锚点跳转）
                addHeadingIds(docsRendered);
                // 渲染 TOC（仅 Markdown）
                renderToc(data.content);
                // 渲染 Mermaid 图表
                renderMermaidInElement(docsRendered);
            }
        } catch (e) {
            // 预览加载失败不影响新标签页
        }
    }
    
    function showDocsViewer(type) {
        docsEmptyState.classList.add('hidden');
        docsViewerContainer.classList.remove('hidden');
        docsRendered.classList.add('hidden');
        docsIframe.classList.add('hidden');
        docsRawContent.classList.add('hidden');
        if (docsToc) docsToc.classList.add('hidden');
        
        if (docsShowRaw) {
            // 带行号的源码视图
            const lines = docsRawContent_text.split('\n');
            docsRawContent.innerHTML = lines.map((line, i) =>
                `<span class="line-num">${String(i + 1).padStart(String(lines.length).length, ' ') + ' '}</span>${escapeHtml(line)}`
            ).join('\n');
            docsRawContent.classList.remove('hidden');
        } else if (type === 'html') {
            docsIframe.classList.remove('hidden');
        } else {
            if (docsToc) docsToc.classList.remove('hidden');  // TOC 仅在 MD 模式显示
            docsRendered.classList.remove('hidden');
        }
    }
    
    // 生成 Markdown 文档的目录（TOC）
    function renderToc(mdText) {
        if (!docsToc) return;
        // 提取所有 h1/h2/h3 标题
        const headingRe = /^(#{1,3})\s+(.+)$/gm;
        const headings = [];
        let m;
        while ((m = headingRe.exec(mdText)) !== null) {
            const level = m[1].length;
            const text = m[2].replace(/`([^`]+)`/g, '$1').trim();
            headings.push({ level, text });
        }
        
        if (headings.length < 2) {
            docsToc.classList.add('hidden');
            return;
        }
        docsToc.classList.remove('hidden');
        let html = '<div class="docs-toc-title">📑 目录</div><ul class="docs-toc-list">';
        headings.forEach((h, i) => {
            html += `<li class="docs-toc-item docs-toc-l${h.level}"><a href="#toc-h${i}" class="docs-toc-link">${h.text}</a></li>`;
        });
        html += '</ul>';
        docsToc.innerHTML = html;
    }
    
    // 在指定容器中渲染 Mermaid 图表
    function renderMermaidInElement(container) {
        if (!container) return;
        const mermaidEls = container.querySelectorAll('.mermaid-code-block, pre code.language-mermaid');
        if (mermaidEls.length === 0) return;
        // 延迟渲染，等待 marked 处理完毕
        setTimeout(() => {
            try {
                if (typeof mermaid !== 'undefined' && mermaid.run) {
                    mermaid.run({ querySelector: '.mermaid-code-block, .language-mermaid' });
                }
            } catch (e) {
                // 静默失败，Mermaid 可能未初始化
            }
        }, 150);
    }
    // 为容器中的 h1/h2/h3 按顺序添加 id 属性（支持 TOC 锚点跳转）
    function addHeadingIds(container) {
        if (!container) return;
        const headings = container.querySelectorAll('h1, h2, h3');
        headings.forEach((h, i) => {
            h.id = 'toc-h' + i;
        });
    }
    
    // 更新 TOC 中的锚点链接，使其与 addHeadingIds 生成的 id 对应
    function syncTocAnchors() {
        if (!docsToc) return;
        const links = docsToc.querySelectorAll('.docs-toc-link');
        const headings = docsRendered.querySelectorAll('h1, h2, h3');
        links.forEach((link, i) => {
            if (i < headings.length) {
                link.href = '#' + headings[i].id;
            }
        });
    }
    
    // 刷新按钮
    btnDocsRefresh.addEventListener('click', loadDocsList);
    
    // 复制按钮
    btnDocsCopy.addEventListener('click', () => {
        if (!docsRawContent_text) return;
        navigator.clipboard.writeText(docsRawContent_text).then(() => {
            showToast('已复制文件内容');
        }).catch(() => {
            // fallback
            const ta = document.createElement('textarea');
            ta.value = docsRawContent_text;
            document.body.appendChild(ta);
            ta.select();
            document.execCommand('copy');
            document.body.removeChild(ta);
            showToast('已复制文件内容');
        });
    });
    
    // 【新增】“🌐 打开”按钮的点击事件监听器。
    // 当点击时，在新标签页/新窗口中全屏打开当前正在浏览的文档文件（利用 docsCurrentFile 绑定的路径）。
    // 这样将“新窗口打开”的行为交由用户主动选择，极大提升了多文档快速预览时的用户体验。
    btnDocsView.addEventListener('click', () => {
        if (!docsCurrentFile) return;
        window.open(`/api/docs/view?path=${encodeURIComponent(docsCurrentFile.path)}`, '_blank');
    });
    
    // 源码/渲染切换
    btnDocsRaw.addEventListener('click', () => {
        docsShowRaw = !docsShowRaw;
        btnDocsRaw.textContent = docsShowRaw ? '👁️ 渲染' : '🔤 源码';
        if (docsCurrentFile) {
            const type = docsCurrentFile.type;
            showDocsViewer(type);
        }
    });
    
    // 首次切换到文档页时加载列表
    const docsTabBtn = document.querySelector('[data-tab="docs"]');
    if (docsTabBtn) {
        docsTabBtn.addEventListener('click', () => {
            if (_allDocsFiles.length === 0 && docsFileList.querySelector('.docs-loading')) {
                loadDocsList();
            }
        });
    }
    
    // 搜索输入事件
    if (docsSearch) {
        docsSearch.addEventListener('input', () => renderDocsList());
    }
    
    // 排序切换事件
    if (docsSortSelect) {
        docsSortSelect.addEventListener('change', () => renderDocsList());
    }
});
