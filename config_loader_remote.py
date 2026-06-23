# config_loader.py
import os
import json
import csv

# 获取当前模块文件所在的目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 从配置文件加载配置
def load_config():
    config_path = os.path.join(BASE_DIR, "config.json")
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config
    else:
        raise FileNotFoundError(f"找不到配置文件 {config_path}")

# 加载巴蜀用户名-姓名映射
def load_bashu_username_map():
    mapping = {}
    path = os.path.join(BASE_DIR, "bashu_username_list.csv")
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for i, row in enumerate(reader):
                    username = row.get('username')
                    realname = row.get('realname', '') # 即使 realname 为空也获取
                    group = row.get('group', '')
                    nickname_csv = row.get('neikname', '') # 注意这里的拼写 'neikname'

                    if username: # 只要 username 存在就添加到 mapping
                        mapping[username.strip()] = {
                            'name': realname.strip(),
                            'group': group.strip(),
                            'nickname_csv': nickname_csv.strip() # 保存来自 CSV 的昵称
                        }
                        # DEBUG: 打印前5个有效映射
                        # if i < 5:
                        #    print(f"DEBUG: CSV Map[{username.strip()}]: name='{realname.strip()}', group='{group.strip()}', nickname_csv='{nickname_csv.strip()}'")

            # print(f"DEBUG: load_bashu_username_map loaded {len(mapping)} entries from {path}.")
            # print("DEBUG: First 10 entries of BASHU_USERNAME_MAP:")
            # for i, (k, v) in enumerate(mapping.items()):
            #     if i >= 10: break
            #     print(f"  {repr(k)}: {v}")
        except Exception as e:
            print(f"ERROR: 读取巴蜀用户名映射文件失败: {e}")
    else:
        print(f"WARNING: 巴蜀用户名映射文件 '{path}' 不存在。")
    return mapping

# 加载配置
CONFIG = load_config()
COOKIES = CONFIG.get("cookies", {})
RANKING_NAMES = CONFIG.get("rankings", {})
AI_CONFIG = CONFIG.get("ai_config", {})
BASHU_USERNAME_MAP = load_bashu_username_map() # 确保在所有其他模块之前加载
