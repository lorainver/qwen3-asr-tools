"""
config_loader.py - 统一配置加载工具

所有模块通过此文件读取 config.yaml，避免重复加载和路径错误。

用法：
    from config_loader import config
    
    model_path = config['models']['llm']
    batch_size = config['gpu']['batch_size']
"""

import os
import yaml
from pathlib import Path

class ConfigLoader:
    _instance = None
    _config = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_config()
        return cls._instance
    
    def _load_config(self):
        """加载配置文件，路径相对于项目根目录"""
        # 项目根目录 = 此文件所在目录
        self._base_dir = Path(__file__).parent.absolute()
        config_path = self._base_dir / "config.yaml"
        
        if not config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            self._config = yaml.safe_load(f)
            
        # 动态合并 prompts.yaml 中的预设提示词
        prompts_path = self._base_dir / "prompts.yaml"
        if 'prompts' not in self._config or self._config['prompts'] is None:
            self._config['prompts'] = {}
            
        if prompts_path.exists():
            try:
                with open(prompts_path, 'r', encoding='utf-8') as f:
                    prompts_data = yaml.safe_load(f)
                    if prompts_data and 'prompts' in prompts_data and isinstance(prompts_data['prompts'], dict):
                        self._config['prompts'].update(prompts_data['prompts'])
            except Exception as e:
                print(f"警告：加载 prompts.yaml 失败: {e}")
        
        # 将相对路径转换为绝对路径（基于项目根目录）
        self._resolve_paths()
        
    def _resolve_paths(self):
        """将所有路径配置转换为绝对路径"""
        # 模型路径
        if 'models' in self._config:
            for key, path in self._config['models'].items():
                # 跳过非字符串值（如 llm_models 字典）
                if isinstance(path, dict):
                    # 递归处理嵌套字典中的路径
                    for sub_key, sub_path in path.items():
                        if isinstance(sub_path, dict) and 'path' in sub_path:
                            model_path = sub_path['path']
                            if model_path and not os.path.isabs(model_path):
                                sub_path['path'] = str(self._base_dir / model_path)
                elif path and not os.path.isabs(path):
                    self._config['models'][key] = str(self._base_dir / path)
        
        # 文件路径
        if 'paths' in self._config:
            for key, path in self._config['paths'].items():
                if path and not os.path.isabs(path):
                    self._config['paths'][key] = str(self._base_dir / path)
        
        # TTS 模型路径
        if 'models' in self._config and 'tts' in self._config['models']:
            tts_path = self._config['models']['tts']
            if tts_path and not os.path.isabs(tts_path):
                self._config['models']['tts'] = str(self._base_dir / tts_path)
    
    def get(self, key, default=None):
        """获取配置项，支持点号分隔的路径"""
        keys = key.split('.')
        value = self._config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    def __getitem__(self, key):
        """支持字典式访问：config['models']['llm']"""
        return self._config.get(key, {})

    def __getattr__(self, key):
        """支持属性式访问：config.prompts（Jinja2 模板需要）"""
        if key.startswith('_'):
            raise AttributeError(key)
        try:
            return self._config.get(key, {})
        except Exception:
            raise AttributeError(key)
    
    @property
    def base_dir(self):
        """返回项目根目录"""
        return self._base_dir

# 全局单例
config = ConfigLoader()

if __name__ == '__main__':
    # 测试
    print("项目根目录:", config.base_dir)
    print("LLM 模型路径:", config['models']['llm'])
    print("ASR 模型路径:", config['models']['asr'])
    print("TTS 模型路径:", config['models']['tts'])
    print("服务器端口:", config['server']['port'])
    prompts = config['prompts']
    print(f"已加载的提示词数量: {len(prompts)}")
    print("所有提示词 Key 列表:", list(prompts.keys()))
