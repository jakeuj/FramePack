"""
視頻處理模組
負責視頻生成的核心邏輯
"""
import torch
import numpy as np
import einops
import os
import glob
from PIL import Image
from typing import Optional, Callable, Dict, Any, List, Tuple
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
from diffusers_helper.models.hunyuan_video_packed import get_cu_seqlens


# MagCache utility functions
def nearest_interp(src_array, target_length):
    """Nearest neighbor interpolation for MagCache ratios"""
    src_length = len(src_array)
    if target_length == 1:
        return np.array([src_array[-1]])

    scale = (src_length - 1) / (target_length - 1)
    mapped_indices = np.round(np.arange(target_length) * scale).astype(int)
    return src_array[mapped_indices]


def initialize_magcache(self, enable_magcache=True, num_steps=25, magcache_thresh=0.1, K=2, retention_ratio=0.2):
    """Initialize MagCache parameters"""
    self.enable_magcache = enable_magcache
    self.cnt = 0
    self.num_steps = num_steps
    self.magcache_thresh = magcache_thresh
    self.K = K
    self.retention_ratio = retention_ratio
    self.mag_ratios = np.array([1.0]+[1.25781, 1.08594, 1.02344, 1.00781, 1.02344, 1.00781, 1.02344, 1.05469, 0.99609, 1.03906, 1.00781, 1.01562, 1.00781, 1.02344, 1.01562, 0.98047, 1.05469, 0.98047, 0.96875, 1.03125, 0.97266, 0.9375, 0.96484, 0.78516])
    # Nearest interpolation when the num_steps is different from the length of mag_ratios
    if len(self.mag_ratios) != num_steps:
        interpolated_mag_ratios = nearest_interp(self.mag_ratios, num_steps)
        self.mag_ratios = interpolated_mag_ratios


def magcache_framepack_calibration(
        self,
        hidden_states, timestep, encoder_hidden_states, encoder_attention_mask, pooled_projections, guidance,
        latent_indices=None,
        clean_latents=None, clean_latent_indices=None,
        clean_latents_2x=None, clean_latent_2x_indices=None,
        clean_latents_4x=None, clean_latent_4x_indices=None,
        image_embeddings=None,
        attention_kwargs=None, return_dict=True
    ):
    """
    Calibration function for `mag_ratios`, requiring only a single prompt/input.
    Please recalibrate `mag_ratios` if the number of inference steps differs significantly from the predefined value (25),
    or if the scheduler or solver is modified.
    """
    if attention_kwargs is None:
        attention_kwargs = {}

    batch_size, num_channels, num_frames, height, width = hidden_states.shape
    p, p_t = self.config['patch_size'], self.config['patch_size_t']
    post_patch_num_frames = num_frames // p_t
    post_patch_height = height // p
    post_patch_width = width // p
    original_context_length = post_patch_num_frames * post_patch_height * post_patch_width

    hidden_states, rope_freqs = self.process_input_hidden_states(hidden_states, latent_indices, clean_latents, clean_latent_indices, clean_latents_2x, clean_latent_2x_indices, clean_latents_4x, clean_latent_4x_indices)

    temb = self.gradient_checkpointing_method(self.time_text_embed, timestep, guidance, pooled_projections)
    encoder_hidden_states = self.gradient_checkpointing_method(self.context_embedder, encoder_hidden_states, timestep, encoder_attention_mask)

    if self.image_projection is not None:
        assert image_embeddings is not None, 'You must use image embeddings!'
        extra_encoder_hidden_states = self.gradient_checkpointing_method(self.image_projection, image_embeddings)
        extra_attention_mask = torch.ones((batch_size, extra_encoder_hidden_states.shape[1]), dtype=encoder_attention_mask.dtype, device=encoder_attention_mask.device)

        # must cat before (not after) encoder_hidden_states, due to attn masking
        encoder_hidden_states = torch.cat([extra_encoder_hidden_states, encoder_hidden_states], dim=1)
        encoder_attention_mask = torch.cat([extra_attention_mask, encoder_attention_mask], dim=1)

    if batch_size == 1:
        # When batch size is 1, we do not need any masks or var-len funcs since cropping is mathematically same to what we want
        # If they are not same, then their impls are wrong. Ours are always the correct one.
        text_len = encoder_attention_mask.sum().item()
        encoder_hidden_states = encoder_hidden_states[:, :text_len]
        attention_mask = None, None, None, None
    else:
        img_seq_len = hidden_states.shape[1]
        txt_seq_len = encoder_hidden_states.shape[1]

        cu_seqlens_q = get_cu_seqlens(encoder_attention_mask, img_seq_len)
        cu_seqlens_kv = cu_seqlens_q
        max_seqlen_q = img_seq_len + txt_seq_len
        max_seqlen_kv = max_seqlen_q

        attention_mask = cu_seqlens_q, cu_seqlens_kv, max_seqlen_q, max_seqlen_kv

    if self.cnt == 0 :
        self.norm_ratio, self.norm_std, self.cos_dis = [], [], []

    ori_hidden_states = hidden_states.clone()
    for block_id, block in enumerate(self.transformer_blocks):
        hidden_states, encoder_hidden_states = self.gradient_checkpointing_method(
            block,
            hidden_states,
            encoder_hidden_states,
            temb,
            attention_mask,
            rope_freqs
        )

    for block_id, block in enumerate(self.single_transformer_blocks):
        hidden_states, encoder_hidden_states = self.gradient_checkpointing_method(
            block,
            hidden_states,
            encoder_hidden_states,
            temb,
            attention_mask,
            rope_freqs
        )
    cur_residual = hidden_states - ori_hidden_states

    if self.cnt >= 1:
        norm_ratio = ((cur_residual.norm(dim=-1)/self.previous_residual.norm(dim=-1)).mean()).item()
        norm_std = (cur_residual.norm(dim=-1)/self.previous_residual.norm(dim=-1)).std().item()
        cos_dis = (1-torch.nn.functional.cosine_similarity(cur_residual, self.previous_residual, dim=-1, eps=1e-8)).mean().item()
        self.norm_ratio.append(round(norm_ratio, 5))
        self.norm_std.append(round(norm_std, 5))
        self.cos_dis.append(round(cos_dis, 5))
        print(f"time: {self.cnt}, norm_ratio: {norm_ratio}, norm_std: {norm_std}, cos_dis: {cos_dis}")

    self.previous_residual = cur_residual
    self.cnt += 1
    if self.cnt == self.num_steps:
        print("norm ratio")
        print(self.norm_ratio)
        print("norm std")
        print(self.norm_std)
        print("cos_dis")
        print(self.cos_dis)
        self.cnt = 0
        self.norm_ratio = []
        self.norm_std = []
        self.cos_dis = []

    hidden_states = self.gradient_checkpointing_method(self.norm_out, hidden_states, temb)

    hidden_states = hidden_states[:, -original_context_length:, :]

    if self.high_quality_fp32_output_for_inference:
        hidden_states = hidden_states.to(dtype=torch.float32)
        if self.proj_out.weight.dtype != torch.float32:
            self.proj_out.to(dtype=torch.float32)

    hidden_states = self.gradient_checkpointing_method(self.proj_out, hidden_states)

    hidden_states = einops.rearrange(hidden_states, 'b (t h w) (c pt ph pw) -> b c (t pt) (h ph) (w pw)',
                                        t=post_patch_num_frames, h=post_patch_height, w=post_patch_width,
                                        pt=p_t, ph=p, pw=p)

    if return_dict:
        from diffusers.models.modeling_outputs import Transformer2DModelOutput
        return Transformer2DModelOutput(sample=hidden_states)

    return hidden_states,


def magcache_framepack_forward(
        self,
        hidden_states, timestep, encoder_hidden_states, encoder_attention_mask, pooled_projections, guidance,
        latent_indices=None,
        clean_latents=None, clean_latent_indices=None,
        clean_latents_2x=None, clean_latent_2x_indices=None,
        clean_latents_4x=None, clean_latent_4x_indices=None,
        image_embeddings=None,
        attention_kwargs=None, return_dict=True
    ):
    """MagCache optimized forward pass for FramePack"""

    if attention_kwargs is None:
        attention_kwargs = {}

    batch_size, num_channels, num_frames, height, width = hidden_states.shape
    p, p_t = self.config['patch_size'], self.config['patch_size_t']
    post_patch_num_frames = num_frames // p_t
    post_patch_height = height // p
    post_patch_width = width // p
    original_context_length = post_patch_num_frames * post_patch_height * post_patch_width

    hidden_states, rope_freqs = self.process_input_hidden_states(hidden_states, latent_indices, clean_latents, clean_latent_indices, clean_latents_2x, clean_latent_2x_indices, clean_latents_4x, clean_latent_4x_indices)

    temb = self.gradient_checkpointing_method(self.time_text_embed, timestep, guidance, pooled_projections)
    encoder_hidden_states = self.gradient_checkpointing_method(self.context_embedder, encoder_hidden_states, timestep, encoder_attention_mask)

    if self.image_projection is not None:
        assert image_embeddings is not None, 'You must use image embeddings!'
        extra_encoder_hidden_states = self.gradient_checkpointing_method(self.image_projection, image_embeddings)
        extra_attention_mask = torch.ones((batch_size, extra_encoder_hidden_states.shape[1]), dtype=encoder_attention_mask.dtype, device=encoder_attention_mask.device)

        # must cat before (not after) encoder_hidden_states, due to attn masking
        encoder_hidden_states = torch.cat([extra_encoder_hidden_states, encoder_hidden_states], dim=1)
        encoder_attention_mask = torch.cat([extra_attention_mask, encoder_attention_mask], dim=1)

    if batch_size == 1:
        # When batch size is 1, we do not need any masks or var-len funcs since cropping is mathematically same to what we want
        # If they are not same, then their impls are wrong. Ours are always the correct one.
        text_len = encoder_attention_mask.sum().item()
        encoder_hidden_states = encoder_hidden_states[:, :text_len]
        attention_mask = None, None, None, None
    else:
        img_seq_len = hidden_states.shape[1]
        txt_seq_len = encoder_hidden_states.shape[1]

        cu_seqlens_q = get_cu_seqlens(encoder_attention_mask, img_seq_len)
        cu_seqlens_kv = cu_seqlens_q
        max_seqlen_q = img_seq_len + txt_seq_len
        max_seqlen_kv = max_seqlen_q

        attention_mask = cu_seqlens_q, cu_seqlens_kv, max_seqlen_q, max_seqlen_kv

    if self.enable_magcache:
        if self.cnt == 0: # initialize MagCache
            self.accumulated_ratio = 1.0
            self.accumulated_steps = 0
            self.accumulated_err = 0

        skip_forward = False
        if self.cnt>=int(self.retention_ratio*self.num_steps) and self.cnt>=1: # keep first retention_ratio steps
            cur_mag_ratio = self.mag_ratios[self.cnt]
            self.accumulated_ratio = self.accumulated_ratio*cur_mag_ratio
            cur_skip_err = np.abs(1-self.accumulated_ratio)
            self.accumulated_err += cur_skip_err
            self.accumulated_steps += 1
            if self.accumulated_err<=self.magcache_thresh and self.accumulated_steps<=self.K and np.abs(1-cur_mag_ratio)<=0.06:
                skip_forward = True
            else:
                self.accumulated_ratio = 1.0
                self.accumulated_steps = 0
                self.accumulated_err = 0

        if skip_forward:
            hidden_states = hidden_states + self.previous_residual
        else:
            ori_hidden_states = hidden_states.clone()

            for block_id, block in enumerate(self.transformer_blocks):
                hidden_states, encoder_hidden_states = self.gradient_checkpointing_method(
                    block,
                    hidden_states,
                    encoder_hidden_states,
                    temb,
                    attention_mask,
                    rope_freqs
                )

            for block_id, block in enumerate(self.single_transformer_blocks):
                hidden_states, encoder_hidden_states = self.gradient_checkpointing_method(
                    block,
                    hidden_states,
                    encoder_hidden_states,
                    temb,
                    attention_mask,
                    rope_freqs
                )

            self.previous_residual = hidden_states - ori_hidden_states
        self.cnt += 1
        if self.cnt == self.num_steps:
            self.cnt = 0
    else:
        for block_id, block in enumerate(self.transformer_blocks):
            hidden_states, encoder_hidden_states = self.gradient_checkpointing_method(
                block,
                hidden_states,
                encoder_hidden_states,
                temb,
                attention_mask,
                rope_freqs
            )

        for block_id, block in enumerate(self.single_transformer_blocks):
            hidden_states, encoder_hidden_states = self.gradient_checkpointing_method(
                block,
                hidden_states,
                encoder_hidden_states,
                temb,
                attention_mask,
                rope_freqs
            )

    hidden_states = self.gradient_checkpointing_method(self.norm_out, hidden_states, temb)

    hidden_states = hidden_states[:, -original_context_length:, :]

    if self.high_quality_fp32_output_for_inference:
        hidden_states = hidden_states.to(dtype=torch.float32)
        if self.proj_out.weight.dtype != torch.float32:
            self.proj_out.to(dtype=torch.float32)

    hidden_states = self.gradient_checkpointing_method(self.proj_out, hidden_states)

    hidden_states = einops.rearrange(hidden_states, 'b (t h w) (c pt ph pw) -> b c (t pt) (h ph) (w pw)',
                                        t=post_patch_num_frames, h=post_patch_height, w=post_patch_width,
                                        pt=p_t, ph=p, pw=p)

    if return_dict:
        from diffusers.models.modeling_outputs import Transformer2DModelOutput
        return Transformer2DModelOutput(sample=hidden_states)

    return hidden_states,


class BaseVideoProcessor(ABC):
    """視頻處理基礎類"""
    
    def __init__(self, model_manager, output_dir: str):
        self.model_manager = model_manager
        self.output_dir = output_dir
        
    @abstractmethod
    def process_video(self, input_image, prompt, n_prompt, seed, total_second_length,
                     latent_window_size, steps, cfg, gs, rs, gpu_memory_preservation,
                     use_teacache, mp4_crf, resolution, lora_file, lora_multiplier,
                     stream, callback_fn: Optional[Callable] = None, use_magcache=False,
                     magcache_thresh=0.1, magcache_K=3, magcache_retention_ratio=0.2):
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
            try:
                preview = d['denoised']
                preview = vae_decode_fake(preview)

                preview = (preview * 255.0).detach().cpu().numpy().clip(0, 255).astype(np.uint8)
                preview = einops.rearrange(preview, 'b c t h w -> (b h) (t w) c')

                # 檢查是否需要停止
                if stream.input_queue.top() == 'end':
                    stream.output_queue.push(('end', None))
                    raise KeyboardInterrupt('User ends the task.')

                current_step = d['i'] + 1
                percentage = int(100.0 * current_step / steps)
                hint = f'Sampling {current_step}/{steps}'
                desc = f'Total generated frames: {int(max(0, total_generated_latent_frames * 4 - 3))}, Video length: {max(0, (total_generated_latent_frames * 4 - 3) / 24) :.2f} seconds (FPS-24). The video is being extended now ...'
                stream.output_queue.push(('progress', (preview, desc, make_progress_bar_html(percentage, hint))))

            except KeyboardInterrupt:
                # 確保結束信號被發送
                stream.output_queue.push(('end', None))
                raise
            except Exception as e:
                print(f"Error in sampling callback: {e}")
                # 發送錯誤信息但不中斷處理
                stream.output_queue.push(('progress', (None, f"Error: {e}", make_progress_bar_html(0, 'Error'))))

            return

        return callback
    
    def _save_video(self, history_pixels, job_id: str, total_generated_latent_frames: int, mp4_crf: int):
        """保存視頻文件並清理舊的較短視頻"""
        output_filename = os.path.join(self.output_dir, f'{job_id}_{total_generated_latent_frames}.mp4')
        save_bcthw_as_mp4(history_pixels, output_filename, fps=24, crf=mp4_crf)

        # 清理同一任務的較短視頻文件
        self._cleanup_old_videos(job_id, total_generated_latent_frames)

        return output_filename

    def _parse_video_filename(self, filename: str) -> Tuple[Optional[str], Optional[int]]:
        """解析視頻文件名，提取任務ID和幀數信息"""
        try:
            # 移除.mp4擴展名
            name_without_ext = filename.replace('.mp4', '')
            # 分割文件名，格式假設為: timestamp_jobid_framecount
            parts = name_without_ext.split('_')
            if len(parts) >= 3:
                # 最後一個數字是幀數
                frame_count = int(parts[-1])
                # 前面的部分是任務標識符
                job_id = '_'.join(parts[:-1])
                return job_id, frame_count
            return None, None
        except:
            return None, None

    def _cleanup_old_videos(self, current_job_id: str, current_frame_count: int):
        """清理同一任務的較短視頻文件"""
        try:
            # 查找輸出目錄中的所有MP4文件
            mp4_files = glob.glob(os.path.join(self.output_dir, "*.mp4"))

            files_to_delete = []
            for file_path in mp4_files:
                filename = os.path.basename(file_path)
                job_id, frame_count = self._parse_video_filename(filename)

                # 只處理同一任務且幀數較少的文件
                if (job_id == current_job_id and
                    frame_count is not None and
                    frame_count < current_frame_count):
                    files_to_delete.append((file_path, filename, frame_count))

            # 刪除較短的視頻文件
            for file_path, filename, frame_count in files_to_delete:
                try:
                    file_size = os.path.getsize(file_path) / (1024 * 1024)  # MB
                    os.remove(file_path)
                    print(f"✅ 自動清理舊視頻: {filename} ({file_size:.1f}MB, {frame_count} 幀)")
                except Exception as e:
                    print(f"⚠️ 清理舊視頻失敗: {filename} - {str(e)}")

        except Exception as e:
            print(f"⚠️ 自動清理過程中發生錯誤: {str(e)}")
            # 不拋出異常，避免影響主要的視頻生成流程


class FramePackVideoProcessor(BaseVideoProcessor):
    """FramePack 視頻處理器"""

    def process_video(self, input_image, prompt, n_prompt, seed, total_second_length,
                     latent_window_size, steps, cfg, gs, rs, gpu_memory_preservation,
                     use_teacache, mp4_crf, resolution, lora_file, lora_multiplier,
                     stream, callback_fn: Optional[Callable] = None, use_magcache=False,
                     magcache_thresh=0.1, magcache_K=3, magcache_retention_ratio=0.2):
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
                     stream, callback_fn: Optional[Callable] = None, use_magcache=False,
                     magcache_thresh=0.1, magcache_K=3, magcache_retention_ratio=0.2):
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

                # Store original forward method
                if not hasattr(self.model_manager.transformer, '_orig_forward'):
                    self.model_manager.transformer._orig_forward = self.model_manager.transformer.__class__.forward

                if use_magcache:
                    # Apply MagCache monkey patch
                    self.model_manager.transformer.__class__.forward = magcache_framepack_forward
                    self.model_manager.transformer.__class__.initialize_magcache = initialize_magcache
                    self.model_manager.transformer.initialize_magcache(
                        enable_magcache=True,
                        num_steps=steps,
                        magcache_thresh=magcache_thresh,
                        K=magcache_K,
                        retention_ratio=magcache_retention_ratio
                    )
                elif use_teacache:
                    self.model_manager.transformer.__class__.forward = self.model_manager.transformer._orig_forward
                    self.model_manager.transformer.initialize_teacache(enable_teacache=True, num_steps=steps)
                else:
                    self.model_manager.transformer.__class__.forward = self.model_manager.transformer._orig_forward
                    self.model_manager.transformer.__class__.initialize_magcache = initialize_magcache
                    self.model_manager.transformer.initialize_teacache(enable_teacache=False)
                    self.model_manager.transformer.initialize_magcache(enable_magcache=False)

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
