"""
模型管理模組
負責模型的載入、初始化和管理
"""
import torch
import gc
import time
from typing import Optional
from diffusers import AutoencoderKLHunyuanVideo
from transformers import LlamaModel, CLIPTextModel, LlamaTokenizerFast, CLIPTokenizer, SiglipImageProcessor, SiglipVisionModel
from diffusers_helper.models.hunyuan_video_packed import HunyuanVideoTransformer3DModelPacked
from diffusers_helper.memory import gpu, get_cuda_free_memory_gb, DynamicSwapInstaller
from utils.lora_utils import merge_lora_to_state_dict


class ModelManager:
    """模型管理類"""
    
    def __init__(self, model_path: str):
        self.model_path = model_path
        self.high_vram = self._check_vram()
        
        # 模型實例
        self.text_encoder = None
        self.text_encoder_2 = None
        self.tokenizer = None
        self.tokenizer_2 = None
        self.vae = None
        self.feature_extractor = None
        self.image_encoder = None
        self.transformer = None
        
        # 模型狀態
        self.transformer_dtype = torch.bfloat16
        self.previous_lora_file = None
        self.previous_lora_multiplier = None
        
        self._initialize_models()
        
    def _check_vram(self) -> bool:
        """檢查 VRAM 大小"""
        if torch.cuda.is_available():
            free_mem_gb = get_cuda_free_memory_gb(gpu)
        elif torch.backends.mps.is_available():
            # 對於 MPS (Apple Silicon)，使用推薦的最大記憶體
            try:
                free_mem_gb = torch.mps.recommended_max_memory() / 1024 / 1024 / 1024
            except:
                # 如果無法獲取 MPS 記憶體信息，假設有足夠的記憶體
                free_mem_gb = 100.0
        else:
            # CPU 模式，假設有足夠的記憶體
            free_mem_gb = 100.0

        high_vram = free_mem_gb > 60
        print(f'Free VRAM {free_mem_gb} GB')
        print(f'High-VRAM Mode: {high_vram}')
        return high_vram
        
    def _initialize_models(self):
        """初始化所有模型"""
        print("正在初始化模型...")
        
        # 載入文本編碼器
        self.text_encoder = LlamaModel.from_pretrained(
            "hunyuanvideo-community/HunyuanVideo", 
            subfolder='text_encoder', 
            torch_dtype=torch.float16
        ).cpu()
        
        self.text_encoder_2 = CLIPTextModel.from_pretrained(
            "hunyuanvideo-community/HunyuanVideo", 
            subfolder='text_encoder_2', 
            torch_dtype=torch.float16
        ).cpu()
        
        # 載入分詞器
        self.tokenizer = LlamaTokenizerFast.from_pretrained(
            "hunyuanvideo-community/HunyuanVideo", 
            subfolder='tokenizer'
        )
        
        self.tokenizer_2 = CLIPTokenizer.from_pretrained(
            "hunyuanvideo-community/HunyuanVideo", 
            subfolder='tokenizer_2'
        )
        
        # 載入 VAE
        self.vae = AutoencoderKLHunyuanVideo.from_pretrained(
            "hunyuanvideo-community/HunyuanVideo", 
            subfolder='vae', 
            torch_dtype=torch.float16
        ).cpu()
        
        # 載入圖像編碼器
        self.feature_extractor = SiglipImageProcessor.from_pretrained(
            "lllyasviel/flux_redux_bfl", 
            subfolder='feature_extractor'
        )
        
        self.image_encoder = SiglipVisionModel.from_pretrained(
            "lllyasviel/flux_redux_bfl", 
            subfolder='image_encoder', 
            torch_dtype=torch.float16
        ).cpu()
        
        self._setup_models()
        
    def _setup_models(self):
        """設置模型參數"""
        # 設置為評估模式
        self.vae.eval()
        self.text_encoder.eval()
        self.text_encoder_2.eval()
        self.image_encoder.eval()
        
        # 低 VRAM 優化
        if not self.high_vram:
            self.vae.enable_slicing()
            self.vae.enable_tiling()
            
        # 設置數據類型
        self.vae.to(dtype=torch.float16)
        self.image_encoder.to(dtype=torch.float16)
        self.text_encoder.to(dtype=torch.float16)
        self.text_encoder_2.to(dtype=torch.float16)
        
        # 禁用梯度計算
        self.vae.requires_grad_(False)
        self.text_encoder.requires_grad_(False)
        self.text_encoder_2.requires_grad_(False)
        self.image_encoder.requires_grad_(False)
        
        # 設置設備
        if not self.high_vram:
            DynamicSwapInstaller.install_model(self.text_encoder, device=gpu)
        else:
            self.text_encoder.to(gpu)
            self.text_encoder_2.to(gpu)
            self.image_encoder.to(gpu)
            self.vae.to(gpu)
            
    def load_transformer(self, lora_file: Optional[str] = None, lora_multiplier: float = 0.8) -> bool:
        """載入 transformer 模型"""
        model_changed = self.transformer is None or (
            lora_file != self.previous_lora_file
            or lora_multiplier != self.previous_lora_multiplier
        )
        
        if not model_changed:
            return False
            
        # 清理舊模型
        self.transformer = None
        time.sleep(1.0)
        torch.cuda.empty_cache()
        gc.collect()
        
        # 更新狀態
        self.previous_lora_file = lora_file
        self.previous_lora_multiplier = lora_multiplier
        
        # 載入新模型
        self.transformer = HunyuanVideoTransformer3DModelPacked.from_pretrained(
            self.model_path, 
            torch_dtype=torch.bfloat16
        ).cpu()
        
        self.transformer.eval()
        self.transformer.high_quality_fp32_output_for_inference = True
        self.transformer.to(dtype=torch.bfloat16)
        self.transformer.requires_grad_(False)
        
        # 應用 LoRA
        if lora_file is not None:
            self._apply_lora(lora_file, lora_multiplier)
            
        # 設置設備
        if not self.high_vram:
            DynamicSwapInstaller.install_model(self.transformer, device=gpu)
        else:
            self.transformer.to(gpu)
            
        return True
        
    def _apply_lora(self, lora_file: str, lora_multiplier: float):
        """應用 LoRA 權重"""
        import os
        state_dict = self.transformer.state_dict()
        print(f"Merging LoRA file {os.path.basename(lora_file)} ...")
        state_dict = merge_lora_to_state_dict(
            state_dict, lora_file, lora_multiplier, device=gpu
        )
        gc.collect()
        info = self.transformer.load_state_dict(state_dict, strict=True, assign=True)
        print(f"LoRA applied: {info}")
        
    def get_models(self):
        """獲取所有模型"""
        return {
            'text_encoder': self.text_encoder,
            'text_encoder_2': self.text_encoder_2,
            'tokenizer': self.tokenizer,
            'tokenizer_2': self.tokenizer_2,
            'vae': self.vae,
            'feature_extractor': self.feature_extractor,
            'image_encoder': self.image_encoder,
            'transformer': self.transformer
        }
