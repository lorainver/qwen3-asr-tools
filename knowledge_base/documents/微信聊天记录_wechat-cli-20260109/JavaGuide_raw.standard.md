# 聊天记录: JavaGuide
**时间范围:** 2026-01-09 ~ 最新
**导出时间:** 2026-06-27 10:34
**消息数量:** 75
**类型:** 私聊
---

**JavaGuide** (2026-04-01 10:45):

感谢你的关注！很开心能和你相遇～


**JavaGuide** (2026-04-01 12:25):

[链接] 推荐 6 个爆火的神级 Skills，400K+ 点赞！Vibe Coding 必备！！


**JavaGuide** (2026-04-02 18:09):

[链接] 又一款国产模型诞生，性价比杀疯了！


**JavaGuide** (2026-04-03 17:13):

[链接] Claude Code创始人最爱！一行命令打造24小时专属牛马，香爆了！


**JavaGuide** (2026-04-04 20:59):

[链接] 人麻了已经，学不动了！现在圈子里各种新概念、新名词层出不穷， 每天睁眼不是“范式转移”就是“智能体协作”。可讽刺的是，AI 爆发这两年，程序员反而活得越来越累了。 工具在迭代，老板的欲望膨胀得更快。很多人真信了“一人即团队”的幻觉，招聘名额先砍一半，剩下的兄弟往死里用。以前你只需深耕一个模块，现在要同时应付前后端、多线程任务、甚至一堆 Agent。脑子在无数个上下文里疯狂切换，那是纯粹的心力交瘁。 更要命的是那种“工具强迫症”。 最近“小龙虾”（Claude Code）火了，很多人就开始魔怔。明明一行 Python 脚本就能搞定的事，非要折腾半天 Agent，耗着 Token 走着弯路，这不叫提效，这叫赛博自嗨。 这种焦虑循环最扎心的地方在于：你硬着头皮学完那些高大上的概念，回头面对公司那堆烂泥巴业务，发现根本落不了地。它们大多只是向上管理和PPT包装的“社交货币”，白白浪费了你原本可以补觉的时间。 那不用 AI 行不行？KPI 压着呢。别人用 AI 一天交三个需求，你纯手撸一个，领导怎么看？内卷就这么被无情加速了。 抱怨也没啥用，大环境就这样，只能硬着头皮上。别再死磕源码和底层原理了，在 AI 面前那点活儿真不够看。往后看，能不能把业务逻辑理清楚、把问题定义准确，才是拉开差距的关键。说白了，得是你使唤 AI，别反过来被工具给卷死了。 ⭐️推荐: 🔥Java & 后端面试指南（AI 应用开发面试正在持续更新）：<a class="normal_text_link mp_article_text_link" target="_blank" href="https://mp.weixin.qq.com/s?__biz=Mzg2OTA0Njk0OA==&mid=2247552140&idx=1&sn=551aeaa2298099436d22ac4983b17c49&scene=21#wechat_redirect">javaguide.cn</a> 🚀大模型实战项目（已开源）：<a class="normal_text_link mp_article_text_link" target="_blank" href="https://mp.weixin.qq.com/s?__biz=Mzg2OTA0Njk0OA==&mid=2247552320&idx=1&sn=a7e4e5a8d957446e6bb032d78b2fa5fb&scene=21#wechat_redirect">《SpringAI 智能面试平台+RAG 知识库》</a>


**JavaGuide** (2026-04-05 18:45):

[链接] 最近用 Claude Code + 国产模型，基于 Java 从零搭了一个多 Agent股票分析系统。核心是研究员→技术分析师→舆情分析师→投资经理的流水线，还加了多模型辩论模式——多个 LLM从多、空、中立三方立场互相对抗，仲裁官综合裁决。 分享几点感触： 1. 先设计再动手 最值的操作是先花大半天写设计文档：架构、数据流、类图、接口、伪代码全写清楚，丢给 AI 反复review，迭代三四轮才动代码。写代码阶段几乎没返工，因为边界条件和模块契约在设计期就理清了。这就是 Spec Coding 的简化版。 2. 写完跑 /simplify 或者自定义 review skill /simplify 会启动三个并行 Agent，从代码复用、质量、效率三个维度审查。它帮我多次提取了重复逻辑、清掉了死代码、发现了设计缺陷。不需要记命令，一个斜杠 / 就能调出，也可按团队规范自定义 review skill。 真心蛮实用的，我一般也是搭配自己写的自定义 Java 规范 skill 一起使用。 3. 让 Claude 自己干，你去睡觉 设计方案足够详细的话，直接跟 Claude 说“按方案实现，自动执行。执行完成之后，自动跑一遍 simplify。”，第二天起来发现 10个子任务全做完，编译错误也修了，/simplify 也跑过了。设计越模糊，中间需要人工介入的概率越高。 再分享下项目核心功能，出于兴趣开发，完全从零开始（星球里分享过截图了，公众号这里就不贴了）： - 流水线模式：四个 Agent 串并行协作，覆盖行情采集、K线/MACD/RSI 分析、股吧舆情、综合决策与风险评估 - 辩论模式：多 LLM 多空对抗辩论，仲裁官裁决，减少单模型偏见 - 记忆系统：自动召回历史分析结论，保持上下文连贯 - 工程能力：SSE 流式输出、多 LLM 热切换与弹性降级、提示词版本管理、策略系统 - 前端：K 线图、Agent 对话面板（支持 @ 指定 Agent）、自选股管理、分析历史与报告导出 由于这个项目涉及到了爬虫，暂时就不分享了~ ⭐️推荐: 🔥Java & 后端面试指南（AI 应用开发面试正在持续更新）：<a class="normal_text_link mp_article_text_link" target="_blank" href="https://mp.weixin.qq.com/s?__biz=Mzg2OTA0Njk0OA==&mid=2247552140&idx=1&sn=551aeaa2298099436d22ac4983b17c49&scene=21#wechat_redirect">javaguide.cn</a> 🚀大模型实战项目（已开源）：<a class="normal_text_link mp_article_text_link" target="_blank" href="https://mp.weixin.qq.com/s?__biz=Mzg2OTA0Njk0OA==&mid=2247552320&idx=1&sn=a7e4e5a8d957446e6bb032d78b2fa5fb&scene=21#wechat_redirect">《SpringAI 智能面试平台+RAG 知识库》</a>


**JavaGuide** (2026-04-07 12:23):

[链接] 鹅厂面试官：“为什么敏感词过滤不用暴力匹配？” 我：“用暴力匹配的同事性能已经挂了”


**JavaGuide** (2026-04-08 14:02):

[链接] GLM-5.1 发布，实测两周，太猛了！


**JavaGuide** (2026-04-09 14:09):

[链接] 面试官：“Harness Engineering 到底是什么？你的项目用了吗？”


**JavaGuide** (2026-04-10 09:34):

[链接] 近期准备跳槽的兄弟注意了。。。


**JavaGuide** (2026-04-11 21:34):

[链接] 晚上刷到一个硅谷后端老哥的分享，讲得太真实扎心了。这哥们在组里贡献排名前三，PR 和 Code Review 数量都靠前，结果去年 4 月突然被 PIP 了。之后求职整整一年，一个 offer 都没拿到。 1. 现在的市场有多卷 一个岗位放出来，两小时收到成百上千份简历。面试表现不错也不一定能过，老板挑花眼，等着看有没有更完美的人选出现。 传统后端需求在萎缩，简历上没有 Python、AWS 或 AI 相关技能（这里指的是国外求职市场），基本石沉大海。大厂砸了太多钱在算力和芯片上，砍传统岗位来填坑，这不是周期波动，是结构性转型。 2. AI 编程这四年走得太快了 他把 AI 辅助编程的演进拆成了四步，我觉得梳理得挺清楚的： 第一步，2022 年底，Prompt Engineering。给模型一句话，它给你一段代码。 第二步，2024 年，Agent。AI 开始替你跑重复流程，从问答模式变成了干活模式。 第三步，2025 年，Context Engineering。让 AI 理解你的环境、意图和上下文，工作流开始围绕模型来组织。 第四步，2026 年，Harness Engineering。多个 Agent 协作，在约束条件下完成复杂任务。OpenAI 内部测试中，多 Agent 从零构建了数百万行代码，写代码这个环节几乎不需要人了。 3. 程序员的角色在往上走 他说了一句让我印象很深的话：“未来可能一个 CTO 就能管所有 Agent，让它产出所有代码、部署、改 Bug。” 说白了，写代码正在被自动化掉。程序员的核心工作变成了管理 Agent 之间的协作，怎么分工、怎么约束、怎么验收。更像在管一个团队，跟纯技术关系不大了。 做产品最不重要的可能就是纯技术。懂产品、懂市场、懂怎么让 AI 替你干活，这些正在变成真正的竞争力。 4. 两极分化已经开始了 会用 AI 工具的人，产出可能是普通人的 100 倍。不会用的，要么转行，要么接受边缘化。没有中间地带。 说实话，看到这个分享的时候确实挺受触动的。从 Prompt 到 Harness，短短四年，写代码这件事正在从程序员的“手艺”变成 Agent 的“标准操作”。 焦虑是肯定的，但焦虑没用，大环境不会因为你焦虑就慢下来。我们能做的，就是在被替代之前学会驾驭这些工具，成为那个“管 Agent 的人”，而不是被 Agent 替代的人。共勉！ ⭐️推荐: 🔥Java & 后端面试指南（AI 应用开发面试正在持续更新）：<a class="normal_text_link mp_article_text_link" target="_blank" href="https://mp.weixin.qq.com/s?__biz=Mzg2OTA0Njk0OA==&mid=2247552140&idx=1&sn=551aeaa2298099436d22ac4983b17c49&scene=21#wechat_redirect">javaguide.cn</a> 🚀大模型实战项目（已开源，2.0版本已发布）：<a class="normal_text_link mp_article_text_link" target="_blank" href="https://mp.weixin.qq.com/s?__biz=Mzg2OTA0Njk0OA==&mid=2247552320&idx=1&sn=a7e4e5a8d957446e6bb032d78b2fa5fb&scene=21#wechat_redirect">《SpringAI 智能面试平台+RAG 知识库》</a>


**JavaGuide** (2026-04-13 17:12):

[链接] Java 版小龙虾终于有人开源了！


**JavaGuide** (2026-04-14 14:39):

[链接] 桃厂面试官：“你的 Agent 项目提示词工程是怎么做的？恶意用户 Prompt 注入怎么处理？”


**JavaGuide** (2026-04-15 09:34):

[链接] Claude Code + IDEA/VS Code = 王炸！


**JavaGuide** (2026-04-16 11:55):

[链接] 面试官：“你连AI项目都没有也敢面AI应用开发？”我笑了：“简历都过了。”面试官：“勇气可嘉！”


**JavaGuide** (2026-04-17 12:36):

[链接] Claude Opus 4.7 正式发布！确实很顶，全网都在吹。 还是想聊点现实的：国内大部分人用不上 Claude，号早被封了，包括我自己的。想用的话，只能走 Copilot、Qoder 等内置 Claude 模型的第三方平台。 更蛋疼的是，Claude 最近又加了一道身份验证，访问特定功能或触发风控时强制弹窗。官方说法冠冕堂皇：“防止滥用、落实平台政策及履行法律合规义务”。懂的都懂。 所以我现在的用法是这样的：先把系统设计方案扔给 Opus 4.6、GPT-5.4、Gemini 3.1 Pro 这几个顶级模型反复讨论，架构和关键决策敲定之后，实现代码直接交给便宜点的模型写。 下面简单聊聊 Claude Opus 4.7 最关键的升级： 1. 编码跳了最大一档。SWE-bench Pro 从 53.4% 飙到 64.3%，涨了 10.9 个点。Cursor 内部基准上 4.7 拿 70%，4.6 是 58%。Rakuten 报告生产任务解决率翻了 3 倍。 2. 代理能力质变。MCP-Atlas 涨 14.6 个点，所有单项最大。4.7 更会“用工具干活”了，拿到锤子不再当扳手使。 3. 视觉暴涨。图像分辨率从约 1.15MP 提到 3.75MP，像素量翻了 3.3 倍。CharXiv-R 无工具场景 +13.4，截图理解和数据提取直接上一台阶。 4. 自我验证。4.7 报结果前先跑检查、写测试。Vercel 说它“开始干活前先对系统代码做证明”，这行为之前没出现过。 5. 新增 xhigh 努力等级，卡在 high 和 max 之间。Claude Code 已经把默认努力等级调到 xhigh 了。 性价比其实也涨了。Hex 测试发现 low 努力的 4.7 大致等于 medium 努力的 4.6，同样完成质量，用更低档就行。 但升级有三个坑： 1. 新分词器吃 token。同样文本，4.7 可能多出 0–35% 的 token。固定 token 预算的管线，迁移前必须重新测。 2. 指令理解更“死板”。之前 4.6 会猜你想说什么的地方，4.7 照字面执行。prompt 里写了“可以考虑”“建议”这类模糊措辞，4.7 会当真。迁移前审一遍系统 prompt。 3. 三个参数直接废了。temperature、top_p、top_k 设非默认值报 400 错误，旧版 extended thinking 也一样。代码里带着这些的，删干净再升。 说白了，让最贵的脑子干最需要脑子的活——设计、评审、排查疑难杂症。搬砖的活交给性价比高的模型就行。这套打法跑下来，省钱而且效果不错。 ⭐️推荐: 🔥Java & 后端面试指南（AI 应用开发面试正在持续更新）：<a class="normal_text_link mp_article_text_link" target="_blank" href="https://mp.weixin.qq.com/s?__biz=Mzg2OTA0Njk0OA==&mid=2247552140&idx=1&sn=551aeaa2298099436d22ac4983b17c49&scene=21#wechat_redirect">javaguide.cn</a> 🚀大模型实战项目（已开源，2.0版本已发布）：<a class="normal_text_link mp_article_text_link" data-itemshowtype="0" data-unique-id="mo2ero1y-2nwlep" target="_blank" href="https://mp.weixin.qq.com/s?__biz=Mzg2OTA0Njk0OA==&mid=2247554061&idx=1&sn=d41c2ef6372d69e39f7dbcbe1a44a33a&scene=21#wechat_redirect">《SpringAI 智能面试平台+RAG 知识库》</a>


**JavaGuide** (2026-04-18 20:57):

[链接] 刚开车听播客听到个离谱消息：苹果把 Siri 团队近 200 名工程师被送去参加为期数周的 AI 编程训练营。 你要是继续坚持做古法程序员，那我真的佩服你。AI 编程这玩意，一旦体验之后就真的回不去了。即使是用便宜点的模型，设计方案给得好的情况下，也能满足日常工作 95% 甚至 99% 的需求。 所以我现在的用法是这样的：先把系统设计方案扔给 Opus 4.6、GPT-5.4、Gemini 3.1 Pro 这几个顶级模型反复讨论，架构和关键决策敲定之后，实现代码直接交给便宜点的模型写。有位朋友对这句话的评论很扎心：直接道出了程序员的真实现状，只会干活的就是便宜。 这话听着刺耳，但想想还真是这么回事。撸代码快已经不算本事了，能不能把需求定义清楚、把方案设计明白、把 AI 输出的结果把关到位，这些才是值钱的。 连苹果都这么干了，信号已经够明确了——AI 编程已经是必修课。放心，不卖课，给几点小建议： 1. 别再观望了。工具迭代的速度远比你想象得快，等你觉得“准备好了”再上手，别人已经跑出去很远了。 2. 警惕工具强迫症。AI 是手段不是目的，一行脚本能搞定的事非要折腾半天 Agent，这不叫提效，叫赛博自嗨。 3. 别当 AI 保姆。生成代码不看逻辑，短期效率高，长期在给自己埋雷。你的角色是“AI 的技术审核官”，别搞成它的一键部署工具了。你并不需要做到对 AI 生成代码的每一个细节都了解，但整体方向依然要是你来掌握！ 4. 上下文很重要！AI 再聪明，它也不懂你们公司的祖传业务和隐藏的坑。与其抱怨它瞎写代码，不如好好研究下怎么把领域模型和边界条件喂清楚。 5. 将精力投入到重要的架构设计上。CRUD 和背 API 这种体力活以后真不值钱了。 两极分化已经开始了，焦虑没用，作为普通人只能顺应时代，在被替代之前用好这些工具解决实际问题。共勉！ 下面这几篇是 AI Coding 相关的经验分享： <a class="normal_text_link mp_article_text_link" target="_blank" href="https://mp.weixin.qq.com/s?__biz=Mzg2OTA0Njk0OA==&mid=2247553788&idx=1&sn=7a4f8838101d9c9ba511f0cec146dea0&scene=21#wechat_redirect">推荐 6 个爆火的神级 Skills，400K+ 点赞！Vibe Coding 必备！！</a> <a class="normal_text_link mp_article_text_link" target="_blank" href="https://mp.weixin.qq.com/s?__biz=Mzg2OTA0Njk0OA==&mid=2247553840&idx=1&sn=8e38b66ff46117ea50ef1fcb7e0719fa&scene=21#wechat_redirect">Claude Code 创始人力荐！一行 /loop 命令打造 24 小时专属牛马</a> <a class="normal_text_link mp_article_text_link" target="_blank" href="https://mp.weixin.qq.com/s?__biz=Mzg2OTA0Njk0OA==&mid=2247553629&idx=1&sn=e30d8188b174d3ad5302eb07ff8abae0&scene=21#wechat_redirect">Claude Code 内置 simplify 代码审查命令代码优化实战</a> <a class="normal_text_link mp_article_text_link" target="_blank" href="https://mp.weixin.qq.com/s?__biz=Mzg2OTA0Njk0OA==&mid=2247552738&idx=1&sn=2f6e724f0b57810ae79c909ff7da8c80&scene=21#wechat_redirect">7 道 AI 编程相关的开放性问题</a>


**JavaGuide** (2026-04-20 14:19):

[链接] 面试官：“Claude Code 内置搜索不够用？非要接个 Tavily 显得你活多？”我冷静回怼：“那是你日常使用场景太少了”


**JavaGuide** (2026-04-21 17:16):

[链接] 鹅厂面试官：“连Workflow、Graph、Loop的层次关系都说不清，还敢说精通AI工作流？”我：“不都是流程引擎吗？”面试官：“下一个！”


**JavaGuide** (2026-04-22 12:15):

[链接] IDEA 爽用 Claude Code 和 Codex 的终极方案，太丝滑！！


**JavaGuide** (2026-04-23 09:31):

[链接] 今年金三银四的实感。。


**JavaGuide** (2026-04-24 11:45):

[链接] SpaceX官宣600亿美元收购Cursor！


**JavaGuide** (2026-04-25 15:03):

[链接] DeepSeek V4+Claude Code一手实战！夯爆了还是拉完了？


**JavaGuide** (2026-04-26 22:04):

[链接] 从夯爆开始锐评我用过的 AI 编程模型： 🥇 第一梯队（夯爆） 1. GPT 5.5：工程场景最稳，API 生态最广，性价比拉满（量大管饱），就是写界面的审美需要继续多打磨打磨。 2. Claude Opus 4.6/4.7：上下文理解最深，UI/产品场景最懂你，就是太贵了。 双王并列，没有绝对第一。两个偶尔都会翻车，只是翻车的姿势不一样。 Guide 经常一个问题其中一个模型解决不了，换成另外一个很快就解决了。 🥈 第二梯队（夯） 1. GLM-5.1：最接近第一梯队的国产模型，Agent 能力已经能贴着第一梯队打，就是慢 + 不稳定，毕竟用的人太多了点，Coding 套餐都抢不到。 2. Kimi K2.6：潜力极强，benchmark 漂亮，但体感有时候跟不上纸面成绩，实际体验偶尔掉链子。 3. DeepSeek V4：写代码最“老实”的一个，不乱发挥，套路代码又快又稳，就是没有 Coding Plan 的情况下，用户编程场景还是有点贵。 4. Gemini：UI 和前端能打，工程场景偏弱，典型的偏科生。 就我自己的体感来说，GLM5.1 是第二梯队中编码体验最好的。这也是我目前的主力模型，Max 套餐就是造，便宜！ 下面这两篇是最近发的真实场景实测： <a class="normal_text_link mp_article_text_link" target="_blank" href="https://mp.weixin.qq.com/s?__biz=Mzg2OTA0Njk0OA==&mid=2247554204&idx=1&sn=87ada30fdb5c2bcdd9ad1c9f5f979eef&scene=21#wechat_redirect">DeepSeek V4+Claude Code一手实战！夯爆了还是拉完了？</a> <a class="normal_text_link mp_article_text_link" target="_blank" href="https://mp.weixin.qq.com/s?__biz=Mzg2OTA0Njk0OA==&mid=2247553896&idx=1&sn=667131f89f74ba561c418ab316aadc7d&scene=21#wechat_redirect">GLM-5.1 发布，实测两周，太猛了！</a> 叠个甲，以上排名仅代表个人看法，希望不要喷我。 列举的都是我自己用过的，还有很多没用过的就没有讨论，欢迎大家来分享自己的实际体验感受。


**JavaGuide** (2026-04-27 17:35):

[链接] DeepSeek V4价格暴降75%！Claude Code实战400万Tokens，终于可以爽用了


**JavaGuide** (2026-04-28 17:39):

[链接] 终于有好用的 Claude Code 状态栏增强插件了！


**JavaGuide** (2026-04-29 17:09):

[链接] GPT 5.5+Codex，夯爆了！


**JavaGuide** (2026-05-01 15:29):

[链接] 我装了一堆 AI 工具，AI Coding 工具都有好几个搭配用，Skill 装了几十个，理论上有了 AI 赋能，人能轻松一点。但坐电脑前的时间，比以前还长，甚至娱乐的时间都减少大半。 你可能觉得这不科学，效率提高了，不应该更轻松吗？还真不是。 为什么会出现这种现象呢？Guide 查了一下，核心结论就一句话：效率越高，加班越狠。 背后的机制其实很好理解。AI 把你的能力放大了，以前一天写三个接口就觉得自己挺能干，现在一天能写十个，还能顺手把架构设计、测试用例、文档全部搞定。 每做完一件事，立刻就能看到效果，价值反馈特别直接。 这就很要命了！多巴胺疯狂分泌，你感觉自己离"改变世界"只差一个回车键。 然后呢？你会忍不住接更多的活儿，因为"我能搞定"的信心被 AI 撑大了。老板也会给你安排更多的活儿，这个我在<a class="normal_text_link mp_article_text_link" target="_blank" href="https://mp.weixin.qq.com/s?__biz=Mzg2OTA0Njk0OA==&mid=2247553217&idx=1&sn=a912a4154efc27fab1f2f4a2645b91cf&scene=21#wechat_redirect">AI Coding 正在让程序员更累、更卷</a>中有提到。 说白了，AI没有让你变轻松，它让你觉得自己无所不能。而“无所不能”的感觉，是最危险的。 就像喝咖啡和功能性饮料强行让自己头脑清醒一样，看着是变强了，实际上在透支生命力。你牺牲的是睡眠、运动、和家人待在一起的时间。这些东西不在 KPI 里，所以你不会觉得亏。但身体会记住。 以前没有 AI 的时候，你写不动了就下班，因为确实干不动了。现在 AI 帮你把体力活全干了，你的瓶颈从"体力不够"变成了"精力不够"，但精力这东西，透支了比体力更难补回来。 现在经常半夜还在调 Agent、优化 Prompt、调整 Skill 写法，越搞越上头，回头一看，凌晨一两点了。 工具没有错，AI 也没有错。错的是我们没有给自己设一条线。 效率提升的红利，不应该全部用来干更多的活儿。至少留一点给自己吧！ 五一快乐啊！大家看到这篇文字消息的时候，Guide 已经开车带家人出去玩啦，放松放松！我是选择避开了人多的地方，找一些小众城市去看看。 ⭐️推荐: 🔥Java & 后端面试指南（AI 应用开发面试正在持续更新）：<a class="normal_text_link mp_article_text_link" target="_blank" href="https://mp.weixin.qq.com/s?__biz=Mzg2OTA0Njk0OA==&mid=2247552140&idx=1&sn=551aeaa2298099436d22ac4983b17c49&scene=21#wechat_redirect">javaguide.cn</a> 🚀大模型实战项目（已开源，2.0版本已发布）：<a class="normal_text_link mp_article_text_link" data-itemshowtype="0" target="_blank" href="https://mp.weixin.qq.com/s?__biz=Mzg2OTA0Njk0OA==&mid=2247554061&idx=1&sn=d41c2ef6372d69e39f7dbcbe1a44a33a&scene=21#wechat_redirect">《SpringAI 智能面试平台+RAG 知识库》</a>


**JavaGuide** (2026-05-03 20:33):

[链接] 收到了一个读者的提问：决定跳槽了，但老板还在 PUA，怎么应对？ 答案其实就四个字：情绪脱钩。 PUA 的底层逻辑，是建立在你对对方评价的在乎之上。一旦你做好了走人的准备，他的看法对你而言就毫无实际意义。 什么绩效被打 C、安排的活比同级难好几倍……在你提交离职申请的那一刻，这些统统归零。 具体到操作层面，有三条实操建议分享一下： 1. 把公司当成“带薪自习室”。不必拼命表现，也无需刻意摆烂，守住“不被开除”的底线即可。以标准质量完成基本任务，省下的精力全部砸在面试准备上。 2. 面对 PUA 用一句话挡回去。“我理解你的反馈，我会注意的。” 表面接受，实质不动。不争辩，不解释，不投入任何情绪。老板说啥你就嗯嗯，说完该干嘛干嘛。 3. 高职级的活，挑着做。这些任务里如果涉及技术难度高的内容，直接拿去当简历素材和面试案例。对跳槽有加分的认真搞，其余的“够用就行”标准交付。说白了，拿老板的活给简历打工。 另外，准备跳槽的顺序至关重要。 很多人一上来就闷头背八股文，效率极低。 正确的打法是：先搞定简历初版和核心项目复盘。在这个过程中暴露出自己的技术盲区，再有针对性地去查漏补缺。先搞清楚缺什么，再决定补什么。 说句实在话，如果最后能拿到裁员补偿走人，那完全是带薪备考，稳赚不赔。 脸皮厚一点，既然决定了要走，当下最核心的任务只有一件：最大化你的面试准备时间。其他的，一概不重要。 ⭐️推荐: 🔥Java & 后端面试指南（AI 应用开发面试正在持续更新）：<a class="normal_text_link mp_article_text_link" target="_blank" href="https://mp.weixin.qq.com/s?__biz=Mzg2OTA0Njk0OA==&mid=2247552140&idx=1&sn=551aeaa2298099436d22ac4983b17c49&scene=21#wechat_redirect">javaguide.cn</a> 🚀大模型实战项目（已开源，2.0版本已发布）：<a class="normal_text_link mp_article_text_link" data-itemshowtype="0" target="_blank" href="https://mp.weixin.qq.com/s?__biz=Mzg2OTA0Njk0OA==&mid=2247554061&idx=1&sn=d41c2ef6372d69e39f7dbcbe1a44a33a&scene=21#wechat_redirect">《SpringAI 智能面试平台+RAG 知识库》</a>


**JavaGuide** (2026-05-04 20:44):

[链接] 下一代 AI 终端神器终于开源了！


**JavaGuide** (2026-05-05 16:30):

[链接] 曾经的王，IDEA倒下了！


**JavaGuide** (2026-05-06 18:24):

[链接] 同事：“Claude Code 都能自动写代码了，还要什么 Agent 记忆系统？”我反问：“CLAUDE.md、Memory、RAG，你真分得清吗？”


**JavaGuide** (2026-05-07 18:37):

[链接] 腾讯面试官：Claude Code 用得挺熟？那你知道 CLAUDE.md 是怎么存记忆的吗？


**JavaGuide** (2026-05-08 14:04):

[链接] 收到工资1182415.18元，爱你DeepSeek！


**JavaGuide** (2026-05-09 14:28):

[链接] 20亿 Tokens！DeepSeek V4 和 GLM-5.1，谁才是 AI Coding 性价比之王？


**JavaGuide** (2026-05-11 14:29):

[链接] Step Plan + Claude Code 实战！代码审查和语音 Agent 都跑通了。


**JavaGuide** (2026-05-12 18:11):

[链接] Claude Code Token 自由，还能用上 GLM5.1，讯飞 Coding Plan 性价比真顶！


**JavaGuide** (2026-05-13 17:56):

[链接] 技术Leader：“还在Vibe Coding呢？要不试试Spec Coding，这套 Agent Skills 拿下 40600+ Star!”，我：“这么厉害？”


**JavaGuide** (2026-05-14 15:25):

[链接] Codex 把我的网站搞崩了！


**JavaGuide** (2026-05-15 15:48):

[链接] 前几天把 Cursor 升到 60 刀那档了，非常后悔！ 本来以为额度能经用点，结果差别真不大，并没有明显感觉到比20刀那档的提升。 随便跑个小任务就掉 1%，稍微复杂点的——让它翻一批文件、看看项目结构、再顺手改几处代码，一轮下来 2%~5% 就没了。 就很离谱，真不如 Codex 一根。GPT Plus 20 刀那档，感觉周额度都快赶上 60 刀这边了。 那为啥还用 Cursor?这不纯找不愉快嘛！ 两个原因吧。 一个是我平时主要拿它跑 Claude，配合 Codex 干点吃推理的活——方案设计、技术选型、讨论架构这种。便宜模型我一般拿去跑任务，写代码，图个性价比。 另一个原因大家都懂，国内直连 Claude 太容易封号，中转站又心里没底，价格还贵。Cursor 是内置了 Claude 模型，不需要担心封号，也比较稳定。 加上，Cursor 这边我是挺早就开了年费会员，也算是早起用户了。 年费到期之后，不准备再继续用 Cursor 了。 GPT Plus 已经升到 Pro 了，后面再申请一个 Claude 账号养一养看看，能不能坚持久一些。


**JavaGuide** (2026-05-16 22:24):

[链接] AI 时代，就是这样，不开玩笑。第一个说出这句话的朋友，真是天才。 真的会麻，都有点脱敏了。天天动不动就颠覆这个，重塑那个。 很多朋友问我：“现在待的公司和 AI 脱节很严重，用的还是内部大模型。很多新东西来不及学习，怎么办？” 对于新玩意，等你终于想起来要去学习的时候，发现可能已经都没什么人讨论了。这个角度看，偶尔拖延下也不是坏事哈。 举个大家都懂的例子，现在还有多少人在讨论龙虾（OpenClaw）？ 当时吹得有多猛、多离谱啊！全网都在营销，好像不装一个就跟不上时代、马上就要被淘汰了。 刚出来那会我也跟风装过，打开看了两眼，直接反手一个卸载。 对我个人使用场景来说，交互链路太长，还要折腾半天环境，实际价值对我个人而言趋近于 0。至于后面冒出来的那些个龙虾替代品，我基本就没再碰过。 也不是说它不好，就是我个人是真心用不上。 真正要干活、要落地生产，我为什么不用 Claude Code？为什么不用 Codex？这就是最顶级的 Agent，一个 npm 就能安装，对生产力确实是质的提升。 其实冷静下来想想，AI 的底层的东西都没怎么改变，就是ReAct、Function Calling、RAG、MCP、Multi-Agent……。 至于工具层面，真心别去折腾那些有的没的，够用就行，没必要浪费时间。 很多东西就是蹭热点，实际使用价值很低很低。 你不学显得落后，你不装显得不懂 AI。可真等这阵热度过去，你再回过头来冷眼瞅瞅，其实也就那么回事。 所以我现在对所有新工具的态度彻底变了：不急着冲，先放两周看看。 真有价值的硬核工具，不会因为我晚用了两周就消失；而那些活不过两周的东西，就当它提前帮我省下折腾环境的时间了。 ⭐️推荐: 🔥Java & 后端面试指南（AI 应用开发面试正在持续更新）：<a class="normal_text_link mp_article_text_link" target="_blank" href="https://mp.weixin.qq.com/s?__biz=Mzg2OTA0Njk0OA==&mid=2247552140&idx=1&sn=551aeaa2298099436d22ac4983b17c49&scene=21#wechat_redirect">javaguide.cn</a> 🚀大模型实战项目（已开源，2.0版本已发布）：<a class="normal_text_link mp_article_text_link" data-itemshowtype="0" target="_blank" href="https://mp.weixin.qq.com/s?__biz=Mzg2OTA0Njk0OA==&mid=2247554061&idx=1&sn=d41c2ef6372d69e39f7dbcbe1a44a33a&scene=21#wechat_redirect">《SpringAI 智能面试平台+RAG 知识库》</a>


**JavaGuide** (2026-05-18 14:12):

[链接] Claude Code 终于能管好多个 Agent 了！Agent View 用下来真香。


**JavaGuide** (2026-05-19 15:20):

[链接] Claude Code + BrowserAct，夯爆了！一句话让 AI 帮你操控浏览器。


**JavaGuide** (2026-05-20 17:10):

[链接] Claude Design 的开源平替爆火！4.7 万 Star！


**JavaGuide** (2026-05-21 11:36):

[链接] IDEA + JavaAI = 真香！


**JavaGuide** (2026-05-22 14:08):

[链接] 面试官坏笑：“DeepSeek-V4、GPT-5.5、Claude Opus 4.7 都 1M 窗口了，都塞进去不就行了？”我：“噪声太大！”，面试官：“尽快入职！”


**JavaGuide** (2026-05-23 18:16):

[链接] 夯爆了！DeepSeek V4 可以继续爽用了。


**JavaGuide** (2026-05-25 18:05):

[链接] 同事惊呆了：“Claude Skills 我也在用，但你 SKILL.md 写了 2000 行，是把它当 Prompt 还是当文档？”


**JavaGuide** (2026-05-26 09:31):

[链接] 面了一个75k的字节小姐姐，想当场给她offer。。


**JavaGuide** (2026-05-27 15:19):

[链接] 夯！让你的 Claude Code 满血起飞的官方神级插件诞生了。


**JavaGuide** (2026-05-28 14:56):

[链接] 同事：“Claude Code 都能自动写代码了，还要什么 Spec Coding？” 我反问：“屎山代码你来维护？”


**JavaGuide** (2026-05-29 17:27):

[链接] 为什么还有这么多人吹 Gemini？ 已经有点路边一条那味了。 现在的使用体验确实挺一般，经常给我一种很睿智的感觉，降智太厉害了。 之间为了用 Gemini 还开了 Google 的会员，现在也直接取消了。 不过，该说不说，用 AI Studio 写出来的前端界面确实还可以，审美不错。另外就是，深度研究功能也做的可以。 现在就看 Gemini 新模型发布能不能改变现状了！ Opus 4.8 今天也发布了，实际体验了一波，只能说没有惊艳，甚至感觉一般。 看到那些吹的起飞的账号，直接取关就好了。 Claude Opus 4.8 这次更新，普通用户重点看 5 件事就够了： 1. 更适合长时间写代码了：Claude 长时间改代码、看项目、跑多步骤任务时，更不容易中途跑偏。尤其是长上下文、上下文压缩之后恢复任务这些地方，比 Opus 4.7 更稳。 2. 工具调用更合理了：Opus 4.7 有时候会出现一个问题，明明应该调用工具，它硬靠自己猜。Opus 4.8 针对这个点做了优化，减少跳过工具调用的情况。 3. 可以在对话中途追加 system message：长任务跑到一半，可以补一条新的系统指令，不用把完整 system prompt 重新发一遍。 4. 快速模式出来了，但得加钱：官方说最高可以提升到 2.5 倍输出速度，但价格更高。本来就不够用，我还开这？ 5. 缓存门槛降低了：以前有些 prompt 太短，没法缓存，现在更容易命中缓存。对长对话、Agent loop、固定系统提示词这些场景比较有用，跑多了能省一点成本。要知道 DeepSeek V4 的缓存命中率真是神中神：<a class="normal_text_link mp_article_text_link" data-itemshowtype="0" data-unique-id="mpqprrzp-9kckwh" target="_blank" href="https://mp.weixin.qq.com/s?__biz=Mzg2OTA0Njk0OA==&mid=2247554627&idx=1&sn=0e6e5cfe772f3ba9dfb749b364780aff&scene=21#wechat_redirect">夯爆了！DeepSeek V4 可以继续爽用了。</a>。 Opus 4.8 目前看只能说是中规中矩，并不是很多博主说的什么王者归来，毕竟人家本身就是王者了，大家的期待也非常高！ 这次更新更像是 Opus 4.7 的工程化补丁。写代码、跑长任务、做 Agent 可能更稳了一点，但很多老用户怀念的那个 4.6 味儿，暂时还没完全回来。 第一天反馈太乱，真要下结论，最好再看几天真实项目里的表现。 ⭐️推荐阅读: <a class="normal_text_link mp_article_text_link" target="_blank" href="https://mp.weixin.qq.com/s?__biz=Mzg2OTA0Njk0OA==&mid=2247552320&idx=1&sn=a7e4e5a8d957446e6bb032d78b2fa5fb&scene=21#wechat_redirect">《SpringAI 智能面试平台》（2.0 版本已开源）</a>(Star 数量 2.1k+) <a class="normal_text_link album" target="_blank" href="https://mp.weixin.qq.com/mp/appmsgalbum?__biz=Mzg2OTA0Njk0OA==&action=getalbum&album_id=4412413577266053125&scene=126&sessionid=1777281752800#wechat_redirect">AI 应用开发面试指南：大模型、Agent、RAG、MCP、Prompt 工程</a>(累计阅读接近 50w+) <a class="normal_text_link album" target="_blank" href="https://mp.weixin.qq.com/mp/appmsgalbum?__biz=Mzg2OTA0Njk0OA==&action=getalbum&album_id=3845984209651990529&scene=126&sessionid=1779072612648#wechat_redirect">AI 编程实战指南：Claude Code、Cursor、Codex、Trae 使用技巧与面试题</a>(累计阅读接近 70w+)


**JavaGuide** (2026-05-31 18:23):

[链接] 为什么同样是 Vibe Coding，别人又快又稳，你这边老翻车？ 下面这 10 条，是我这几年 AI 编码踩坑总结出来的经验： 1. Git 是必备的，建议小步提交，避免 AI 把代码改乱改坏。 2. 让 AI 动手前，先看工作区。确认没有未提交改动，再单独拉分支。别直接在主分支上裸跑，不然后面排雷会很痛苦。 3. 需求别丢一句“帮我实现 xxx”。先写清目标、限制和验收标准，比如字段、权限、数量限制、错误处理。你可以让强模型帮你做这件事。 4. 让 AI 参考项目里的好代码。别只说“你得写优雅点”，直接让它看现有 Controller、Service、测试怎么写。 5. 项目坑点和规范写进规则文件。CLAUDE.md、AGENTS.md、Cursor Rules 里只放 AI 容易犯错、团队又必须遵守的东西。 6. 重复套路沉淀成 Skill。TDD、代码审查、前端检查、网页调研这些固定流程，不要每次靠聊天重新提醒。 7. 贵模型别拿来搬砖。强模型定方向、拆任务、做 Review；便宜模型负责具体编码和补测试，更划算。 8. AI 说修好了不算。看测试、命令输出和 diff。没跑测试就写没跑，性能优化也要有耗时、EXPLAIN 或压测数据。密钥、迁移、删除、推送这类操作必须人工确认。 9. 一个会话别塞太多任务。长任务要写 NOTES，方便新会话接着干。 10. 多 Agent 先串行再并行，流程跑顺以后，再考虑 worktree 并行、Agent View 这类玩法。subagent 适合做专项任务，可以在独立上下文中运行。 希望这些建议对大家有帮助，建议收藏一波！ 说白了，差距其实不完全在谁的 Prompt 写得好，或者谁的模型更强。Vibe Coding 也不是闭眼让 AI 狂写。 短期做原型，可以大胆一点，先把东西跑起来。但只要代码要长期维护，就得把 AI 拉回正常的工程流程里。 AI 写代码越快，Git、测试、Review、Spec 这些东西越不能丢。 以前它们主要是约束人。现在，也顺手约束一下 AI。 ⭐️推荐阅读: <a class="normal_text_link mp_article_text_link" target="_blank" href="https://mp.weixin.qq.com/s?__biz=Mzg2OTA0Njk0OA==&mid=2247552320&idx=1&sn=a7e4e5a8d957446e6bb032d78b2fa5fb&scene=21#wechat_redirect">《SpringAI 智能面试平台》（2.0 版本已开源）</a>(Star 数量 2.1k+) <a class="normal_text_link album" target="_blank" href="https://mp.weixin.qq.com/mp/appmsgalbum?__biz=Mzg2OTA0Njk0OA==&action=getalbum&album_id=4412413577266053125&scene=126&sessionid=1777281752800#wechat_redirect">AI 应用开发面试指南：大模型、Agent、RAG、MCP、Prompt 工程</a>(累计阅读接近 50w+) <a class="normal_text_link album" target="_blank" href="https://mp.weixin.qq.com/mp/appmsgalbum?__biz=Mzg2OTA0Njk0OA==&action=getalbum&album_id=3845984209651990529&scene=126&sessionid=1779072612648#wechat_redirect">AI 编程实战指南：Claude Code、Cursor、Codex、Trae 使用技巧与面试题</a>(累计阅读接近 70w+)


**JavaGuide** (2026-06-01 14:30):

[链接] 又一款国产大模型，开源了！


**JavaGuide** (2026-06-02 14:25):

[链接] 夯爆了！Codex 接入 DeepSeekV4、GLM5.1、K2.6。


**JavaGuide** (2026-06-03 13:01):

[链接] 大厂集体涨薪，风向变了。。。


**JavaGuide** (2026-06-04 18:32):

[链接] MiniMax M3 正式发布，夯！


**JavaGuide** (2026-06-05 14:29):

[链接] 面试官坏笑：“你用 AI 编程半年了，那怎么保证 Claude Code 写出来的代码是对的？”我：“直接用 Claude Opus 4.8！”


**JavaGuide** (2026-06-07 17:55):

[链接] 周五发了一篇 <a class="normal_text_link mp_article_text_link" target="_blank" href="https://mp.weixin.qq.com/s?__biz=Mzg2OTA0Njk0OA==&mid=2247554856&idx=1&sn=b4b406c784373435f7731c2ff3534a74&scene=21#wechat_redirect">Vibe Coding 技巧</a>，直接爆了，阅读马上破6w。 继续分享 7 条让 Claude Code 满血起飞的技巧： 1. 先把 CLAUDE.md 写好 CLAUDE.md 是一份 Claude 行为规范，像项目怎么启动、测试跑哪条命令、目录怎么分层、团队有什么特殊约定，都可以写进去。 Anthropic 建议保持 CLAUDE.md 精简不超过 200 行，只保留 Claude 无法轻易从代码中推断的信息。 我自己判断一条内容该不该放进去时，会用一个很土但好用的问题：这行删掉后，Claude 会不会更容易犯错？ 2. 复杂任务别上来就让它改代码 先让它只读代码，不要改文件。限定范围，让它先把调用链、关键文件、可能原因讲清楚。等方向对了，再让它补测试、改实现、跑验证。 前面慢一点，后面能少很多返工。 3. 权限别一开始全放开 git diff、git status、rg、npm test 这类只读或验证命令，可以适当放宽；rm -rf、强推、读 .env、碰生产配置、碰密钥证书，这些能拦就拦。 Auto Mode 可以减少确认，但它不是安全沙箱。涉及生产环境和真实凭据，还是老老实实隔离。 4. 让它自己验证结果 Anthropic 官方最佳实践里有一句我很认同：给 Claude 一个能运行的检查。测试、构建、lint、截图对比、脚本输出都可以。 5. 长任务用 Sub-Agent 或 Worktree 拆开 排查日志、搜大仓库、并行改多个模块，别都塞进一个会话里。 Sub-Agent 适合做局部调查，只把结论带回来；Worktree 适合多任务并行，一个分支修认证，一个分支改订单，互不干扰。 6. MCP、Skills、Hooks 各干各的 MCP 用来接外部系统，比如数据库、浏览器、Sentry、Notion。 Skills 用来沉淀重复流程，比如代码审查、TDD。 Hooks 用来做硬约束，比如编辑后格式化、提交前跑测试、拦截危险命令。 7. 最后一定自己看 diff 提交前至少看一眼 git diff --stat，关键文件再过一遍 diff。PR 描述和 commit message 可以让它写，但最终判断还是人来做。 Claude Code 很适合当执行力很强的助手，但边界、判断和责任，还是得握在自己手里。 ⭐️推荐阅读: <a class="normal_text_link mp_article_text_link" target="_blank" href="https://mp.weixin.qq.com/s?__biz=Mzg2OTA0Njk0OA==&mid=2247552320&idx=1&sn=a7e4e5a8d957446e6bb032d78b2fa5fb&scene=21#wechat_redirect">《SpringAI 智能面试平台》（2.0 版本已开源）</a>(Star 数量 2.1k+) <a class="normal_text_link album" target="_blank" href="https://mp.weixin.qq.com/mp/appmsgalbum?__biz=Mzg2OTA0Njk0OA==&action=getalbum&album_id=4412413577266053125&scene=126&sessionid=1777281752800#wechat_redirect">AI 应用开发面试指南：大模型、Agent、RAG、MCP、Prompt 工程</a>(累计阅读接近 50w+) <a class="normal_text_link album" target="_blank" href="https://mp.weixin.qq.com/mp/appmsgalbum?__biz=Mzg2OTA0Njk0OA==&action=getalbum&album_id=3845984209651990529&scene=126&sessionid=1779072612648#wechat_redirect">AI 编程实战指南：Claude Code、Cursor、Codex、Trae 使用技巧与面试题</a>(累计阅读接近 70w+)


**JavaGuide** (2026-06-08 14:44):

[链接] Token 暴降 59%！这个项目让 Claude Code / Codex 不再满仓库乱翻。


**JavaGuide** (2026-06-09 14:02):

[链接] 取代后端岗，又一新兴岗位崛起！这将是程序员未来10年最好的方向。


**JavaGuide** (2026-06-10 14:58):

[链接] Kimi 版 Codex 正式发布：股市分析给到夯！


**JavaGuide** (2026-06-11 18:32):

[链接] Claude 桌面版终于能接入第三方模型了！夯爆了。


**JavaGuide** (2026-06-12 18:09):

[链接] 爽用 Codex+Claude Code，免费 Token 随便用！


**JavaGuide** (2026-06-13 18:53):

[链接] Claude Fable 5 刚被禁，GLM-5.2 就全量开放了！


**JavaGuide** (2026-06-15 17:28):

[链接] 面试官坏笑：“你用 Claude Code 写代码，不怕它把项目搞炸？”，我：“怕，所以 CLAUDE.md、权限和验证，一个都不能少。”


**JavaGuide** (2026-06-16 18:29):

[链接] Spring AI 2.0.0 正式版发布！


**JavaGuide** (2026-06-17 14:49):

[链接] 面试官：“你说你懂 Loop Engineering，那 Claude Code 的 /loop 和 /goal 区别是什么？”我：“这是啥？”


**JavaGuide** (2026-06-18 14:43):

[链接] 技术Leader惊了：“你AI Coding一年了，还想转AI应用开发，Claude、Codex、Agent、Skills...你都学了？”我：“小意思！”


**JavaGuide** (2026-06-21 14:01):

[链接] Claude Code 无限 Token，夯！


**JavaGuide** (2026-06-22 17:57):

[链接] 推荐 10 个神级 Claude Code/Codex Skills！


**JavaGuide** (2026-06-23 09:32):

[链接] 今年后端这工资是认真的吗？


**JavaGuide** (2026-06-24 14:21):

[链接] 面试官：“你说你用Claude写代码，你说说你怎么维护CLAUDE.md”，我：“这是啥？”，面试官：“回去等通知吧！”


**JavaGuide** (2026-06-25 17:50):

[链接] 又一个神级 AI 插件诞生了！让 Claude Code 和 Codex 少写废代码


**JavaGuide** (2026-06-26 17:39):

[链接] 不怕大家喷我，哪怕网传的选专业榜单里，计算机已经跌出前 10，我依然觉得计算机是一个很不错的专业。 我知道这样说不讨喜，绝大部分人喜欢听到各种贬低计算机的话，这样才有流量，传播才高。 前两年有亲戚小孩问我选什么专业，我当时也是推荐计算机。当然，我这么说不是因为自己是技术博主，更不是因为推荐计算机能给我带来什么好处。 关注我这个号的大部分读者年龄都在26岁以上，已经工作至少两三年了。 计算机这几年确实没以前那么无脑香了。初中级岗位卷的很，人满为患，AI 又把很多重复编码的活儿干掉了。只会写页面、接口、CRUD，再背点八股，肯定是不够用的。 但我觉得很多人忽略了一点：学计算机不一定非要做程序员。 AI 时代对程序员肯定有冲击，但有程序员底子的人，用很多 AI 工具真的会更顺手。你知道怎么拆任务、怎么喂上下文、怎么判断结果靠不靠谱，也知道哪些地方可以自动化、批量化、流程化，这些都是优势。 流程自动化！！！还是流程自动化！！！这个在当下和未来都会是非常重要的！ 漫剧爆火之前，我就认识几个程序员朋友转过去做这块。靠自动化脚本、AI 生图，再配一套批量化的流程，硬是抓了一波红利，赚得相当多。类似的例子其实挺多的，这里就不做展开了。 四年前，我妹选专业时，是我帮她建议的。她学校新开了新媒体专业，我力排众议让她报这个。按现在的发展来看，这个选择非常正确。只不过如果她是理科，我当时大概率会更建议她报计算机，但她是文科，新媒体对她来说更合适。 所以我选专业的逻辑很简单：不看这个专业热度，重点关注这个专业未来几年能不能顺应时代。 人工智能现在挺热门，但人工智能也不是凭空来的。算法、数据结构、操作系统、网络、工程能力，这些东西绕来绕去还是计算机底子。计算机学扎实了，后面转 AI、做工具、做内容、做自动化，都有路。 而且，你想做人工智能，往深一点走，学校必须得好，而且尽量得多读几年书。 还是那句我常说的，AI 的发展趋势太猛了，这两年颠覆了我们的太多太多。但我觉得真正容易被取代的，是抵触时代发展，不会用好 AI 工具的人。 计算机没以前那么轻松能找到高薪工作，但依然值得认真考虑！ ⭐️推荐阅读: <a class="normal_text_link mp_article_text_link" target="_blank" href="https://mp.weixin.qq.com/s?__biz=Mzg2OTA0Njk0OA==&mid=2247555122&idx=1&sn=96278bed8e2b414434398b56785ea2bd&scene=21#wechat_redirect">AIGuide：AI 应用开发、AI 编程实战与面试指南</a>（对标 JavaGuide，完全开源免费） <a class="normal_text_link mp_article_text_link" target="_blank" href="https://mp.weixin.qq.com/s?__biz=Mzg2OTA0Njk0OA==&mid=2247552320&idx=1&sn=a7e4e5a8d957446e6bb032d78b2fa5fb&scene=21#wechat_redirect">《SpringAI 智能面试平台》（2.0 版本已开源）</a>(Star 数量 2.1k+)

