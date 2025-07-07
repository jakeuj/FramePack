"""
基礎應用類
提供應用程式的基本結構和共同功能
"""
import gradio as gr
from abc import ABC, abstractmethod
from typing import Optional

from diffusers_helper.thread_utils import AsyncStream, async_run
from .config import AppConfig
from .model_manager import ModelManager
from .file_manager import FileManager
from .ui_builder import UIBuilder


class BaseApp(ABC):
    """基礎應用類"""
    
    def __init__(self, model_path: str, app_title: str = "FramePack"):
        self.model_path = model_path
        self.app_title = app_title
        
        # 初始化組件
        self.config = AppConfig()
        self.model_manager = None
        self.file_manager = None
        self.ui_builder = None
        self.stream = AsyncStream()
        
        # 設置環境
        self.config.setup_environment()
        
    def setup_auth(self) -> 'BaseApp':
        """設置認證功能"""
        self.config.add_auth_arguments()
        return self
        
    def initialize(self):
        """初始化應用程式"""
        # 解析命令行參數
        args = self.config.parse_args()
        print(args)
        
        # 創建輸出目錄
        self.config.create_output_dir()
        
        # 初始化模型管理器
        self.model_manager = ModelManager(self.model_path)
        
        # 初始化文件管理器
        self.file_manager = FileManager(self.config.output_dir)
        
        # 初始化 UI 構建器
        self.ui_builder = UIBuilder(
            app_title=self.app_title,
            high_vram=self.model_manager.high_vram
        )
        
    @abstractmethod
    def get_video_processor(self):
        """獲取視頻處理器（抽象方法）"""
        pass
        
    @abstractmethod
    def enable_advanced_features(self) -> bool:
        """是否啟用高級功能（抽象方法）"""
        pass
    
    def worker(self, input_image, prompt, n_prompt, seed, total_second_length,
               latent_window_size, steps, cfg, gs, rs, gpu_memory_preservation,
               use_teacache, mp4_crf, resolution, lora_file, lora_multiplier,
               use_magcache, magcache_thresh, magcache_K, magcache_retention_ratio):
        """工作線程函數"""
        video_processor = self.get_video_processor()

        video_processor.process_video(
            input_image=input_image,
            prompt=prompt,
            n_prompt=n_prompt,
            seed=seed,
            total_second_length=total_second_length,
            latent_window_size=latent_window_size,
            steps=steps,
            cfg=cfg,
            gs=gs,
            rs=rs,
            gpu_memory_preservation=gpu_memory_preservation,
            use_teacache=use_teacache,
            mp4_crf=mp4_crf,
            resolution=resolution,
            lora_file=lora_file,
            lora_multiplier=lora_multiplier,
            use_magcache=use_magcache,
            magcache_thresh=magcache_thresh,
            magcache_K=magcache_K,
            magcache_retention_ratio=magcache_retention_ratio,
            stream=self.stream
        )
    
    def process(self, input_image, prompt, n_prompt, seed, total_second_length,
                latent_window_size, steps, cfg, gs, rs, gpu_memory_preservation,
                use_teacache, mp4_crf, resolution, lora_file, lora_multiplier,
                use_magcache, magcache_thresh, magcache_K, magcache_retention_ratio):
        """處理視頻生成請求"""
        assert input_image is not None, 'No input image!'

        yield None, None, '', '', gr.update(interactive=False), gr.update(interactive=True)

        self.stream = AsyncStream()

        async_run(
            self.worker, input_image, prompt, n_prompt, seed, total_second_length,
            latent_window_size, steps, cfg, gs, rs, gpu_memory_preservation,
            use_teacache, mp4_crf, resolution, lora_file, lora_multiplier,
            use_magcache, magcache_thresh, magcache_K, magcache_retention_ratio
        )
        
        output_filename = None
        
        while True:
            flag, data = self.stream.output_queue.next()
            
            if flag == 'file':
                output_filename = data
                yield output_filename, gr.update(), gr.update(), gr.update(), gr.update(interactive=False), gr.update(interactive=True)
            
            if flag == 'progress':
                preview, desc, html = data
                yield gr.update(), gr.update(visible=True, value=preview), desc, html, gr.update(interactive=False), gr.update(interactive=True)
            
            if flag == 'end':
                yield output_filename, gr.update(visible=False), gr.update(), '', gr.update(interactive=True), gr.update(interactive=False)
                break
    
    def end_process(self):
        """結束處理"""
        self.stream.input_queue.push('end')
    
    def create_interface(self) -> gr.Blocks:
        """創建用戶界面"""
        return self.ui_builder.create_interface(
            process_fn=self.process,
            end_process_fn=self.end_process,
            file_manager=self.file_manager,
            enable_advanced_features=self.enable_advanced_features()
        )
    
    def launch(self):
        """啟動應用程式"""
        # 初始化
        self.initialize()
        
        # 創建界面
        interface = self.create_interface()
        
        # 獲取認證設置
        auth_settings = self.config.get_auth_settings() if hasattr(self.config, 'get_auth_settings') else None
        
        # 啟動應用
        launch_kwargs = {
            'server_name': self.config.server_name,
            'server_port': self.config.server_port,
            'share': self.config.share,
            'inbrowser': self.config.inbrowser,
            'allowed_paths': [self.config.output_dir],
        }
        
        if auth_settings:
            launch_kwargs['auth'] = auth_settings
            
        interface.launch(**launch_kwargs)
