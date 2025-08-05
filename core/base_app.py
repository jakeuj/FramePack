"""
基礎應用類
提供應用程式的基本結構和共同功能
"""
import os
import gradio as gr
import numpy as np
from abc import ABC, abstractmethod
from typing import Optional, List
from PIL import Image

from diffusers_helper.thread_utils import AsyncStream, async_run
from .config import AppConfig
from .model_manager import ModelManager
from .file_manager import FileManager
from .ui_builder import UIBuilder
from .queue_manager import ImageProcessingQueue


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

        # 獲取 GPU ID（從環境變數或配置）
        self.gpu_id = os.environ.get('CUDA_VISIBLE_DEVICES', '0').split(',')[0]

        # 初始化隊列管理器（支援共享隊列）
        self.queue_manager = ImageProcessingQueue(gpu_id=self.gpu_id, shared_queue=True)
        self.is_processing_queue = False

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
        self.is_processing_queue = False

    def add_to_queue(self, input_image, batch_images, upload_mode, prompt, n_prompt, seed,
                     total_second_length, latent_window_size, steps, cfg, gs, rs,
                     gpu_memory_preservation, use_teacache, mp4_crf, resolution,
                     lora_file, lora_multiplier, use_magcache, magcache_thresh,
                     magcache_K, magcache_retention_ratio):
        """添加項目到處理隊列"""

        images_to_add = []

        if upload_mode == "單張上傳" and input_image is not None:
            images_to_add = [input_image]
        elif upload_mode == "批量上傳" and batch_images is not None:
            # 處理批量上傳的圖片文件
            for file_path in batch_images:
                try:
                    img = Image.open(file_path.name)
                    img_array = np.array(img)
                    images_to_add.append(img_array)
                except Exception as e:
                    print(f"Error loading image {file_path.name}: {e}")

        if not images_to_add:
            return (
                gr.update(),  # input_image
                gr.update(),  # batch_images
                "❌ 請先上傳圖片",  # queue_status
                []  # queue_list
            )

        # 添加到隊列
        self.queue_manager.add_batch_items(
            images_to_add, prompt, n_prompt, seed, total_second_length,
            latent_window_size, steps, cfg, gs, rs, gpu_memory_preservation,
            use_teacache, mp4_crf, resolution, lora_file, lora_multiplier,
            use_magcache, magcache_thresh, magcache_K, magcache_retention_ratio
        )

        # 清理上傳組件
        clear_input = gr.update(value=None)
        clear_batch = gr.update(value=None)

        # 更新隊列狀態
        status = self.queue_manager.get_queue_status()
        status_text = f"📋 隊列狀態: 等待 {status['waiting']}, 處理中 {status['processing']}, 已完成 {status['completed']}"
        queue_items = self.queue_manager.get_queue_items()

        return clear_input, clear_batch, status_text, queue_items

    def start_queue_processing(self):
        """開始處理隊列"""
        if self.is_processing_queue:
            return (
                gr.update(),  # result_video
                gr.update(),  # preview_image
                "⚠️ 隊列正在處理中...",  # progress_desc
                "",  # progress_bar
                gr.update(interactive=False),  # start_queue_button
                gr.update(interactive=True),  # end_button
                "📋 隊列處理中...",  # queue_status
                []  # queue_list
            )

        if self.queue_manager.is_empty():
            return (
                gr.update(),  # result_video
                gr.update(),  # preview_image
                "❌ 隊列為空，請先添加圖片",  # progress_desc
                "",  # progress_bar
                gr.update(interactive=True),  # start_queue_button
                gr.update(interactive=False),  # end_button
                "📋 隊列為空",  # queue_status
                []  # queue_list
            )

        self.is_processing_queue = True

        # 開始異步處理隊列
        async_run(self.process_queue)

        return (
            gr.update(),  # result_video
            gr.update(),  # preview_image
            "🚀 開始處理隊列...",  # progress_desc
            "",  # progress_bar
            gr.update(interactive=False),  # start_queue_button
            gr.update(interactive=True),  # end_button
            "📋 隊列處理中...",  # queue_status
            self.queue_manager.get_queue_items()  # queue_list
        )

    def process_queue(self):
        """處理隊列中的項目"""
        while self.is_processing_queue and not self.queue_manager.is_empty():
            # 獲取下一個項目
            item = self.queue_manager.get_next_item()
            if item is None:
                break

            try:
                # 創建新的 stream 用於這個項目
                self.stream = AsyncStream()

                # 處理項目
                self.worker(
                    item.image, item.prompt, item.n_prompt, item.seed,
                    item.total_second_length, item.latent_window_size, item.steps,
                    item.cfg, item.gs, item.rs, item.gpu_memory_preservation,
                    item.use_teacache, item.mp4_crf, item.resolution,
                    item.lora_file, item.lora_multiplier, item.use_magcache,
                    item.magcache_thresh, item.magcache_K, item.magcache_retention_ratio
                )

                # 等待處理完成
                output_filename = None
                while True:
                    flag, data = self.stream.output_queue.next()

                    if flag == 'file':
                        output_filename = data

                    if flag == 'end':
                        break

                # 標記項目完成
                if output_filename:
                    self.queue_manager.complete_item(item.id, output_filename)
                else:
                    self.queue_manager.fail_item(item.id, "No output file generated")

            except Exception as e:
                # 標記項目失敗
                self.queue_manager.fail_item(item.id, str(e))
                print(f"Error processing queue item {item.id}: {e}")

        # 隊列處理完成
        self.is_processing_queue = False

    def refresh_queue(self):
        """刷新隊列狀態"""
        status = self.queue_manager.get_queue_status()
        status_text = f"📋 隊列狀態: 等待 {status['waiting']}, 處理中 {status['processing']}, 已完成 {status['completed']}"
        queue_items = self.queue_manager.get_queue_items()
        return status_text, queue_items

    def clear_completed_items(self):
        """清理已完成的項目"""
        self.queue_manager.clear_completed()
        return self.refresh_queue()

    def clear_queue(self):
        """清空隊列"""
        if not self.is_processing_queue:
            self.queue_manager.clear_all()
        return self.refresh_queue()
    
    def create_interface(self) -> gr.Blocks:
        """創建用戶界面"""
        # 準備隊列管理函數
        queue_manager_fns = {
            'refresh_queue': self.refresh_queue,
            'clear_completed': self.clear_completed_items,
            'clear_queue': self.clear_queue
        }

        # 獲取認證設置
        auth_settings = self.config.get_auth_settings() if hasattr(self.config, 'get_auth_settings') else None

        return self.ui_builder.create_interface(
            process_fn=self.process,
            end_process_fn=self.end_process,
            file_manager=self.file_manager,
            enable_advanced_features=self.enable_advanced_features(),
            add_to_queue_fn=self.add_to_queue,
            start_queue_fn=self.start_queue_processing,
            queue_manager_fns=queue_manager_fns,
            auth_settings=auth_settings
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
