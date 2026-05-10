"""
模型管理器 - 统一管理所有 AI 模型的加载、卸载和取消操作

设计目标：
1. Web 服务持续运行，不会因为释放显存而退出
2. 支持取消当前正在执行的任务
3. 支持手动释放所有模型显存
"""

import threading
import gc
import torch

class ModelManager:
    """单例模式：管理所有 AI 模型的生命周期"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance
    
    def _init(self):
        self._lock = threading.Lock()
        self._cancel_event = threading.Event()
        self._summarizer_model = None  # Qwen2.5-1.5B 总结模型
        self._transcriber_model = None  # Qwen3-ASR 转录模型
        self._is_processing = False  # 是否有任务正在执行
        
    @property
    def cancel_event(self):
        """获取取消信号事件，供各模块检查"""
        return self._cancel_event
    
    def is_cancelled(self):
        """检查是否被取消"""
        return self._cancel_event.is_set()
    
    def cancel(self):
        """发送取消信号"""
        self._cancel_event.set()
        
    def reset_cancel(self):
        """重置取消信号"""
        self._cancel_event.clear()
        
    def set_processing(self, status: bool):
        """设置处理状态"""
        with self._lock:
            self._is_processing = status
            
    def is_processing(self):
        """检查是否有任务在执行"""
        with self._lock:
            return self._is_processing
    
    def register_summarizer(self, model):
        """注册总结模型引用"""
        with self._lock:
            self._summarizer_model = model
            
    def register_transcriber(self, model):
        """注册转录模型引用"""
        with self._lock:
            self._transcriber_model = model
            
    def unregister_summarizer(self):
        """取消注册总结模型"""
        with self._lock:
            self._summarizer_model = None
            
    def unregister_transcriber(self):
        """取消注册转录模型"""
        with self._lock:
            self._transcriber_model = None
    
    def release_all(self):
        """
        释放所有模型显存
        
        流程：
        1. 发送取消信号（中断正在执行的任务）
        2. 等待当前任务响应取消信号（最多 2 秒）
        3. 强制删除模型引用
        4. 清理 GPU 显存
        """
        print("\n[ModelManager] ========== 开始释放显存 ==========")
        
        # 1. 发送取消信号
        self._cancel_event.set()
        
        # 2. 等待任务响应（给正在执行的任务一点时间来响应取消）
        import time
        wait_time = 0
        while self._is_processing and wait_time < 2.0:
            time.sleep(0.1)
            wait_time += 0.1
        
        # 3. 强制删除模型引用
        with self._lock:
            if self._summarizer_model is not None:
                print("[ModelManager] 卸载 Summarizer 模型...")
                del self._summarizer_model
                self._summarizer_model = None
                
            if self._transcriber_model is not None:
                print("[ModelManager] 卸载 Transcriber 模型...")
                del self._transcriber_model
                self._transcriber_model = None
        
        # 4. 清理显存
        gc.collect()
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
        
        # 5. 重置取消信号
        self._cancel_event.clear()
        
        print("[ModelManager] ✓ 显存释放完成，Web 服务继续运行")
        return {"status": "ok", "message": "GPU memory released, server still running"}
    
    def get_status(self):
        """获取当前状态"""
        with self._lock:
            return {
                "summarizer_loaded": self._summarizer_model is not None,
                "transcriber_loaded": self._transcriber_model is not None,
                "is_processing": self._is_processing,
                "cancel_requested": self._cancel_event.is_set()
            }


# 全局单例
model_manager = ModelManager()
