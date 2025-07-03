"""
視頻處理模組
負責視頻生成的核心邏輯
"""
import torch
import numpy as np
import einops
import os
from PIL import Image
from typing import Optional, Callable, Dict, Any
from abc import ABC, abstractmethod

from diffusers_helper.hunyuan import encode_prompt_conds, vae_decode, vae_encode, vae_decode_fake
from diffusers_helper.utils import (
    save_bcthw_as_mp4, crop_or_pad_yield_mask, soft_append_bcthw, 
    resize_and_center_crop, generate_timestamp
)
from diffusers_helper.pipelines.k_diffusion_hunyuan import sample_hunyuan
from diffusers_helper.memory import (
    gpu, unload_complete_models, load_model_as_complete, 
    move_model_to_device_with_memory_preservation, 
    offload_model_from_device_for_memory_preservation, fake_diffusers_current_device
)
from diffusers_helper.clip_vision import hf_clip_vision_encode
from diffusers_helper.bucket_tools import find_nearest_bucket
from diffusers_helper.gradio.progress_bar import make_progress_bar_html


class BaseVideoProcessor(ABC):
    """視頻處理基礎類"""
    
    def __init__(self, model_manager, output_dir: str):
        self.model_manager = model_manager
        self.output_dir = output_dir
        
    @abstractmethod
    def process_video(self, input_image, prompt, n_prompt, seed, total_second_length, 
                     latent_window_size, steps, cfg, gs, rs, gpu_memory_preservation, 
                     use_teacache, mp4_crf, resolution, lora_file, lora_multiplier, 
                     stream, callback_fn: Optional[Callable] = None):
        """處理視頻生成的抽象方法"""
        pass
    
    def _encode_text(self, prompt: str, n_prompt: str, cfg: float, stream):
        """編碼文本提示"""
        stream.output_queue.push(('progress', (None, '', make_progress_bar_html(0, 'Text encoding ...'))))
        
        models = self.model_manager.get_models()
        
        if not self.model_manager.high_vram:
            fake_diffusers_current_device(models['text_encoder'], gpu)
            load_model_as_complete(models['text_encoder_2'], target_device=gpu)
        
        llama_vec, clip_l_pooler = encode_prompt_conds(
            prompt, models['text_encoder'], models['text_encoder_2'], 
            models['tokenizer'], models['tokenizer_2']
        )
        
        if cfg == 1:
            llama_vec_n, clip_l_pooler_n = torch.zeros_like(llama_vec), torch.zeros_like(clip_l_pooler)
        else:
            llama_vec_n, clip_l_pooler_n = encode_prompt_conds(
                n_prompt, models['text_encoder'], models['text_encoder_2'], 
                models['tokenizer'], models['tokenizer_2']
            )
        
        llama_vec, llama_attention_mask = crop_or_pad_yield_mask(llama_vec, length=512)
        llama_vec_n, llama_attention_mask_n = crop_or_pad_yield_mask(llama_vec_n, length=512)
        
        return {
            'llama_vec': llama_vec,
            'llama_vec_n': llama_vec_n,
            'clip_l_pooler': clip_l_pooler,
            'clip_l_pooler_n': clip_l_pooler_n,
            'llama_attention_mask': llama_attention_mask,
            'llama_attention_mask_n': llama_attention_mask_n
        }
    
    def _process_image(self, input_image, resolution: int, job_id: str, stream):
        """處理輸入圖像"""
        stream.output_queue.push(('progress', (None, '', make_progress_bar_html(0, 'Image processing ...'))))
        
        H, W, C = input_image.shape
        height, width = find_nearest_bucket(H, W, resolution=resolution)
        input_image_np = resize_and_center_crop(input_image, target_width=width, target_height=height)
        
        Image.fromarray(input_image_np).save(os.path.join(self.output_dir, f'{job_id}.png'))
        
        input_image_pt = torch.from_numpy(input_image_np).float() / 127.5 - 1
        input_image_pt = input_image_pt.permute(2, 0, 1)[None, :, None]
        
        return input_image_pt, input_image_np, height, width
    
    def _encode_vae(self, input_image_pt, stream):
        """VAE 編碼"""
        stream.output_queue.push(('progress', (None, '', make_progress_bar_html(0, 'VAE encoding ...'))))
        
        models = self.model_manager.get_models()
        
        if not self.model_manager.high_vram:
            load_model_as_complete(models['vae'], target_device=gpu)
        
        start_latent = vae_encode(input_image_pt, models['vae'])
        return start_latent
    
    def _encode_clip_vision(self, input_image_np, stream):
        """CLIP Vision 編碼"""
        stream.output_queue.push(('progress', (None, '', make_progress_bar_html(0, 'CLIP Vision encoding ...'))))
        
        models = self.model_manager.get_models()
        
        if not self.model_manager.high_vram:
            load_model_as_complete(models['image_encoder'], target_device=gpu)
        
        image_encoder_output = hf_clip_vision_encode(
            input_image_np, models['feature_extractor'], models['image_encoder']
        )
        return image_encoder_output.last_hidden_state
    
    def _prepare_embeddings(self, text_embeddings: Dict, image_encoder_last_hidden_state):
        """準備嵌入向量"""
        # 轉換數據類型
        llama_vec = text_embeddings['llama_vec'].to(self.model_manager.transformer_dtype)
        llama_vec_n = text_embeddings['llama_vec_n'].to(self.model_manager.transformer_dtype)
        clip_l_pooler = text_embeddings['clip_l_pooler'].to(self.model_manager.transformer_dtype)
        clip_l_pooler_n = text_embeddings['clip_l_pooler_n'].to(self.model_manager.transformer_dtype)
        image_encoder_last_hidden_state = image_encoder_last_hidden_state.to(self.model_manager.transformer_dtype)
        
        return {
            'llama_vec': llama_vec,
            'llama_vec_n': llama_vec_n,
            'clip_l_pooler': clip_l_pooler,
            'clip_l_pooler_n': clip_l_pooler_n,
            'llama_attention_mask': text_embeddings['llama_attention_mask'],
            'llama_attention_mask_n': text_embeddings['llama_attention_mask_n'],
            'image_encoder_last_hidden_state': image_encoder_last_hidden_state
        }
    
    def _load_transformer(self, lora_file: Optional[str], lora_multiplier: float, stream):
        """載入 transformer 模型"""
        model_changed = self.model_manager.load_transformer(lora_file, lora_multiplier)
        
        if model_changed:
            stream.output_queue.push(('progress', (None, '', make_progress_bar_html(0, 'Loading transformer ...'))))
        
        return model_changed
    
    def _create_sampling_callback(self, stream, steps: int, total_generated_latent_frames: int):
        """創建採樣回調函數"""
        def callback(d):
            preview = d['denoised']
            preview = vae_decode_fake(preview)
            
            preview = (preview * 255.0).detach().cpu().numpy().clip(0, 255).astype(np.uint8)
            preview = einops.rearrange(preview, 'b c t h w -> (b h) (t w) c')
            
            if stream.input_queue.top() == 'end':
                stream.output_queue.push(('end', None))
                raise KeyboardInterrupt('User ends the task.')
            
            current_step = d['i'] + 1
            percentage = int(100.0 * current_step / steps)
            hint = f'Sampling {current_step}/{steps}'
            desc = f'Total generated frames: {int(max(0, total_generated_latent_frames * 4 - 3))}, Video length: {max(0, (total_generated_latent_frames * 4 - 3) / 24) :.2f} seconds (FPS-24). The video is being extended now ...'
            stream.output_queue.push(('progress', (preview, desc, make_progress_bar_html(percentage, hint))))
            return
        
        return callback
    
    def _save_video(self, history_pixels, job_id: str, total_generated_latent_frames: int, mp4_crf: int):
        """保存視頻文件"""
        output_filename = os.path.join(self.output_dir, f'{job_id}_{total_generated_latent_frames}.mp4')
        save_bcthw_as_mp4(history_pixels, output_filename, fps=24, crf=mp4_crf)
        return output_filename


class FramePackVideoProcessor(BaseVideoProcessor):
    """FramePack 視頻處理器"""

    def process_video(self, input_image, prompt, n_prompt, seed, total_second_length,
                     latent_window_size, steps, cfg, gs, rs, gpu_memory_preservation,
                     use_teacache, mp4_crf, resolution, lora_file, lora_multiplier,
                     stream, callback_fn: Optional[Callable] = None):
        """處理 FramePack 視頻生成"""

        total_latent_sections = (total_second_length * 24) / (latent_window_size * 4)
        total_latent_sections = int(max(round(total_latent_sections), 1))

        job_id = generate_timestamp()
        stream.output_queue.push(('progress', (None, '', make_progress_bar_html(0, 'Starting ...'))))

        try:
            # 清理 GPU
            if not self.model_manager.high_vram:
                models = self.model_manager.get_models()
                unload_complete_models(
                    models['text_encoder'], models['text_encoder_2'],
                    models['image_encoder'], models['vae'], models['transformer']
                )

            # 文本編碼
            text_embeddings = self._encode_text(prompt, n_prompt, cfg, stream)

            # 圖像處理
            input_image_pt, input_image_np, height, width = self._process_image(
                input_image, resolution, job_id, stream
            )

            # VAE 編碼
            start_latent = self._encode_vae(input_image_pt, stream)

            # CLIP Vision 編碼
            image_encoder_last_hidden_state = self._encode_clip_vision(input_image_np, stream)

            # 準備嵌入向量
            embeddings = self._prepare_embeddings(text_embeddings, image_encoder_last_hidden_state)

            # 載入 transformer
            self._load_transformer(lora_file, lora_multiplier, stream)

            # 開始採樣
            stream.output_queue.push(('progress', (None, '', make_progress_bar_html(0, 'Start sampling ...'))))

            rnd = torch.Generator("cpu").manual_seed(seed)
            num_frames = latent_window_size * 4 - 3

            history_latents = torch.zeros(
                size=(1, 16, 1 + 2 + 16, height // 8, width // 8),
                dtype=torch.float32
            ).cpu()
            history_pixels = None
            total_generated_latent_frames = 0

            latent_paddings = reversed(range(total_latent_sections))

            if total_latent_sections > 4:
                latent_paddings = [3] + [2] * (total_latent_sections - 3) + [1, 0]

            for latent_padding in latent_paddings:
                is_last_section = latent_padding == 0
                latent_padding_size = latent_padding * latent_window_size

                if stream.input_queue.top() == 'end':
                    stream.output_queue.push(('end', None))
                    return

                print(f'latent_padding_size = {latent_padding_size}, is_last_section = {is_last_section}')

                # 準備索引和潛在變量
                indices = torch.arange(0, sum([1, latent_padding_size, latent_window_size, 1, 2, 16])).unsqueeze(0)
                clean_latent_indices_pre, blank_indices, latent_indices, clean_latent_indices_post, clean_latent_2x_indices, clean_latent_4x_indices = indices.split([1, latent_padding_size, latent_window_size, 1, 2, 16], dim=1)
                clean_latent_indices = torch.cat([clean_latent_indices_pre, clean_latent_indices_post], dim=1)

                clean_latents_pre = start_latent.to(history_latents)
                clean_latents_post, clean_latents_2x, clean_latents_4x = history_latents[:, :, :1 + 2 + 16, :, :].split([1, 2, 16], dim=2)
                clean_latents = torch.cat([clean_latents_pre, clean_latents_post], dim=2)

                # 準備模型
                if not self.model_manager.high_vram:
                    unload_complete_models()
                    move_model_to_device_with_memory_preservation(
                        self.model_manager.transformer, target_device=gpu,
                        preserved_memory_gb=gpu_memory_preservation
                    )

                if use_teacache:
                    self.model_manager.transformer.initialize_teacache(enable_teacache=True, num_steps=steps)
                else:
                    self.model_manager.transformer.initialize_teacache(enable_teacache=False)

                # 創建回調函數
                callback = self._create_sampling_callback(stream, steps, total_generated_latent_frames)

                # 執行採樣
                generated_latents = sample_hunyuan(
                    transformer=self.model_manager.transformer,
                    sampler='unipc',
                    width=width,
                    height=height,
                    frames=num_frames,
                    real_guidance_scale=cfg,
                    distilled_guidance_scale=gs,
                    guidance_rescale=rs,
                    num_inference_steps=steps,
                    generator=rnd,
                    prompt_embeds=embeddings['llama_vec'],
                    prompt_embeds_mask=embeddings['llama_attention_mask'],
                    prompt_poolers=embeddings['clip_l_pooler'],
                    negative_prompt_embeds=embeddings['llama_vec_n'],
                    negative_prompt_embeds_mask=embeddings['llama_attention_mask_n'],
                    negative_prompt_poolers=embeddings['clip_l_pooler_n'],
                    device=gpu,
                    dtype=self.model_manager.transformer.dtype,
                    image_embeddings=embeddings['image_encoder_last_hidden_state'],
                    latent_indices=latent_indices,
                    clean_latents=clean_latents,
                    clean_latent_indices=clean_latent_indices,
                    clean_latents_2x=clean_latents_2x,
                    clean_latent_2x_indices=clean_latent_2x_indices,
                    clean_latents_4x=clean_latents_4x,
                    clean_latent_4x_indices=clean_latent_4x_indices,
                    callback=callback,
                )

                if is_last_section:
                    generated_latents = torch.cat([start_latent.to(generated_latents), generated_latents], dim=2)

                total_generated_latent_frames += int(generated_latents.shape[2])
                history_latents = torch.cat([generated_latents.to(history_latents), history_latents], dim=2)

                # VAE 解碼
                if not self.model_manager.high_vram:
                    offload_model_from_device_for_memory_preservation(
                        self.model_manager.transformer, target_device=gpu, preserved_memory_gb=8
                    )
                    load_model_as_complete(self.model_manager.get_models()['vae'], target_device=gpu)

                real_history_latents = history_latents[:, :, :total_generated_latent_frames, :, :]

                if history_pixels is None:
                    history_pixels = vae_decode(real_history_latents, self.model_manager.get_models()['vae']).cpu()
                else:
                    section_latent_frames = (latent_window_size * 2 + 1) if is_last_section else (latent_window_size * 2)
                    overlapped_frames = latent_window_size * 4 - 3

                    current_pixels = vae_decode(
                        real_history_latents[:, :, :section_latent_frames],
                        self.model_manager.get_models()['vae']
                    ).cpu()
                    history_pixels = soft_append_bcthw(current_pixels, history_pixels, overlapped_frames)

                if not self.model_manager.high_vram:
                    unload_complete_models()

                # 保存視頻
                output_filename = self._save_video(history_pixels, job_id, total_generated_latent_frames, mp4_crf)

                print(f'Decoded. Current latent shape {real_history_latents.shape}; pixel shape {history_pixels.shape}')

                stream.output_queue.push(('file', output_filename))

                if is_last_section:
                    break

        except Exception as e:
            import traceback
            traceback.print_exc()

            if not self.model_manager.high_vram:
                models = self.model_manager.get_models()
                unload_complete_models(
                    models['text_encoder'], models['text_encoder_2'],
                    models['image_encoder'], models['vae'], models['transformer']
                )

        stream.output_queue.push(('end', None))
        return


class FramePackF1VideoProcessor(BaseVideoProcessor):
    """FramePack F1 視頻處理器"""

    def process_video(self, input_image, prompt, n_prompt, seed, total_second_length,
                     latent_window_size, steps, cfg, gs, rs, gpu_memory_preservation,
                     use_teacache, mp4_crf, resolution, lora_file, lora_multiplier,
                     stream, callback_fn: Optional[Callable] = None):
        """處理 FramePack F1 視頻生成"""

        total_latent_sections = (total_second_length * 24) / (latent_window_size * 4)
        total_latent_sections = int(max(round(total_latent_sections), 1))

        job_id = generate_timestamp()
        stream.output_queue.push(('progress', (None, '', make_progress_bar_html(0, 'Starting ...'))))

        try:
            # 清理 GPU
            if not self.model_manager.high_vram:
                models = self.model_manager.get_models()
                unload_complete_models(
                    models['text_encoder'], models['text_encoder_2'],
                    models['image_encoder'], models['vae'], models['transformer']
                )

            # 文本編碼
            text_embeddings = self._encode_text(prompt, n_prompt, cfg, stream)

            # 圖像處理
            input_image_pt, input_image_np, height, width = self._process_image(
                input_image, resolution, job_id, stream
            )

            # VAE 編碼
            start_latent = self._encode_vae(input_image_pt, stream)

            # CLIP Vision 編碼
            image_encoder_last_hidden_state = self._encode_clip_vision(input_image_np, stream)

            # 準備嵌入向量
            embeddings = self._prepare_embeddings(text_embeddings, image_encoder_last_hidden_state)

            # 載入 transformer
            self._load_transformer(lora_file, lora_multiplier, stream)

            # 開始採樣
            stream.output_queue.push(('progress', (None, '', make_progress_bar_html(0, 'Start sampling ...'))))

            rnd = torch.Generator("cpu").manual_seed(seed)

            history_latents = torch.zeros(
                size=(1, 16, 16 + 2 + 1, height // 8, width // 8),
                dtype=torch.float32
            ).cpu()
            history_pixels = None

            history_latents = torch.cat([history_latents, start_latent.to(history_latents)], dim=2)
            total_generated_latent_frames = 1

            for section_index in range(total_latent_sections):
                if stream.input_queue.top() == 'end':
                    stream.output_queue.push(('end', None))
                    return

                print(f'section_index = {section_index}, total_latent_sections = {total_latent_sections}')

                # 準備模型
                if not self.model_manager.high_vram:
                    unload_complete_models()
                    move_model_to_device_with_memory_preservation(
                        self.model_manager.transformer, target_device=gpu,
                        preserved_memory_gb=gpu_memory_preservation
                    )

                if use_teacache:
                    self.model_manager.transformer.initialize_teacache(enable_teacache=True, num_steps=steps)
                else:
                    self.model_manager.transformer.initialize_teacache(enable_teacache=False)

                # 創建回調函數
                callback = self._create_sampling_callback(stream, steps, total_generated_latent_frames)

                # 準備索引和潛在變量
                indices = torch.arange(0, sum([1, 16, 2, 1, latent_window_size])).unsqueeze(0)
                clean_latent_indices_start, clean_latent_4x_indices, clean_latent_2x_indices, clean_latent_1x_indices, latent_indices = indices.split([1, 16, 2, 1, latent_window_size], dim=1)
                clean_latent_indices = torch.cat([clean_latent_indices_start, clean_latent_1x_indices], dim=1)

                clean_latents_4x, clean_latents_2x, clean_latents_1x = history_latents[:, :, -sum([16, 2, 1]):, :, :].split([16, 2, 1], dim=2)
                clean_latents = torch.cat([start_latent.to(history_latents), clean_latents_1x], dim=2)

                # 執行採樣
                generated_latents = sample_hunyuan(
                    transformer=self.model_manager.transformer,
                    sampler='unipc',
                    width=width,
                    height=height,
                    frames=latent_window_size * 4 - 3,
                    real_guidance_scale=cfg,
                    distilled_guidance_scale=gs,
                    guidance_rescale=rs,
                    num_inference_steps=steps,
                    generator=rnd,
                    prompt_embeds=embeddings['llama_vec'],
                    prompt_embeds_mask=embeddings['llama_attention_mask'],
                    prompt_poolers=embeddings['clip_l_pooler'],
                    negative_prompt_embeds=embeddings['llama_vec_n'],
                    negative_prompt_embeds_mask=embeddings['llama_attention_mask_n'],
                    negative_prompt_poolers=embeddings['clip_l_pooler_n'],
                    device=gpu,
                    dtype=self.model_manager.transformer.dtype,
                    image_embeddings=embeddings['image_encoder_last_hidden_state'],
                    latent_indices=latent_indices,
                    clean_latents=clean_latents,
                    clean_latent_indices=clean_latent_indices,
                    clean_latents_2x=clean_latents_2x,
                    clean_latent_2x_indices=clean_latent_2x_indices,
                    clean_latents_4x=clean_latents_4x,
                    clean_latent_4x_indices=clean_latent_4x_indices,
                    callback=callback,
                )

                total_generated_latent_frames += int(generated_latents.shape[2])
                history_latents = torch.cat([history_latents, generated_latents.to(history_latents)], dim=2)

                # VAE 解碼
                if not self.model_manager.high_vram:
                    offload_model_from_device_for_memory_preservation(
                        self.model_manager.transformer, target_device=gpu, preserved_memory_gb=8
                    )
                    load_model_as_complete(self.model_manager.get_models()['vae'], target_device=gpu)

                real_history_latents = history_latents[:, :, -total_generated_latent_frames:, :, :]

                if history_pixels is None:
                    history_pixels = vae_decode(real_history_latents, self.model_manager.get_models()['vae']).cpu()
                else:
                    section_latent_frames = latent_window_size * 2
                    overlapped_frames = latent_window_size * 4 - 3

                    current_pixels = vae_decode(
                        real_history_latents[:, :, -section_latent_frames:],
                        self.model_manager.get_models()['vae']
                    ).cpu()
                    history_pixels = soft_append_bcthw(history_pixels, current_pixels, overlapped_frames)

                if not self.model_manager.high_vram:
                    unload_complete_models()

                # 保存視頻
                output_filename = self._save_video(history_pixels, job_id, total_generated_latent_frames, mp4_crf)

                print(f'Decoded. Current latent shape {real_history_latents.shape}; pixel shape {history_pixels.shape}')

                stream.output_queue.push(('file', output_filename))

        except Exception as e:
            import traceback
            traceback.print_exc()

            if not self.model_manager.high_vram:
                models = self.model_manager.get_models()
                unload_complete_models(
                    models['text_encoder'], models['text_encoder_2'],
                    models['image_encoder'], models['vae'], models['transformer']
                )

        stream.output_queue.push(('end', None))
        return
