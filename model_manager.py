"""
模型管理器 - 统一管理所有 AI 模型的加载、卸载和取消操作

设计目标：
1. Web 服务持续运行，不会因为释放显存而退出
2. 支持取消当前正在执行的任务
3. 支持手动释放所有模型显存
4. 释放时直接调用各模块的 _unload_model() 确保模型真正卸载

关键设计：
- 注册的是模块实例（而非模型对象），这样释放时能调用实例的卸载方法
- 模型对象的引用由各模块自己管理，model_manager 通过实例方法间接清理
"""

import threading
import gc

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
        self._summarizer = None   # LongTextSummarizer 实例
        self._transcriber_model = None  # Qwen3ASRModel 对象（转录模型是局部变量，只能引用模型）
        self._is_processing = False
        
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
    
    def register_summarizer(self, summarizer_instance):
        """注册 Summarizer 实例（用于释放时调用 _unload_model）"""
        with self._lock:
            self._summarizer = summarizer_instance
            
    def register_transcriber(self, model):
        """注册转录模型对象引用（转录模型是局部变量）"""
        with self._lock:
            self._transcriber_model = model
            
    def unregister_summarizer(self):
        """取消注册 Summarizer"""
        with self._lock:
            self._summarizer = None
            
    def unregister_transcriber(self):
        """取消注册转录模型"""
        with self._lock:
            self._transcriber_model = None
    
    def release_all(self):
        """
        释放所有模型显存
        
        流程：
        1. 发送取消信号（中断正在执行的任务）
        2. 调用 summarizer._unload_model() 彻底卸载总结模型
        3. 清理转录模型引用
        4. 强制 GC + CUDA 缓存清理
        5. 重置取消信号
        
        关键：必须通过实例的 _unload_model() 方法卸载，
        而不是只删除 model_manager 自己的引用，
        否则模块内部仍持有模型引用，GPU 显存不会释放。
        """
        print("\n[ModelManager] ========== 开始释放显存 ==========")
        
        # 1. 发送取消信号
        self._cancel_event.set()
        
        # 2. 卸载 Summarizer 模型（通过实例方法，确保内部引用也被清除）
        with self._lock:
            summarizer = self._summarizer
            transcriber_model = self._transcriber_model
        
        if summarizer is not None:
            try:
                print("[ModelManager] 卸载 Summarizer 模型...")
                summarizer._unload_model()
                print("[ModelManager] ✓ Summarizer 已卸载")
            except Exception as e:
                print(f"[ModelManager] Summarizer 卸载失败: {e}")
        
        # 3. 清理转录模型引用（转录模型在 finally 块中自动清理）
        if transcriber_model is not None:
            try:
                print("[ModelManager] 清理 Transcriber 模型引用...")
                del transcriber_model
                self._transcriber_model = None
            except Exception as e:
                print(f"[ModelManager] Transcriber 清理失败: {e}")
        
        # 4. 强制清理 GPU 缓存（多次尝试）
        import torch
        gc.collect()
        try:
            torch.cuda.synchronize()
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats()
            gc.collect()
            torch.cuda.empty_cache()  # 再次清理
        except Exception:
            pass
        
        # 5. 重置取消信号和处理状态
        self._cancel_event.clear()
        self._is_processing = False
        
        print("[ModelManager] ✓ 显存释放完成，Web 服务继续运行")
        return {"status": "ok", "message": "GPU memory released, server still running"}
    
    def prepare_for_transcription(self):
        """
        为加载 ASR 转录模型做准备
        核心逻辑：若 LLM (Summarizer) 已载入显存，则自动执行卸载以完全释放显存给 ASR 模型。
        """
        print("\n[ModelManager] [Exclusive Lock] 检测是否需要释放 LLM 显存以准备 ASR 转录...")
        with self._lock:
            summarizer = self._summarizer
            is_processing = self._is_processing
            
        if is_processing and summarizer is not None and hasattr(summarizer, 'model') and summarizer.model is not None:
            raise RuntimeError("当前有正在运行的 LLM 任务，请稍后再试或点击取消。")
            
        if summarizer is not None:
            try:
                has_model = hasattr(summarizer, 'model') and summarizer.model is not None
                if has_model:
                    print("[ModelManager] [Exclusive Lock] 发现 LLM 已载入显存，触发自动卸载...")
                    summarizer._unload_model()
                    
                    # 强力回收
                    import gc
                    import torch
                    gc.collect()
                    torch.cuda.empty_cache()
                    print("[ModelManager] [Exclusive Lock] ✓ LLM 已被成功卸载，显存已清空。")
                else:
                    print("[ModelManager] [Exclusive Lock] 确认 LLM 未载入显存，无需释放。")
            except Exception as e:
                print(f"[ModelManager] [Exclusive Lock] 自动释放 LLM 显存失败: {e}")

    def prepare_for_llm(self):
        """
        为加载 LLM 模型做准备
        核心逻辑：若 ASR 任务处于运行中，拒绝加载以避免冲突；若 ASR 转录模型载入但未清理，自动进行清理释放。
        """
        print("\n[ModelManager] [Exclusive Lock] 检测是否需要释放 ASR 显存以准备 LLM 任务...")
        with self._lock:
            transcriber_model = self._transcriber_model
            is_processing = self._is_processing
            
        if is_processing and transcriber_model is not None:
            raise RuntimeError("当前有正在运行的语音转录任务，无法同时加载 LLM 模型。请稍候或取消转录任务。")
            
        if transcriber_model is not None:
            try:
                print("[ModelManager] [Exclusive Lock] 发现残留的 ASR 模型对象，触发自动释放清理...")
                self._transcriber_model = None
                
                # 强力回收
                import gc
                import torch
                gc.collect()
                torch.cuda.empty_cache()
                print("[ModelManager] [Exclusive Lock] ✓ ASR 残留资源已成功释放。")
            except Exception as e:
                print(f"[ModelManager] [Exclusive Lock] 自动释放 ASR 显存失败: {e}")

    def get_status(self):
        """获取当前状态"""
        with self._lock:
            summarizer_loaded = (
                self._summarizer is not None and 
                hasattr(self._summarizer, 'model') and 
                self._summarizer.model is not None
            )
            return {
                "summarizer_loaded": summarizer_loaded,
                "transcriber_loaded": self._transcriber_model is not None,
                "is_processing": self._is_processing,
                "cancel_requested": self._cancel_event.is_set()
            }


# 全局单例
model_manager = ModelManager()
