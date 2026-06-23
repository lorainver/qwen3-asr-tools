# luogu_query.py
import os
import json
import requests
from datetime import datetime, date, timezone, timedelta
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd  # 用于生成CSV/Excel
from luogu_problem_fetcher import fetch_and_save_problem # [新增] 洛谷元数据补全
# 替换原有的 load_config 函数和 CONFIG、COOKIES 变量定义为：
# 从配置加载器导入
from config_loader import CONFIG, COOKIES

MAX_PAGES = 20
# 从配置文件加载 HEADERS，不使用默认值
HEADERS = CONFIG.get("headers", {})

# 状态和语言映射（用于前端展示）
STATUS_MAP = {
    12: "✅ Accepted",
    11: "❌ Wrong Answer",
    13: "⚠️ Time Limit Exceeded",
    14: "❌ Unaccepted",
    15: "🚫 Runtime Error",
    16: "🔍 Output Limit Exceeded",
    20: "🔄 Compilation Error",
}

LANG_MAP = {
    "1": "C++", "2": "C", "3": "Pascal", "4": "Java", "5": "Python",
    "6": "Ruby", "7": "Go", "8": "JavaScript", "9": "Kotlin", "10": "Rust",
    "11": "PHP", "12": "C#", "13": "Swift", "14": "Scala", "15": "Haskell",
    "16": "Lua", "17": "Bash", "18": "TypeScript", "19": "OCaml", "20": "Delphi"
}

# 状态对应的 CSS 类名映射
STATUS_COLOR = {
    12: "luogu-ac",       # Accepted
    11: "luogu-wa",       # Wrong Answer
    13: "luogu-tle",      # Time Limit Exceeded
    14: "luogu-mle",      # Memory Limit Exceeded
    15: "luogu-re",       # Runtime Error
    16: "luogu-ole",      # Output Limit Exceeded
    20: "luogu-ce",       # Compilation Error
    "Unknown": "luogu-unknown"
}

# 洛谷题目元数据统一缓存目录 (指向在线IDE目录)
LUOGU_PROBLEM_CACHE = "/home/work/Cplusplus/luogu_online_ide/cache/problems"
# 保持兼容性定义
LUOGU_IDE_CACHE_DIR = LUOGU_PROBLEM_CACHE

# 确保统一缓存目录存在
os.makedirs(LUOGU_PROBLEM_CACHE, exist_ok=True)

# 难度颜色映射
DIFFICULTY_MAP = {
    0: {"color": "#bfbfbf", "text": "暂无评定", "class": "diff-0"},
    1: {"color": "#fe4c61", "text": "入门", "class": "diff-1"},
    2: {"color": "#f39c11", "text": "普及-", "class": "diff-2"},
    3: {"color": "#ffc116", "text": "普及/提高-", "class": "diff-3"},
    4: {"color": "#52c41a", "text": "普及+/提高", "class": "diff-4"},
    5: {"color": "#3498db", "text": "提高+/省选-", "class": "diff-5"},
    6: {"color": "#9d3dcf", "text": "省选/NOI-", "class": "diff-6"},
    7: {"color": "#0e1d69", "text": "NOI/NOI+/CTSC", "class": "diff-7"}
}

# 洛谷常用标签映射 (可通过 update_luogu_tags.py 自动更新)
LUOGU_TAG_MAP = {
    -2: "语言入门",
    1: "模拟",
    2: "字符串",
    3: "动态规划 DP",
    4: "搜索",
    5: "数学",
    6: "图论",
    7: "贪心",
    8: "计算几何",
    9: "暴力数据结构",
    10: "高精度",
    11: "树形数据结构",
    12: "递推",
    13: "博弈论",
    14: "1997",
    15: "1998",
    16: "1999",
    17: "2000",
    18: "2001",
    19: "2002",
    20: "2003",
    21: "2004",
    22: "2005",
    23: "2006",
    24: "2007",
    25: "2008",
    26: "2009",
    27: "2010",
    28: "2011",
    29: "2012",
    30: "2013",
    31: "2014",
    32: "2015",
    33: "2016",
    34: "2017",
    35: "2018",
    36: "2019",
    37: "2020",
    38: "重庆",
    39: "四川",
    40: "河南",
    41: "莫队",
    42: "线段树",
    43: "倍增",
    44: "线性数据结构",
    45: "二分",
    46: "USACO",
    47: "并查集",
    48: "各省省选",
    49: "点分治",
    50: "平衡树",
    51: "堆",
    52: "集训队互测",
    53: "树状数组",
    54: "递归",
    55: "树上启发式合并",
    56: "单调队列",
    57: "POI（波兰）",
    58: "2021",
    59: "2022",
    60: "2023",
    61: "2024",
    62: "2025",
    63: "LGV 引理",
    64: "矩阵树定理",
    65: "颜色段均摊（珂朵莉树 ODT）",
    66: "原根",
    67: "三分",
    68: "Kruskal 重构树",
    69: "多项式",
    70: "福建省历届夏令营",
    71: "矩阵运算",
    72: "数论",
    73: "算法",
    74: "数据结构",
    75: "来源",
    76: "时间",
    77: "NOI",
    78: "离散化",
    79: "网络流",
    80: "高级数据结构",
    81: "洛谷原创",
    82: "NOIP 普及组",
    83: "NOIP 提高组",
    85: "APIO",
    87: "地区",
    88: "浙江",
    89: "上海",
    90: "福建",
    91: "江苏",
    92: "安徽",
    93: "湖南",
    94: "北京",
    95: "河北",
    96: "广东",
    97: "山东",
    98: "吉林",
    99: "NOI 导刊",
    100: "cdq 分治",
    101: "后缀自动机 SAM",
    102: "IOI",
    103: "交互题",
    104: "提交答案",
    105: "特殊题目",
    107: "Special Judge",
    108: "O2优化",
    110: "﻿基础算法",
    111: "枚举",
    112: "分治",
    113: "排序",
    114: "山西",
    115: "CCO（加拿大）",
    116: "CCC（加拿大）",
    117: "CEOI（中欧）",
    118: "eJOI（欧洲）",
    119: "快速排序",
    120: "堆排序",
    121: "希尔排序",
    122: "信息论",
    123: "查找算法",
    124: "顺序查找",
    126: "广度优先搜索 BFS",
    127: "深度优先搜索 DFS",
    128: "剪枝",
    129: "记忆化搜索",
    130: "启发式搜索",
    131: "迭代加深搜索",
    132: "启发式迭代加深搜索 IDA*",
    133: "Dancing Links",
    134: "爬山算法 Local search",
    135: "模拟退火",
    136: "随机调整",
    137: "遗传算法",
    139: "背包 DP",
    140: "环形 dp",
    141: "数位 DP",
    143: "多维状态",
    144: "区间 DP",
    146: "动态规划优化",
    148: "优先队列",
    149: "矩阵加速",
    150: "斜率优化",
    151: "状态合并",
    152: "树形 DP",
    153: "凸完全单调性（wqs 二分）",
    154: "四边形不等式",
    155: "图论建模",
    156: "邻接矩阵",
    157: "邻接表",
    158: "图遍历",
    159: "拓扑排序",
    160: "最短路",
    161: "江西",
    162: "贵州",
    163: "广西",
    164: "陕西",
    166: "生成树",
    167: "辽宁",
    168: "云南",
    169: "生成树的另类算法",
    170: "次小生成树",
    171: "特殊生成树",
    172: "平面图",
    173: "最小环",
    174: "负权环",
    175: "连通块",
    176: "2-SAT",
    177: "平面图欧拉公式",
    179: "强连通分量",
    180: "Tarjan",
    181: "双连通分量",
    182: "欧拉回路",
    183: "AOV",
    184: "AOE",
    185: "差分约束",
    186: "仙人掌",
    187: "二分图",
    188: "匈牙利算法",
    189: "一般图的最大匹配",
    190: "Konig定理",
    191: "带权二分图匹配",
    192: "KM算法",
    193: "稳定婚姻系统",
    195: "Dinic",
    196: "Sap",
    197: "上下界网络流",
    198: "最小割",
    199: "闭合图",
    200: "最小点权覆盖集",
    201: "最大点权独立集",
    202: "分数规划",
    203: "最大密度子图",
    204: "费用流",
    205: "最短路增广费用流",
    207: "最小费用可行流",
    208: "树的遍历",
    209: "树上距离",
    210: "节点到根的距离",
    211: "最近公共祖先 LCA",
    212: "节点间的距离",
    213: "树的直径",
    214: "霍夫曼树",
    215: "可并堆",
    216: "斜堆",
    217: "二项堆",
    218: "AVL",
    219: "Treap",
    220: "SBT",
    221: "Splay",
    222: "静态排序树",
    223: "替罪羊树",
    224: "二维线段树",
    225: "矩形树",
    227: "动态树",
    228: "树链剖分",
    229: "动态树 LCT",
    230: "树论",
    231: "RMQ",
    232: "树套树",
    233: "可持久化线段树",
    234: "可持久化",
    235: "哈希 hashing",
    236: "ELFhash",
    237: "SDBM",
    238: "BKDR",
    239: "素数判断,质数,筛法",
    241: "最大公约数 gcd",
    242: "扩展欧几里德算法",
    243: "不定方程",
    244: "进制",
    246: "群论",
    247: "置换",
    248: "Pólya 定理",
    249: "虚树",
    250: "中国剩余定理 CRT",
    251: "莫比乌斯反演",
    252: "组合数学",
    253: "排列组合",
    254: "前缀和",
    255: "二项式定理",
    256: "康托展开",
    257: "袋与球问题",
    258: "鸽笼原理",
    259: "容斥原理",
    260: "Fibonacci 数列",
    261: "Catalan 数",
    262: "Stirling 数",
    263: "A*  算法",
    264: "生成函数",
    265: "线性规划",
    266: "概率论",
    267: "简单概率",
    269: "Bayes",
    270: "期望",
    271: "线性代数",
    272: "矩阵乘法",
    273: "线性递推",
    274: "高斯消元",
    275: "异或方程组",
    276: "逆元",
    277: "线性基",
    278: "微积分",
    280: "导数",
    281: "积分",
    282: "定积分",
    283: "三维计算几何",
    284: "级数",
    285: "基本数组",
    286: "向量",
    287: "栈",
    288: "队列",
    289: "分块",
    290: "ST 表",
    291: "凸包",
    292: "叉积",
    293: "线段相交",
    295: "半平面交",
    296: "最近点对",
    298: "扫描线",
    299: "旋转卡壳",
    300: "字典树 Trie",
    301: "AC 自动机",
    302: "KMP 算法",
    303: "后缀数组 SA",
    304: "后缀树",
    305: "有限状态自动机",
    307: "简单密码学",
    308: "其它技巧",
    309: "随机化",
    311: "博弈树",
    312: "Shannon 开关游戏",
    313: "快速傅里叶变换 FFT",
    314: "位运算",
    316: "整体二分",
    318: "构造",
    320: "基环树",
    321: "K-D Tree",
    322: "Lucas 定理",
    323: "轮廓线 DP",
    324: "快速数论变换 NTT",
    325: "回文自动机 PAM",
    326: "快速沃尔什变换 FWT",
    327: "快速莫比乌斯变换 FMT",
    328: "天津",
    329: "Manacher 算法",
    330: "差分",
    331: "CTT（清华集训/北大集训）",
    332: "网络流与线性规划 24 题",
    333: "COCI（克罗地亚）",
    334: "BalticOI（波罗的海）",
    335: "ICPC",
    336: "JOI（日本）",
    337: "洛谷月赛",
    338: "2026",
    339: "2027",
    340: "2028",
    341: "2077",
    342: "CSP-S 提高级",
    343: "CSP-J 入门级",
    344: "1996",
    345: "双指针 two-pointer",
    346: "AGM",
    347: "NOI Online",
    348: "Ynoi",
    350: "圆方树",
    351: "通信题",
    353: "顺序结构",
    354: "分支结构",
    355: "循环结构",
    356: "数组",
    357: "字符串（入门）",
    358: "结构体",
    359: "函数与递归",
    360: "链表",
    361: "蓝桥杯国赛",
    362: "2078",
    363: "蓝桥杯省赛",
    364: "Dilworth 定理",
    365: "Ad-hoc",
    367: "2029",
    368: "笛卡尔树",
    369: "拟阵",
    370: "Nim 积",
    371: "根号分治",
    372: "拉格朗日反演",
    373: "模拟费用流",
    374: "分散层叠",
    375: "均摊分析",
    376: "分类讨论",
    377: "李超线段树",
    378: "吉司机线段树 segment tree beats",
    379: "线段树合并",
    380: "折半搜索 meet in the middle",
    381: "省赛/邀请赛",
    382: "动态树分治",
    383: "传智杯",
    385: "单调栈",
    386: "语言月赛",
    387: "杨表",
    388: "类欧几里得算法",
    389: "PA（波兰）",
    390: "THUPC",
    391: "Berlekamp-Massey(BM) 算法",
    393: "ROI（俄罗斯）",
    394: "EGOI（欧洲/女生）",
    396: "梯度下降法",
    397: "湖北",
    398: "黑龙江",
    399: "海南",
    400: "甘肃",
    401: "青海",
    402: "台湾",
    403: "内蒙古",
    404: "西藏",
    405: "宁夏",
    406: "新疆",
    407: "香港",
    408: "澳门",
    409: "GESP",
    410: "Prüfer 序列",
    411: "调和级数",
    412: "拉格朗日乘数法",
    413: "近似算法",
    414: "随机算法",
    415: "欧拉降幂",
    416: "集合幂级数，子集卷积",
    417: "拉格朗日插值法",
    419: "Lyndon 分解",
    420: "济南",
    421: "南京",
    422: "青岛",
    423: "Stern-Brocot 树",
    424: "2079",
    426: "NOI 系列赛事",
    427: "经典套题",
    428: "国际知名赛事",
    429: "洛谷比赛",
    430: "大学竞赛",
    431: "其他竞赛",
    432: "THUSC",
    434: "高校校赛",
    435: "DP 套 DP",
    436: "NOISG（新加坡）",
    437: "NordicOI（北欧）",
    438: "THUWC",
    439: "BalkanOI（巴尔干半岛）",
    440: "KOI（韩国）",
    441: "RMI（罗马尼亚）",
    442: "CSP-X 小学组",
    443: "动态 DP",
    444: "线性 DP",
    445: "SG 函数",
    446: "线段树分治",
    447: "离线处理",
    448: "整除分块",
    449: "极角排序",
    450: "弦图",
    451: "Dirichlet 卷积",
    452: "大步小步算法 BSGS",
    453: "二次剩余",
    454: "行列式",
    455: "Bézout 定理",
    456: "概率生成函数",
    457: "随机游走 Markov Chain",
    458: "鞅的停时定理",
    459: "WC",
    460: "CTSC/CTS",
    461: "杜教筛",
    462: "欧拉函数",
    463: "决策单调性",
    464: "状压 DP",
    465: "bitset",
    466: "特征值",
    467: "组合优化",
    468: "整数规划",
    469: "半正定规划",
    470: "原始对偶",
    471: "最大流最小割定理",
    472: "全局平衡二叉树",
    473: "哈希表",
    474: "Z 函数",
    475: "筛法",
    476: "Floyd 算法",
    477: "启发式合并",
    478: "COI（克罗地亚）",
    479: "ROIR（俄罗斯）",
    480: "单位根反演",
    482: "平面几何",
    483: "树的重心",
    484: "保序回归",
    485: "Code+",
    486: "梦熊比赛",
    487: "信息与未来",
    488: "科创活动",
    489: "BCSP-X",
    492: "小学活动",
    493: "初中活动",
    494: "科大国创杯",
    495: "蓝桥杯青少年组",
    496: "后缀平衡树",
    497: "国内省市",
    498: "国内赛站",
    499: "国际赛区",
    500: "NERC/NEERC",
    501: "SEERC",
    502: "CERC",
    503: "NWRRC",
    504: "STL",
    505: "INOI（伊朗）",
    506: "UOI（乌克兰）",
    507: "整体转移",
    508: "斜率维护技巧 slope trick",
    509: "EC Final",
    510: "WF",
    511: "NAC",
    512: "JOISC/JOIST（日本）",
    513: "COTS（克罗地亚）",
    514: "Google Code Jam",
    515: "Moscow Olympiad",
    516: "CSPro",
    518: "PO（瑞典）",
    519: "PAIO",
    520: "杭州",
    521: "昆明",
    522: "西安",
    523: "模板题",
    524: "反悔贪心",
    525: "闵可夫斯基和 Minkowski sum",
    526: "CCPC",
    527: "哈尔滨",
    528: "首尔",
    529: "横浜",
    530: "广义串并联图",
    531: "二区间合并（猫树分治）",
    532: "SWERC",
    533: "MCC/MCO（马来西亚）",
    534: "成都",
    535: "KTSC（韩国）",
    536: "雅加达",
    537: "IATI（保加利亚/东欧）",
    538: "Google Kick Start",
    539: "KTT / Kinetic Tournament Tree",
}

# 根存储目录
ROOT_STORAGE_DIR = "./luogu_data"
os.makedirs(ROOT_STORAGE_DIR, exist_ok=True)

def get_latest_local_record_id(username):
    """获取本地存储中最新的一条记录ID，用于增量更新"""
    user_dir = os.path.join(ROOT_STORAGE_DIR, username)
    main_data_file = os.path.join(user_dir, f"{username}_all_records.json")

    if not os.path.exists(main_data_file):
        return None

    try:
        with open(main_data_file, "r", encoding="utf-8") as f:
            records = json.load(f)
            if records:
                # 找到记录中 record_id 最大的（假设 ID 自增，越大越新）
                # 注意处理 record_id 可能为非数字的情况（虽然洛谷通常是数字）
                try:
                    latest = max(records, key=lambda x: int(x.get('record_id', 0)))
                    return str(latest.get('record_id'))
                except ValueError:
                    # 如果转换失败，退回到字符串比较或直接取第一条（取决于存储顺序）
                    return records[0].get('record_id') if records else None
    except Exception:
        return None
    return None

def parse_date_to_timestamp(date_str):
    """将 'YYYY-MM-DD' 转为 UTC+8 的 00:00:00 时间戳（秒）"""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        tz = timezone(timedelta(hours=8))
        dt = dt.replace(tzinfo=tz)
        return int(dt.timestamp())
    except Exception as e:
        raise ValueError(f"日期格式错误（应为 YYYY-MM-DD）: {date_str}") from e

def get_time_range(start_date, end_date=None):
    """返回 [start_ts, end_ts) 的时间戳范围（左闭右开）"""
    start_ts = parse_date_to_timestamp(start_date)
    if not end_date:
        end_date = start_date
    end_ts = parse_date_to_timestamp(end_date) + 86400  # 加一天（覆盖结束日期全天）
    return start_ts, end_ts

def fetch_raw_records(username, start_ts, end_ts, max_pages=20):
    """获取原始提交记录（支持增量更新，避免重复抓取）"""
    # 获取本地最新的记录ID作为断点
    latest_local_id = get_latest_local_record_id(username)
    if latest_local_id:
        print(f"📡 [增量模式] 本地最新记录 ID: {latest_local_id}，抓取到此处将自动停止。")

    all_records = []
    stop_fetching = False

    for page in range(1, max_pages + 1):
        if stop_fetching:
            break

        url = "https://www.luogu.com.cn/record/list"
        params = {
            "user": username,
            "page": page,
            "_contentOnly": "1"
        }

        try:
            resp = requests.get(url, params=params, cookies=COOKIES, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            if "currentData" not in data or "records" not in data["currentData"]:
                print("❌ API 返回异常，可能 Cookie 失效或用户不存在")
                break

            records = data["currentData"]["records"]["result"]
            if not records:
                break

            filtered = []
            for r in records:
                current_id = str(r.get("id", ""))

                # 检查是否遇到了本地已有的记录
                if latest_local_id and current_id == latest_local_id:
                    print(f"🛑 [增量模式] 已同步到已知记录 {current_id}，停止后续抓取。")
                    stop_fetching = True
                    break

                submit_time = r.get("submitTime", 0)
                if start_ts <= submit_time < end_ts:
                    # 保存原始数据（尽可能完整）
                    filtered.append({
                        "record_id": current_id,
                        "problem_pid": r.get("problem", {}).get("pid", "Unknown"),
                        "problem_title": r.get("problem", {}).get("title", "Unknown"),
                        "user": r.get("user", {}).get("name", "Unknown"),
                        "result": r.get("status", "Unknown"),
                        "time": f"{r.get('time', 0)}ms",
                        "memory": f"{r.get('memory', 0)}KB",
                        "submit_time": submit_time,
                        "language": str(r.get("language", "Unknown")),
                        "code_length": f"{r.get('codeLength', 0)}B",
                        "raw_data": r  # 保存原始响应数据，便于后续扩展
                    })

            if filtered:
                all_records.extend(filtered)

            # 时间范围判断：如果最后一条记录的时间早于起始时间，后续页面肯定不在范围内
            last_submit = records[-1].get("submitTime", 0) if records else 0
            if last_submit < start_ts:
                break

        except Exception as e:
            print(f"请求失败 (页 {page}): {e}")
            break

    # 去重（根据record_id）
    seen = set()
    unique_records = []
    for r in all_records:
        if r["record_id"] not in seen:
            seen.add(r["record_id"])
            unique_records.append(r)

    return unique_records


def _load_problem_metadata(pid):
    """加载题目元数据（难度+标签），优先使用线程安全的常驻内存缓存，兼顾后台同步更新"""
    difficulty_info = {"text": "", "class": "", "index": -1}
    tag_names = []

    try:
        from shared_resources import get_problem_cached
        prob_data = get_problem_cached(pid, LUOGU_PROBLEM_CACHE, is_bashu=False)
    except Exception as cache_err:
        print(f"⚠️ [缓存读透系统] 内存检索发生异常: {cache_err}")
        prob_data = None

    # 如果缓存和本地磁盘都未命中，则尝试同步抓取并加入后台队列
    if not prob_data:
        try:
            success = fetch_and_save_problem(pid)
            if success:
                from shared_resources import get_problem_cached
                prob_data = get_problem_cached(pid, LUOGU_PROBLEM_CACHE, is_bashu=False)
            else:
                _enqueue_missing_problem(pid)
        except Exception as e:
            print(f"ERROR: _load_problem_metadata - 同步抓取异常 PID {pid}: {e}")
            _enqueue_missing_problem(pid)

    if prob_data:
        try:
            diff_val = prob_data.get('difficulty', 0)
            mapped = DIFFICULTY_MAP.get(diff_val, DIFFICULTY_MAP[0])
            difficulty_info = {
                "text": prob_data.get('difficulty_text', mapped['text']),
                "class": mapped['class'],
                "index": diff_val
            }
            raw_tags = prob_data.get('tags', [])
            for tid in raw_tags:
                try:
                    tid_int = int(tid)
                    name = LUOGU_TAG_MAP.get(tid_int)
                    if name:
                        tag_names.append(name)
                except Exception as tag_err:
                    print(f"WARNING: _load_problem_metadata - 标签解析发生异常 {tid} (PID {pid}): {tag_err}")
                    continue
        except Exception as e:
            print(f"ERROR: _load_problem_metadata - 解析缓存元数据异常 PID {pid}: {e}")
            _enqueue_missing_problem(pid)

    return difficulty_info, tag_names


def _enqueue_missing_problem(pid):
    """将缺失的题目加入后台补全队列"""
    try:
        from shared_resources import LUOGU_MISSING_QUEUE, LUOGU_PROCESSING_SET
        if pid and pid not in LUOGU_PROCESSING_SET:
            LUOGU_PROCESSING_SET.add(pid)
            LUOGU_MISSING_QUEUE.put(pid)
            print(f"📡 [元数据补全] 题目 {pid} 缺失，已加入后台抓取队列。")
    except Exception as e:
        print(f"Error enqueueing problem {pid}: {e}")


def _format_single_record(r):
    """格式化单条记录"""
    readable_time = datetime.fromtimestamp(r["submit_time"]).strftime("%Y-%m-%d %H:%M:%S")
    result_int = int(r["result"]) if str(r["result"]).isdigit() else r["result"]
    result_text = STATUS_MAP.get(result_int, f"❓ Status {r['result']}")
    status_class = STATUS_COLOR.get(result_int, "luogu-unknown")
    lang_name = LANG_MAP.get(r["language"], r["language"])
    problem_link = f"http://8.137.117.134/?pid={r['problem_pid']}"

    difficulty_info, tag_names = _load_problem_metadata(r['problem_pid'])

    return {
        "record_id": r["record_id"],
        "problem_pid": r["problem_pid"],
        "problem_title": r["problem_title"],
        "problem_link": problem_link,
        "result_text": result_text,
        "score": r.get("raw_data", {}).get("score"),
        "status_class": status_class,
        "lang_name": lang_name,
        "run_time": r["time"],
        "memory_usage": r["memory"],
        "code_length": r["code_length"],
        "submit_time": readable_time,
        "raw_submit_time": r["submit_time"],
        "difficulty": difficulty_info,
        "tags": tag_names
    }


def format_records(records):
    """格式化记录（供前端展示和文件生成）"""
    if not records:
        return []

    with ThreadPoolExecutor(max_workers=min(8, len(records))) as executor:
        formatted_records = list(executor.map(_format_single_record, records))

    formatted_records.sort(key=lambda x: x["raw_submit_time"], reverse=True)
    return formatted_records

def get_radar_statistics(records):
    """
    计算能力雷达图数据
    只统计 AC 的题目，且去重
    """
    # 核心关注的八大维度 (新增 贪心、枚举)
    CORE_DIMENSIONS = ["模拟", "搜索", "动态规划, DP", "数据结构", "图论", "数学", "贪心", "枚举"]
    # 维度别名（用于图表显示更简洁）
    DIMENSION_ALIAS = {
        "模拟": "模拟",
        "搜索": "搜索",
        "动态规划, DP": "动态规划",
        "数据结构": "数据结构",
        "图论": "图论",
        "数学": "数学",
        "贪心": "贪心",
        "枚举": "枚举"
    }

    # 基础练习关键字，用于过滤，不计入核心能力分析
    BASIC_KEYWORDS = ["数组", "循环", "顺序结构", "分支结构", "字符串（入门）", "函数与递归（入门）"]

    stats = {dim: 0 for dim in CORE_DIMENSIONS}
    tag_solve_counts = {dim: 0 for dim in CORE_DIMENSIONS} # 用于计算饱和度
    seen_pids = set()

    for r in records:
        # 1. 必须是 AC
        if "Accepted" not in r['result_text']:
            continue

        # 2. 题目去重
        real_pid = r.get('problem_pid')
        if not real_pid or real_pid in seen_pids:
            continue
        seen_pids.add(real_pid)

        # 过滤基础练习
        title = r.get('problem_title', '')
        if any(kw in title for kw in BASIC_KEYWORDS):
            continue

        # 3. 统计标签
        if 'tags' in r and r['tags']:
            # 过滤包含基础标签的题目
            if any(any(kw in t for kw in BASIC_KEYWORDS) for t in r['tags']):
                continue

            # [核心修改] 复合加权系统
            diff_idx = r.get('difficulty', {}).get('index', 0)
            base_weight = 1.0 + (diff_idx * 0.2)

            is_template = any("模板" in t for t in r['tags'])
            weight_val = base_weight * (1.5 if is_template else 1.0)

            def add_weighted_score(dim_name):
                # 权重饱和度: 单题贡献度随数量逐渐降低 (衰减系数 0.95)
                current_count = tag_solve_counts.get(dim_name, 0)
                decay_factor = 0.95 ** current_count
                stats[dim_name] += weight_val * decay_factor
                tag_solve_counts[dim_name] = current_count + 1

            for tag in r['tags']:
                matched = False
                if tag in stats:
                    add_weighted_score(tag)
                    matched = True

                if not matched:
                    if "搜索" in tag or "DFS" in tag or "BFS" in tag:
                        add_weighted_score("搜索")
                    elif "DP" in tag or "背包" in tag:
                        add_weighted_score("动态规划, DP")
                    elif "树" in tag or "栈" in tag or "队" in tag or "链表" in tag or "堆" in tag:
                        add_weighted_score("数据结构")
                    elif "图" in tag or "路" in tag:
                        add_weighted_score("图论")
                    elif "数" in tag and "数据" not in tag:
                        add_weighted_score("数学")
                    elif "贪心" in tag:
                        add_weighted_score("贪心")
                    elif "枚举" in tag or "暴力" in tag:
                        add_weighted_score("枚举")
                    elif "分治" in tag:
                        # 分治虽然不单独在雷达图，但可以按性质归入搜索或数学，这里暂不计入核心六/八维
                        pass

    # 格式化为 ECharts 需要的格式
    indicators = []
    values = []
    max_val = max(stats.values()) if stats.values() else 10
    max_val = max(max_val, 5) # 至少显示到5
    #稍微放大一点 max，让图好看点
    max_val = int(max_val * 1.2)

    for dim in CORE_DIMENSIONS:
        indicators.append({
            "name": DIMENSION_ALIAS[dim],
            "max": max_val
        })
        values.append(stats[dim])

    return {
        "indicators": indicators,
        "values": values
    }

def get_heatmap_statistics(records):
    """
    计算热力图数据 (日期 -> 提交次数)
    """
    daily_counts = defaultdict(int)
    for r in records:
        date_str = r['submit_time'].split(' ')[0]
        daily_counts[date_str] += 1
    return [[d, c] for d, c in daily_counts.items()]


def get_weakness_analysis(records, top_n=5):
    """
    分析薄弱知识点，返回错误率最高的知识点及其推荐练习

    Args:
        records: 格式化后的记录列表
        top_n: 返回前N个薄弱点

    Returns:
        dict: {
            "weakness_list": [
                {
                    "tag": "动态规划",
                    "total_submits": 20,
                    "ac_count": 8,
                    "error_rate": 0.6,
                    "failed_problems": [
                        {"pid": "P1001", "title": "A+B问题", "submit_count": 7, "is_ac": False, "difficulty": {...}},
                        ...
                    ],
                    "recommend_problems": [
                        {"pid": "P1002", "title": "题解", "difficulty": {"text": "入门", "class": "diff-1"}},
                        ...
                    ]
                },
                ...
            ]
        }
    """
    tag_stats = defaultdict(lambda: {"total": 0, "ac": 0, "problems": {}})

    for r in records:
        if 'tags' not in r or not r['tags']:
            continue

        is_ac = "Accepted" in r['result_text']
        pid = r.get('problem_pid')
        if not pid:
            continue

        title = r.get('problem_title', '')
        difficulty = r.get('difficulty', {})

        for tag in r['tags']:
            tag_stats[tag]["total"] += 1
            if is_ac:
                tag_stats[tag]["ac"] += 1

            if pid not in tag_stats[tag]["problems"]:
                tag_stats[tag]["problems"][pid] = {
                    "pid": pid,
                    "title": title,
                    "submit_count": 0,
                    "is_ac": False,
                    "difficulty": difficulty
                }

            tag_stats[tag]["problems"][pid]["submit_count"] += 1
            if is_ac:
                tag_stats[tag]["problems"][pid]["is_ac"] = True

    weakness_list = []
    for tag, stats in tag_stats.items():
        if stats["total"] < 3:
            continue

        error_rate = (stats["total"] - stats["ac"]) / stats["total"]
        if error_rate > 0:
            failed_problems = []
            for pid, problem_data in stats["problems"].items():
                if not problem_data["is_ac"]:
                    failed_problems.append({
                        "pid": pid,
                        "title": problem_data["title"],
                        "submit_count": problem_data["submit_count"],
                        "is_ac": problem_data["is_ac"],
                        "difficulty": problem_data["difficulty"]
                    })

            failed_problems.sort(key=lambda x: x["submit_count"], reverse=True)

            weakness_list.append({
                "tag": tag,
                "total_submits": stats["total"],
                "ac_count": stats["ac"],
                "error_rate": round(error_rate, 2),
                "failed_problems": failed_problems
            })

    weakness_list.sort(key=lambda x: x["error_rate"], reverse=True)

    weak_results = []
    for item in weakness_list[:top_n]:
        # [核心优化] 推荐逻辑：直接从该标签的“失败题目”中选取最简单的 N 道
        # 排序失败题目，按难度升序
        item["failed_problems"].sort(key=lambda x: x["difficulty"].get("index", 0))
        recommend_problems = []
        for p in item["failed_problems"]:
            recommend_problems.append({
                "pid": p["pid"],
                "title": p["title"],
                "difficulty": p["difficulty"]
            })
            if len(recommend_problems) >= 3: # 推荐前3个
                break

        if recommend_problems:
            item["recommend_problems"] = recommend_problems
        else:
            item["recommend_problems"] = [] # 如果没有失败题目，则为空列表

        weak_results.append(item)

    return {
        "weakness_list": weak_results
    }

def save_and_merge_records(username, new_records):
    """保存新数据并与历史数据整合，返回整合后的所有记录"""
    # 创建用户目录
    user_dir = os.path.join(ROOT_STORAGE_DIR, username)
    os.makedirs(user_dir, exist_ok=True)

    # 主数据文件（存储该用户所有记录）
    main_data_file = os.path.join(user_dir, f"{username}_all_records.json")

    # 读取历史数据
    history_records = []
    if os.path.exists(main_data_file):
        with open(main_data_file, "r", encoding="utf-8") as f:
            history_records = json.load(f)

    # 合并新数据和历史数据，去重（根据record_id）
    all_records = history_records + new_records
    seen = set()
    unique_records = []
    for r in all_records:
        if r["record_id"] not in seen:
            seen.add(r["record_id"])
            unique_records.append(r)

    # 按提交时间正序排序（便于按时间展示）
    unique_records.sort(key=lambda x: x["submit_time"])

    # 保存整合后的数据
    with open(main_data_file, "w", encoding="utf-8") as f:
        json.dump(unique_records, f, ensure_ascii=False, indent=2)

    # 生成格式化的展示文件（CSV/Excel/MD），传递main_data_file路径
    generate_display_files(username, unique_records, main_data_file)

    return unique_records

def generate_display_files(username, records, main_data_file):
    """生成CSV/Excel/MD展示文件（接收main_data_file参数）"""
    if not records:
        return

    user_dir = os.path.join(ROOT_STORAGE_DIR, username)
    # 格式化数据（用于CSV/Excel）
    formatted_for_table = []
    for r in records:
        readable_time = datetime.fromtimestamp(r["submit_time"]).strftime("%Y-%m-%d %H:%M:%S")
        # 尝试从 raw_data 中提取分数
        score = r.get("raw_data", {}).get("score")
        if score is not None:
            try:
                # 去除 .0
                if float(score) == int(float(score)):
                    score = int(float(score))
            except (ValueError, TypeError):
                pass

        formatted_for_table.append({
            "提交ID": r["record_id"],
            "题目编号": r["problem_pid"],
            "题目标题": r["problem_title"],
            "提交者": r["user"],
            "结果代码": r["result"],
            "分数": score,
            "运行时间": r["time"],
            "内存占用": r["memory"],
            "提交时间": readable_time,
            "语言ID": r["language"],
            "代码长度": r["code_length"]
        })

    # 按提交时间倒序排序
    formatted_for_table.sort(key=lambda x: x["提交时间"], reverse=True)

    # 生成CSV
    csv_file = os.path.join(user_dir, f"{username}_all_records.csv")
    df = pd.DataFrame(formatted_for_table)
    df.to_csv(csv_file, index=False, encoding="utf-8-sig")

    # 生成Excel
    excel_file = os.path.join(user_dir, f"{username}_all_records.xlsx")
    df.to_excel(excel_file, index=False, engine="openpyxl")

    # 生成MD
    md_file = os.path.join(user_dir, f"{username}_all_records.md")
    # 按日期分组
    grouped = defaultdict(list)
    for r in records:
        date_str = datetime.fromtimestamp(r["submit_time"]).strftime("%Y-%m-%d")
        grouped[date_str].append(r)

    md_lines = []
    md_lines.append(f"# 📅 {username} 的洛谷提交记录（整合所有时间）")
    md_lines.append(f"> 最后更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    md_lines.append(f"> 总提交记录数：{len(records)}")
    md_lines.append("")

    for date_key in sorted(grouped.keys()):
        md_lines.append(f"## 🗓️ {date_key}")
        md_lines.append("")
        for r in grouped[date_key]:
            result_int = int(r["result"]) if str(r["result"]).isdigit() else r["result"]
            result_text = STATUS_MAP.get(result_int, f"❓ Status {r['result']}")
            # 尝试获取分数
            score = r.get("raw_data", {}).get("score")
            score_val = score
            if score is not None:
                try:
                    if float(score) == int(float(score)):
                        score_val = int(float(score))
                except (ValueError, TypeError):
                    pass
            score_text = f" ({score_val}分)" if score is not None and result_int != 12 else ""

            lang_name = LANG_MAP.get(r["language"], r["language"])
            pid = r["problem_pid"]
            title = r["problem_title"]
            problem_link = f"[{pid} - {title}](https://www.luogu.com.cn/problem/{pid})"
            detail = f"- {problem_link} | {result_text}{score_text} | {lang_name} | {r['time']} / {r['memory']} | {r['code_length']}"
            md_lines.append(detail)
        md_lines.append("")

    with open(md_file, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    print(f"\n🎉 数据已整合保存至用户目录：{user_dir}")
    print(f"  - 主数据文件：{os.path.basename(main_data_file)}")
    print(f"  - CSV文件：{os.path.basename(csv_file)}")
    print(f"  - Excel文件：{os.path.basename(excel_file)}")
    print(f"  - MD文件：{os.path.basename(md_file)}")

def fetch_user_records_in_range(username, start_ts, end_ts, max_pages=20):
    """获取用户指定时间范围内的提交记录（整合本地数据+返回前端数据）"""
    # 1. 获取原始新数据
    new_raw_records = fetch_raw_records(username, start_ts, end_ts, max_pages)
    # 2. 保存并整合到本地
    merged_raw_records = save_and_merge_records(username, new_raw_records)
    # 3. 格式化数据供前端展示
    # 从整合后的全量数据中，过滤出本次查询时间范围内的记录
    current_records = [r for r in merged_raw_records if start_ts <= r["submit_time"] < end_ts]
    formatted_records = format_records(current_records)

    # 按日期分组（供前端展示）
    grouped_records = defaultdict(list)
    for r in formatted_records:
        date_str = r["submit_time"].split(" ")[0]  # 提取日期部分
        grouped_records[date_str].append(r)

    # 计算本次查询的时间范围
    start_date = datetime.fromtimestamp(start_ts).strftime("%Y-%m-%d")
    end_date = datetime.fromtimestamp(end_ts - 1).strftime("%Y-%m-%d")

    # 计算所有统计数据
    submission_summary = _calculate_submission_summary(formatted_records)
    radar_statistics = get_radar_statistics(formatted_records)
    heatmap_statistics = get_heatmap_statistics(formatted_records)
    weakness_analysis = get_weakness_analysis(merged_raw_records) # 薄弱点分析基于全量数据

    return {
        "total": len(formatted_records),
        "start_date": start_date,
        "end_date": end_date,
        "username": username,
        "grouped_records": dict(grouped_records),
        "all_records": formatted_records, # 原始格式化数据
        "local_storage_path": os.path.join(ROOT_STORAGE_DIR, username),
        "submission_summary": submission_summary, # 新增的汇总统计
        "statistics": { # 图表相关的统计
            "radar": radar_statistics,
            "heatmap": heatmap_statistics,
            "weakness": weakness_analysis,
            "failed_problems": get_failed_problems(formatted_records), # 未AC题目列表
            "analysis_range": "current_range" # 标识统计范围
        }
    }

def _calculate_submission_summary(records):
    """
    计算提交记录的汇总统计信息，包括AC/未AC题目数、尝试次数等。
    """
    summary = {
        "ac_problems_count": defaultdict(int), # 按难度分类的AC题目数
        "ac_attempts_count": defaultdict(int), # 按难度分类的AC尝试次数
        "ac_problems_list": defaultdict(list), # 按难度分类的AC题目列表
        "unsolved_problems_count": defaultdict(int), # 按难度分类的未AC题目数
        "unsolved_attempts_count": defaultdict(int), # 按难度分类的未AC尝试次数
        "unsolved_problems_list": defaultdict(list), # 按难度分类的未AC题目列表
        "total_ac_problems": 0,
        "total_unsolved_problems": 0,
        "total_attempts": 0, # 总提交次数
        "total_ac_attempts": 0, # AC题目的总尝试次数
        "total_unsolved_attempts": 0, # 未AC题目的总尝试次数
    }

    # 用于追踪每个题目的AC状态和尝试次数
    problem_stats = defaultdict(lambda: {
        "pid": None,
        "title": "未知题目",
        "difficulty_text": "未知",
        "difficulty_level": 0,
        "is_ac": False,
        "attempts": 0,
        "ac_attempts": 0, # 首次AC前的尝试次数
        "submissions": [], # 存储所有提交记录 (时间, 分数)
        "max_score": 0,
        "first_ts": None,
        "last_ts": None
    })

    # 必须按时间正序（从旧到新）处理，才能正确计算“首次AC前的尝试次数”
    # 因为传入的 records 默认是倒序（最新在前）
    for r in reversed(records):
        pid = r.get('problem_pid')
        if not pid:
            continue

        difficulty_level = r.get('difficulty', {}).get('index', 0)
        difficulty_text = DIFFICULTY_MAP.get(difficulty_level, {}).get('text', '未知')
        submit_ts = r.get('raw_submit_time', 0)

        problem_stats[pid]["pid"] = pid
        problem_stats[pid]["title"] = r.get('problem_title', pid)
        problem_stats[pid]["difficulty_text"] = difficulty_text
        problem_stats[pid]["difficulty_level"] = difficulty_level
        problem_stats[pid]["attempts"] += 1
        summary["total_attempts"] += 1

        # 记录首尾时间
        if problem_stats[pid]["first_ts"] is None:
            problem_stats[pid]["first_ts"] = submit_ts
        problem_stats[pid]["last_ts"] = submit_ts

        # 记录提交历史
        score_val = r.get('score', '0')
        try:
            # 统一处理分数显示
            display_score = int(float(score_val))
            if display_score > problem_stats[pid]["max_score"]:
                problem_stats[pid]["max_score"] = display_score
        except:
            display_score = score_val

        problem_stats[pid]["submissions"].append({
            "time": r.get('submit_time', ''),
            "score": display_score
        })

        if r.get('result_text', '').startswith('✅ Accepted'):
            if not problem_stats[pid]["is_ac"]: # 首次AC
                problem_stats[pid]["is_ac"] = True
                problem_stats[pid]["ac_attempts"] = problem_stats[pid]["attempts"] # 记录首次AC时的尝试次数

    # 汇总最终统计
    for pid, stats in problem_stats.items():
        # 计算趋势：取最后 3-5 次不重复的分数变化
        trend_scores = []
        for sub in stats["submissions"]:
            if not trend_scores or sub["score"] != trend_scores[-1]:
                trend_scores.append(sub["score"])

        trend_str = " -> ".join(map(str, trend_scores[-3:])) if len(trend_scores) > 1 else ""

        # 计算钻研历时 (秒)
        duration = 0
        if stats["first_ts"] and stats["last_ts"]:
            duration = stats["last_ts"] - stats["first_ts"]

        # 构造题目详情对象
        prob_detail = {
            "pid": pid,
            "title": stats["title"],
            "attempts": stats["ac_attempts"] if stats["is_ac"] else stats["attempts"],
            "history": list(reversed(stats["submissions"])), # 最新在前
            "max_score": stats["max_score"],
            "trend": trend_str,
            "duration": duration
        }

        if stats["is_ac"]:
            summary["total_ac_problems"] += 1
            summary["ac_problems_count"][stats["difficulty_text"]] += 1
            summary["total_ac_attempts"] += stats["ac_attempts"]
            summary["ac_attempts_count"][stats["difficulty_text"]] += stats["ac_attempts"]
            summary["ac_problems_list"][stats["difficulty_text"]].append(prob_detail)
        else:
            summary["total_unsolved_problems"] += 1
            summary["unsolved_problems_count"][stats["difficulty_text"]] += 1
            summary["total_unsolved_attempts"] += stats["attempts"]
            summary["unsolved_attempts_count"][stats["difficulty_text"]] += stats["attempts"]
            summary["unsolved_problems_list"][stats["difficulty_text"]].append(prob_detail)

    return summary


def get_failed_problems(records):
    """
    分析未AC的题目，返回提交次数和最高分信息

    Args:
        records: 格式化后的记录列表

    Returns:
        list: [
            {
                "pid": "P1001",
                "title": "A+B问题",
                "difficulty": {"text": "入门", "class": "diff-1"},
                "submit_count": 7,
                "max_score": 90
            },
            ...
        ]
    """
    problem_stats = {}

    for r in records:
        pid = r.get('problem_pid')
        if not pid:
            continue

        if pid not in problem_stats:
            problem_stats[pid] = {
                "pid": pid,
                "title": r.get('problem_title', ''),
                "difficulty": r.get('difficulty', {}),
                "submit_count": 0,
                "max_score": None, # 初始化为 None 以区分“从未得分”和“得 0 分”
                "is_ac": False
            }

        problem_stats[pid]["submit_count"] += 1

        if "Accepted" in r.get('result_text', ''):
            problem_stats[pid]["is_ac"] = True

        # 使用 record 中的 score 字段更新最高分
        score = r.get('score')
        if score is not None:
            try:
                score_int = int(float(score))
                if problem_stats[pid]["max_score"] is None or score_int > problem_stats[pid]["max_score"]:
                    problem_stats[pid]["max_score"] = score_int
            except (ValueError, TypeError):
                pass

        if "AC" in r.get('result_text', ''):
            problem_stats[pid]["is_ac"] = True

    failed_problems = []
    for pid, stat in problem_stats.items():
        if not stat["is_ac"]:
            failed_problems.append({
                "pid": stat["pid"],
                "title": stat["title"],
                "difficulty": stat["difficulty"],
                "submit_count": stat["submit_count"],
                "max_score": stat["max_score"]
            })

    failed_problems.sort(key=lambda x: x["submit_count"], reverse=True)

    return failed_problems


def _fetch_single_user(args):
    """辅助函数：并行获取单个用户记录"""
    username, start_ts, end_ts, max_pages = args
    try:
        return username, fetch_user_records_in_range(username, start_ts, end_ts, max_pages), None
    except Exception as e:
        return username, None, str(e)


def fetch_multi_user_records(usernames, start_ts, end_ts, max_pages=20, max_workers=4):
    """并行获取多个用户的提交记录

    Args:
        usernames: 用户名列表
        start_ts: 起始时间戳
        end_ts: 结束时间戳
        max_pages: 最大页数
        max_workers: 最大并行数

    Returns:
        dict: {用户名: 结果}，失败的会包含 error 字段
    """
    results = {}
    tasks = [(u, start_ts, end_ts, max_pages) for u in usernames]

    with ThreadPoolExecutor(max_workers=min(max_workers, len(usernames))) as executor:
        futures = {executor.submit(_fetch_single_user, task): task[0] for task in tasks}
        for future in as_completed(futures):
            username = futures[future]
            try:
                name, result, error = future.result()
                if error:
                    results[username] = {"error": error}
                else:
                    results[username] = result
            except Exception as e:
                results[username] = {"error": str(e)}

    return results
