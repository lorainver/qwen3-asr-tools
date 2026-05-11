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
        
        # 将相对路径转换为绝对路径（基于项目根目录）
        self._resolve_paths()
        
    def _resolve_paths(self):
        """将所有路径配置转换为绝对路径"""
        # 模型路径
        if 'models' in self._config:
            for key, path in self._config['models'].items():
                if path and not os.path.isabs(path):
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
