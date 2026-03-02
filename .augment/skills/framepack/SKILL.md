---
name: framepack
description: Guide for working with the FramePack codebase — a next-frame prediction video generation system based on HunyuanVideo. Use this skill whenever the user asks about FramePack architecture, video generation pipeline, memory management, VRAM optimization, model loading, Gradio UI, LoRA integration, TeaCache, diffusion sampling, or any code changes in this repository. Also use when the user mentions image-to-video, latent windows, VAE encoding/decoding, CLIP vision, progressive video generation, GPU offload, DynamicSwap, medium_vram, high_vram, or RTX 5090/4090/3090 optimization.
---

# FramePack 專案 Skill

FramePack 是一個基於 next-frame-section prediction 的影片生成系統，能將輸入影像轉換為影片。它使用 HunyuanVideo 13B 模型，透過壓縮輸入 context 至固定長度來實現與影片長度無關的生成負載。

## 專案結構

```
FramePack/
├── demo_gradio.py          # 主要 Gradio UI 入口（標準版）
├── demo_gradio_f1.py       # F1 變體版本的 Gradio UI
├── requirements.txt        # Python 依賴
├── diffusers_helper/       # 核心引擎模組
│   ├── memory.py           # GPU/CPU 記憶體管理、DynamicSwapInstaller
│   ├── hunyuan.py          # HunyuanVideo 相關：prompt encoding、VAE encode/decode
│   ├── utils.py            # 工具函式：MP4 儲存、影像裁切、時間戳生成
│   ├── clip_vision.py      # CLIP Vision 編碼
│   ├── bucket_tools.py     # 解析度 bucket 匹配
│   ├── thread_utils.py     # AsyncStream 非同步串流工具
│   ├── hf_login.py         # HuggingFace 登入
│   ├── dit_common.py       # DiT 通用工具
│   ├── gradio/
│   │   └── progress_bar.py # 進度條 CSS/HTML 生成
│   ├── models/
│   │   └── hunyuan_video_packed.py  # HunyuanVideoTransformer3DModelPacked 模型
│   ├── pipelines/
│   │   └── k_diffusion_hunyuan.py   # sample_hunyuan 取樣管線
│   └── k_diffusion/
│       ├── uni_pc_fm.py    # UniPC 取樣器 
│       └── wrapper.py      # K-diffusion wrapper
└── utils/
    └── lora_utils.py       # LoRA 權重合併工具
```

## 核心架構

### 影片生成管線流程

1. **Text Encoding** — 使用 LlamaModel + CLIPTextModel 編碼正/負向 prompt
2. **Image Processing** — 上傳圖片裁切至最近的 bucket 解析度
3. **VAE Encoding** — 將輸入影像編碼為 latent
4. **CLIP Vision Encoding** — 使用 SiglipVisionModel 提取影像特徵
5. **Transformer Sampling** — 透過 `sample_hunyuan()` 使用 UniPC 取樣器生成 latent frames
6. **VAE Decoding** — 將生成的 latent 解碼為像素影片
7. **MP4 Output** — 以 24fps 儲存為 MP4

### 記憶體管理（`diffusers_helper/memory.py`）

- **`DynamicSwapInstaller`** — 比 HuggingFace 的 `enable_sequential_offload` 快 3 倍的動態模型搬移機制。透過 monkey-patch `__getattr__` 讓參數在存取時自動搬到 GPU
- **`gpu_memory_preservation`** — 使用者可設定保留的 GPU 記憶體量，避免 OOM
- **三級 VRAM 模式**：`high_vram`（>60GB，全常駐）、`medium_vram`（28-60GB，transformer+小模型常駐，text_encoder 用 DynamicSwap）、低 VRAM（≤28GB，動態 offload）
- 模型 VRAM 合計 ~41.75 GB（transformer ~25.7GB 佔最大宗，text_encoder ~14GB 次之）

> 📖 詳細的模型大小表、VRAM 模式說明、推論流程時序圖、峰值估算，請參考 `references/vram-management.md`

### Latent Window 機制

影片以 section 為單位逆向生成（inverted sampling）：
- `latent_window_size` 預設為 9，每個 section 生成 `latent_window_size * 4 - 3` 個 frames
- `total_latent_sections` = `(total_seconds * 24) / (latent_window_size * 4)`
- 使用 `history_latents` 累積生成結果，透過 `soft_append_bcthw` 做重疊融合
- Padding 策略：`[3] + [2] * (N-3) + [1, 0]`（當 sections > 4 時）

### 模型載入

- **Text Encoder**: `hunyuanvideo-community/HunyuanVideo` (LlamaModel + CLIPTextModel, fp16)
- **VAE**: `hunyuanvideo-community/HunyuanVideo` (AutoencoderKLHunyuanVideo, fp16)
- **Image Encoder**: `lllyasviel/flux_redux_bfl` (SiglipVisionModel, fp16)
- **Transformer**: `lllyasviel/FramePackI2V_HY` (HunyuanVideoTransformer3DModelPacked, bf16)
- 模型下載存放於 `./hf_download/`

### LoRA 支援（`utils/lora_utils.py`）

支援兩種 LoRA 格式：
- **Musubi Tuner** 格式（key 以 `lora_unet_` 開頭）
- **Diffusion-pipe** 格式（含 `lora_A`/`lora_B` 且有 `diffusion_model` 或 `transformer` prefix）
- LoRA 合併至 transformer state_dict，支援 multiplier 調整

### TeaCache 加速

`transformer.initialize_teacache(enable_teacache=True, num_steps=steps)` 可加速取樣，但可能影響手部/手指品質。建議先用 TeaCache 快速試想法，再用完整 diffusion 取得高品質結果。

## Gradio UI 參數

| 參數 | 預設值 | 說明 |
|------|--------|------|
| Resolution | 416 | 生成解析度（正方形基準） |
| Seed | 31337 | 隨機種子 |
| Total Video Length | 5 秒 | 影片總長度（最長 120 秒） |
| Steps | 25 | 取樣步數 |
| Distilled CFG Scale | 10.0 | Distilled guidance scale |
| TeaCache | 開啟 | 加速但可能降低手部品質 |
| MP4 CRF | 16 | 壓縮品質（0=無壓縮） |
| GPU Memory Preservation | 6 GB | 保留的 GPU 記憶體 |

## 啟動方式

```bash
# 標準版
python demo_gradio.py

# F1 版本
python demo_gradio_f1.py

# 常用選項
python demo_gradio.py --share --port 7860 --server 127.0.0.1 --inbrowser --output_dir ./outputs

# RTX 5090 (32GB) 優化：手動強制啟用 medium_vram 模式
python demo_gradio.py --medium-vram
python demo_gradio_f1.py --medium-vram
# 注意：VRAM > 28GB 時會自動啟用 medium_vram，通常不需要手動指定
```

## 支援平台

- **CUDA** (RTX 30XX/40XX/50XX)：完整支援，最低 6GB VRAM
- **macOS MPS** (Apple Silicon)：支援，使用 `PYTORCH_ENABLE_MPS_FALLBACK=1`
- 模型預設 dtype：transformer 用 bf16，其餘用 fp16

## 開發注意事項

- 修改取樣邏輯時，注意 `worker()` 函式是在非同步執行緒中執行（`async_run`）
- `AsyncStream` 用於 worker 與 Gradio UI 之間的通訊（progress、file、end 事件）
- 影片生成是逆向的（ending actions 先生成，starting actions 後生成）
- `demo_gradio.py` 和 `demo_gradio_f1.py` 結構相似但有不同的取樣策略
- 修改 `diffusers_helper/` 下的模組時，需同時確認兩個 demo 檔案的相容性

