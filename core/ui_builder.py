"""
UI 構建模組
負責構建 Gradio 用戶界面
"""
import gradio as gr
from typing import List, Tuple, Optional, Callable
from diffusers_helper.gradio.progress_bar import make_progress_bar_css


class UIBuilder:
    """UI 構建器類"""

    def __init__(self, app_title: str = "FramePack", high_vram: bool = False):
        self.app_title = app_title
        self.high_vram = high_vram
        self.quick_prompts = [
            'The girl dances gracefully, with clear movements, full of charm.',
            'A character doing some simple body movements.',
        ]
        self.quick_prompts = [[x] for x in self.quick_prompts]

    def handle_magcache_change(self, magcache_value, teacache_value):
        """
        Handles the change event for the 'use_magcache' checkbox.
        Ensures that 'use_teacache' is unchecked if 'use_magcache' is checked.
        """
        if magcache_value and teacache_value:
            # If magcache was just checked AND teacache was already checked,
            # uncheck teacache.
            return gr.update(value=True), gr.update(value=False)
        # Otherwise, return current values to avoid unintended changes
        return gr.update(value=magcache_value), gr.update(value=teacache_value)

    def handle_teacache_change(self, magcache_value, teacache_value):
        """
        Handles the change event for the 'use_teacache' checkbox.
        Ensures that 'use_magcache' is unchecked if 'use_teacache' is checked.
        """
        if magcache_value and teacache_value:
            # If teacache was just checked AND magcache was already checked,
            # uncheck magcache.
            return gr.update(value=False), gr.update(value=True)
        # Otherwise, return current values to avoid unintended changes
        return gr.update(value=magcache_value), gr.update(value=teacache_value)
        
    def create_interface(self, 
                        process_fn: Callable,
                        end_process_fn: Callable,
                        file_manager,
                        enable_advanced_features: bool = False) -> gr.Blocks:
        """創建 Gradio 界面"""
        
        css = make_progress_bar_css()
        block = gr.Blocks(css=css).queue()
        
        with block:
            gr.Markdown(f'# {self.app_title}')
            
            with gr.Row():
                # 左側控制面板
                left_column = self._create_left_column(enable_advanced_features)
                
                # 右側顯示面板
                right_column = self._create_right_column(file_manager, enable_advanced_features)
            
            # 底部鏈接
            gr.HTML('<div style="text-align:center; margin-top:20px;">Share your results and find ideas at the <a href="https://x.com/search?q=framepack&f=live" target="_blank">FramePack Twitter (X) thread</a></div>')
            
            # 設置事件處理
            self._setup_event_handlers(
                left_column, right_column, process_fn, end_process_fn, 
                file_manager, enable_advanced_features
            )
        
        return block
    
    def _create_left_column(self, enable_advanced_features: bool) -> dict:
        """創建左側控制面板"""
        with gr.Column():
            # 基本輸入
            input_image = gr.Image(sources='upload', type="numpy", label="Image", height=320)
            resolution = gr.Slider(label="Resolution", minimum=240, maximum=720, value=416, step=16)
            prompt = gr.Textbox(label="Prompt", value='')
            
            # 快速提示
            example_quick_prompts = gr.Dataset(
                samples=self.quick_prompts, 
                label='Quick List', 
                samples_per_page=1000, 
                components=[prompt]
            )
            example_quick_prompts.click(
                lambda x: x[0], 
                inputs=[example_quick_prompts], 
                outputs=prompt, 
                show_progress=False, 
                queue=False
            )
            
            # 控制按鈕
            with gr.Row():
                start_button = gr.Button(value="Start Generation")
                end_button = gr.Button(value="End Generation", interactive=False)
            
            # 參數設置
            params = self._create_parameter_group(enable_advanced_features)
            
            # LoRA 設置
            lora_group = self._create_lora_group()
        
        return {
            'input_image': input_image,
            'resolution': resolution,
            'prompt': prompt,
            'start_button': start_button,
            'end_button': end_button,
            **params,
            **lora_group
        }
    
    def _create_parameter_group(self, enable_advanced_features: bool) -> dict:
        """創建參數設置組"""
        with gr.Group():
            # Cache options with mutual exclusion
            with gr.Row():
                use_magcache = gr.Checkbox(
                    label='Use MagCache',
                    value=True,
                    info='Faster speed, but often makes hands and fingers slightly worse.'
                )
                use_teacache = gr.Checkbox(
                    label='Use TeaCache',
                    value=False,
                    info='Faster speed, but often makes hands and fingers slightly worse. Only support MagCache or TeaCache'
                )

            # MagCache parameters
            magcache_thresh = gr.Slider(
                label="MagCache Threshold",
                minimum=0.0, maximum=1.0, value=0.10, step=0.005,
                info='Decrease this value when the quality is poor. It denotes the accumulated error caused by skipping steps.'
            )

            magcache_K = gr.Slider(
                label="MagCache K",
                minimum=1, maximum=5, value=3, step=1,
                info='Decrease this value when the quality is poor. 0 means forbidding magcache.'
            )

            magcache_retention_ratio = gr.Slider(
                label="MagCache Retention Ratio",
                minimum=0.0, maximum=1.0, value=0.2, step=0.01,
                info='Increase this ratio to make the video more consistent with the video generated without MagCache. Retain the first x% of steps to preserve semantic consistency.'
            )
            
            n_prompt = gr.Textbox(label="Negative Prompt", value="", visible=False)  # Not used
            seed = gr.Number(label="Seed", value=31337, precision=0)
            
            # F1 版本的默認值不同
            default_length = 120 if enable_advanced_features else 5
            total_second_length = gr.Slider(
                label="Total Video Length (Seconds)", 
                minimum=1, maximum=120, value=default_length, step=0.1
            )
            
            latent_window_size = gr.Slider(
                label="Latent Window Size", 
                minimum=1, maximum=33, value=9, step=1, 
                visible=False  # Should not change
            )
            
            steps = gr.Slider(
                label="Steps", 
                minimum=1, maximum=100, value=25, step=1, 
                info='Changing this value is not recommended.'
            )
            
            cfg = gr.Slider(
                label="CFG Scale", 
                minimum=1.0, maximum=32.0, value=1.0, step=0.01, 
                visible=False  # Should not change
            )
            
            gs = gr.Slider(
                label="Distilled CFG Scale", 
                minimum=1.0, maximum=32.0, value=10.0, step=0.01, 
                info='Changing this value is not recommended.'
            )
            
            rs = gr.Slider(
                label="CFG Re-Scale", 
                minimum=0.0, maximum=1.0, value=0.0, step=0.01, 
                visible=False  # Should not change
            )
            
            # GPU 記憶體設置
            gpu_memory_preservation = gr.Slider(
                label="GPU Inference Preserved Memory (GB) (larger means slower)", 
                minimum=6, maximum=128, value=6, step=0.1, 
                info="Set this number to a larger value if you encounter OOM. Larger value causes slower speed.", 
                visible=not self.high_vram
            )
            
            mp4_crf = gr.Slider(
                label="MP4 Compression", 
                minimum=0, maximum=100, value=16, step=1, 
                info="Lower means better quality. 0 is uncompressed. Change to 16 if you get black outputs. "
            )
        
        return {
            'use_magcache': use_magcache,
            'use_teacache': use_teacache,
            'magcache_thresh': magcache_thresh,
            'magcache_K': magcache_K,
            'magcache_retention_ratio': magcache_retention_ratio,
            'n_prompt': n_prompt,
            'seed': seed,
            'total_second_length': total_second_length,
            'latent_window_size': latent_window_size,
            'steps': steps,
            'cfg': cfg,
            'gs': gs,
            'rs': rs,
            'gpu_memory_preservation': gpu_memory_preservation,
            'mp4_crf': mp4_crf
        }
    
    def _create_lora_group(self) -> dict:
        """創建 LoRA 設置組"""
        with gr.Group():
            lora_file = gr.File(label="LoRA File", file_count="single", type="filepath")
            lora_multiplier = gr.Slider(
                label="LoRA Multiplier", 
                minimum=0.0, maximum=1.0, value=0.8, step=0.1
            )
        
        return {
            'lora_file': lora_file,
            'lora_multiplier': lora_multiplier
        }
    
    def _create_right_column(self, file_manager, enable_advanced_features: bool) -> dict:
        """創建右側顯示面板"""
        with gr.Column():
            # 預覽和結果
            preview_image = gr.Image(label="Next Latents", height=200, visible=False)
            result_video = gr.Video(
                label="Finished Frames", 
                autoplay=True, 
                show_share_button=False, 
                height=512, 
                loop=True
            )
            
            # 進度顯示
            if not enable_advanced_features:
                gr.Markdown('Note that the ending actions will be generated before the starting actions due to the inverted sampling. If the starting action is not in the video, you just need to wait, and it will be generated later.')
            
            progress_desc = gr.Markdown('', elem_classes='no-generating-animation')
            progress_bar = gr.HTML('', elem_classes='no-generating-animation')
            
            # 文件管理區域
            file_management = self._create_file_management_section(enable_advanced_features)
        
        return {
            'preview_image': preview_image,
            'result_video': result_video,
            'progress_desc': progress_desc,
            'progress_bar': progress_bar,
            **file_management
        }
    
    def _create_file_management_section(self, enable_advanced_features: bool) -> dict:
        """創建文件管理區域"""
        with gr.Group():
            gr.Markdown("### 📁 輸出視頻管理")
            
            if enable_advanced_features:
                gr.Markdown("💡 **清理功能說明**:")
                gr.Markdown("• **智能清理**: 對於每個生成任務，只保留最長的視頻文件，刪除中間生成的較短文件")
                gr.Markdown("• **全部刪除**: ⚠️ 刪除輸出文件夾中的所有文件（MP4、PNG、JPG等），操作前請仔細確認")
            
            # 按鈕行
            button_row = self._create_management_buttons(enable_advanced_features)
            
            # 文件列表顯示
            video_list_display = gr.Textbox(
                label="視頻文件列表", 
                lines=6, 
                interactive=False,
                placeholder="點擊刷新按鈕查看視頻文件..."
            )
            
            # 高級功能區域
            advanced_components = {}
            if enable_advanced_features:
                advanced_components = self._create_advanced_management_components()
            
            # 基本文件操作
            basic_components = self._create_basic_file_components()
        
        return {
            **button_row,
            'video_list_display': video_list_display,
            **advanced_components,
            **basic_components
        }
    
    def _create_management_buttons(self, enable_advanced_features: bool) -> dict:
        """創建管理按鈕"""
        with gr.Row():
            refresh_btn = gr.Button("🔄 刷新列表", size="sm")
            
            buttons = {'refresh_btn': refresh_btn}
            
            if enable_advanced_features:
                cleanup_preview_btn = gr.Button("🗂️ 清理預覽", size="sm")
                delete_all_preview_btn = gr.Button("🗑️ 全部刪除預覽", variant="stop", size="sm")
                buttons.update({
                    'cleanup_preview_btn': cleanup_preview_btn,
                    'delete_all_preview_btn': delete_all_preview_btn
                })
        
        return buttons

    def _create_advanced_management_components(self) -> dict:
        """創建高級管理組件"""
        # 清理預覽區域
        cleanup_preview_display = gr.Textbox(
            label="清理預覽",
            lines=8,
            interactive=False,
            visible=False,
            placeholder="點擊清理預覽按鈕查看將要刪除的文件..."
        )

        cleanup_execute_btn = gr.Button("🗑️ 執行清理", variant="stop", size="sm", visible=False)
        cleanup_status = gr.Textbox(label="清理狀態", visible=False, interactive=False)

        # 全部刪除區域
        delete_all_preview_display = gr.Textbox(
            label="全部刪除預覽",
            lines=10,
            interactive=False,
            visible=False,
            placeholder="點擊全部刪除預覽按鈕查看將要刪除的所有文件..."
        )

        with gr.Row():
            delete_all_execute_btn = gr.Button("⚠️ 確認刪除全部文件", variant="stop", size="sm", visible=False)
            delete_all_cancel_btn = gr.Button("❌ 取消", size="sm", visible=False)

        delete_all_status = gr.Textbox(label="刪除狀態", visible=False, interactive=False)

        return {
            'cleanup_preview_display': cleanup_preview_display,
            'cleanup_execute_btn': cleanup_execute_btn,
            'cleanup_status': cleanup_status,
            'delete_all_preview_display': delete_all_preview_display,
            'delete_all_execute_btn': delete_all_execute_btn,
            'delete_all_cancel_btn': delete_all_cancel_btn,
            'delete_all_status': delete_all_status
        }

    def _create_basic_file_components(self) -> dict:
        """創建基本文件操作組件"""
        with gr.Row():
            video_selector = gr.Dropdown(
                label="選擇視頻",
                choices=[],
                visible=False
            )

        with gr.Row():
            preview_btn = gr.Button("👁️ 預覽", size="sm", visible=False)
            download_btn = gr.Button("⬇️ 下載", size="sm", visible=False)

        preview_video = gr.Video(label="視頻預覽", visible=False, height=300)
        download_file = gr.File(label="下載", visible=False)

        return {
            'video_selector': video_selector,
            'preview_btn': preview_btn,
            'download_btn': download_btn,
            'preview_video': preview_video,
            'download_file': download_file
        }

    def _setup_event_handlers(self, left_column: dict, right_column: dict,
                             process_fn: Callable, end_process_fn: Callable,
                             file_manager, enable_advanced_features: bool):
        """設置事件處理器"""

        # 獲取所有輸入參數
        input_params = [
            left_column['input_image'], left_column['prompt'], left_column['n_prompt'],
            left_column['seed'], left_column['total_second_length'], left_column['latent_window_size'],
            left_column['steps'], left_column['cfg'], left_column['gs'], left_column['rs'],
            left_column['gpu_memory_preservation'], left_column['use_teacache'], left_column['mp4_crf'],
            left_column['resolution'], left_column['lora_file'], left_column['lora_multiplier'],
            left_column['use_magcache'], left_column['magcache_thresh'], left_column['magcache_K'],
            left_column['magcache_retention_ratio']
        ]

        # 主要處理事件
        left_column['start_button'].click(
            fn=process_fn,
            inputs=input_params,
            outputs=[
                right_column['result_video'], right_column['preview_image'],
                right_column['progress_desc'], right_column['progress_bar'],
                left_column['start_button'], left_column['end_button']
            ]
        )

        left_column['end_button'].click(fn=end_process_fn)

        # MagCache and TeaCache mutual exclusion
        left_column['use_magcache'].change(
            fn=self.handle_magcache_change,
            inputs=[left_column['use_magcache'], left_column['use_teacache']],
            outputs=[left_column['use_magcache'], left_column['use_teacache']]
        )
        left_column['use_teacache'].change(
            fn=self.handle_teacache_change,
            inputs=[left_column['use_magcache'], left_column['use_teacache']],
            outputs=[left_column['use_magcache'], left_column['use_teacache']]
        )

        # 文件管理事件
        self._setup_file_management_events(right_column, file_manager, enable_advanced_features)

    def _setup_file_management_events(self, right_column: dict, file_manager, enable_advanced_features: bool):
        """設置文件管理事件"""

        # 刷新文件列表
        right_column['refresh_btn'].click(
            fn=file_manager.get_output_videos,
            outputs=[
                right_column['video_list_display'], right_column['video_selector'],
                right_column['preview_btn'], right_column['download_btn'],
                right_column['preview_video']
            ]
        )

        # 基本文件操作
        right_column['preview_btn'].click(
            fn=lambda x: x,
            inputs=[right_column['video_selector']],
            outputs=[right_column['preview_video']]
        ).then(
            fn=lambda: gr.update(visible=True),
            outputs=[right_column['preview_video']]
        )

        right_column['download_btn'].click(
            fn=file_manager.download_selected_video,
            inputs=[right_column['video_selector']],
            outputs=[right_column['download_file'], right_column['download_file']]
        )

        # 高級功能事件
        if enable_advanced_features:
            self._setup_advanced_events(right_column, file_manager)

    def _setup_advanced_events(self, right_column: dict, file_manager):
        """設置高級功能事件"""

        # 清理預覽事件
        right_column['cleanup_preview_btn'].click(
            fn=file_manager.get_cleanup_preview,
            outputs=[right_column['cleanup_preview_display'], right_column['cleanup_execute_btn']]
        )

        # 執行清理事件
        right_column['cleanup_execute_btn'].click(
            fn=file_manager.cleanup_videos,
            outputs=[right_column['cleanup_preview_display'], right_column['cleanup_status']]
        ).then(
            fn=lambda: gr.update(visible=True),
            outputs=[right_column['cleanup_status']]
        ).then(
            fn=file_manager.get_output_videos,  # 清理後自動刷新文件列表
            outputs=[
                right_column['video_list_display'], right_column['video_selector'],
                right_column['preview_btn'], right_column['download_btn'],
                right_column['preview_video']
            ]
        )

        # 全部刪除預覽事件
        right_column['delete_all_preview_btn'].click(
            fn=file_manager.get_all_files_preview,
            outputs=[right_column['delete_all_preview_display'], right_column['delete_all_execute_btn']]
        ).then(
            fn=lambda: [gr.update(visible=True), gr.update(visible=True)],
            outputs=[right_column['delete_all_cancel_btn'], right_column['delete_all_preview_display']]
        )

        # 執行全部刪除事件
        right_column['delete_all_execute_btn'].click(
            fn=file_manager.delete_all_files,
            outputs=[right_column['delete_all_preview_display'], right_column['delete_all_status']]
        ).then(
            fn=lambda: [gr.update(visible=True), gr.update(visible=False), gr.update(visible=False)],
            outputs=[right_column['delete_all_status'], right_column['delete_all_execute_btn'], right_column['delete_all_cancel_btn']]
        ).then(
            fn=file_manager.get_output_videos,  # 刪除後自動刷新文件列表
            outputs=[
                right_column['video_list_display'], right_column['video_selector'],
                right_column['preview_btn'], right_column['download_btn'],
                right_column['preview_video']
            ]
        )

        # 取消全部刪除事件
        right_column['delete_all_cancel_btn'].click(
            fn=lambda: [gr.update(visible=False, value=""), gr.update(visible=False), gr.update(visible=False)],
            outputs=[right_column['delete_all_preview_display'], right_column['delete_all_execute_btn'], right_column['delete_all_cancel_btn']]
        )
