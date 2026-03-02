# VRAM 管理與推論流程詳細參考

本文件包含 FramePack 各模型的 VRAM 佔用大小、三級 VRAM 模式說明、以及各模式下的推論流程時序圖。
當需要分析記憶體問題、優化 GPU 使用、或修改 offload 邏輯時，請參考此文件。

## 模型 VRAM 佔用大小

| 模型 | 來源 | dtype | VRAM |
|------|------|-------|------|
| **text_encoder** (LlamaModel) | `hunyuanvideo-community/HunyuanVideo` | fp16 | **~14 GB** |
| **text_encoder_2** (CLIPTextModel) | 同上 | fp16 | **~0.24 GB** |
| **vae** (AutoencoderKLHunyuanVideo) | 同上 | fp16 | **~0.97 GB** |
| **image_encoder** (SiglipVisionModel) | `lllyasviel/flux_redux_bfl` | fp16 | **~0.84 GB** |
| **transformer** (HunyuanVideoTransformer3DModelPacked) | `lllyasviel/FramePackI2V_HY` 或 `lllyasviel/FramePack_F1_I2V_HY_20250503` | bf16 | **~25.7 GB** |
| **全部合計** | | | **~41.75 GB** |

資料來源：HuggingFace 上各模型的 safetensors 檔案大小（即實際 GPU 記憶體佔用）。

## VRAM 模式（三級）

| 模式 | 條件 | 行為 |
|------|------|------|
| **`high_vram`** | VRAM > 60 GB | 所有模型常駐 GPU，無任何 offload |
| **`medium_vram`** | `--medium-vram` 或 28 < VRAM ≤ 60 GB | text_encoder 用 DynamicSwap；其餘模型（含 transformer）常駐 GPU (~28 GB) |
| **低 VRAM**（預設） | VRAM ≤ 28 GB | text_encoder 用 DynamicSwap；其餘模型動態 offload，每個 section 搬移 transformer |

### medium_vram 模式設計理由

RTX 5090 (32GB) 無法同時載入所有模型（合計 ~41.75 GB），但 transformer + vae + 小模型 ≈ 28 GB 可以放進 32 GB。
最大效能瓶頸是低 VRAM 模式下每個 section 都要搬移 25.7 GB 的 transformer，medium_vram 透過讓 transformer 常駐 GPU 來消除這個瓶頸。

## 推論流程 — 記憶體管理時序

### 低 VRAM 模式（每個 section 都搬移，效能瓶頸）

```
Phase 1: 編碼（一次性）
  CPU→GPU: text_encoder (DynamicSwap 串流 ~14GB) → encode → 卸載
  CPU→GPU: text_encoder_2 (~0.24GB) → encode → 卸載
  CPU→GPU: vae (~1GB) → vae_encode → 卸載
  CPU→GPU: image_encoder (~0.84GB) → clip_encode → 卸載

Phase 2: 取樣迴圈（每個 section 重複！⚠️ 效能瓶頸）
  ┌─ section loop ──────────────────────────────────┐
  │ CPU→GPU: transformer (~25.7GB)  ← 很慢!         │
  │ sample_hunyuan()                                 │
  │ GPU→CPU: transformer 卸載       ← 很慢!         │
  │ CPU→GPU: vae (~1GB)                              │
  │ vae_decode()                                     │
  │ GPU→CPU: vae 卸載                                │
  └──────────────────────────────────────────────────┘
```

### medium_vram 模式（RTX 5090 32GB 優化，零搬移）

```
啟動時載入常駐模型:
  CPU→GPU: text_encoder_2 (0.24GB) ← 常駐
  CPU→GPU: image_encoder (0.84GB)  ← 常駐
  CPU→GPU: vae (0.97GB)            ← 常駐
  已使用 ~2GB

Phase 1: 編碼（一次性）
  text_encoder 透過 DynamicSwap 串流（不常駐，~0.5GB 暫存/layer）
  vae_encode / clip_encode 直接使用已在 GPU 的模型

Phase 2: Transformer 載入（一次）
  CPU→GPU: transformer (25.7GB) ← 常駐，不用 DynamicSwap
  已使用 ~28GB / 32GB

Phase 3: 取樣迴圈 ✅ 零搬移！
  ┌─ section loop ──────────────────────────────────┐
  │ sample_hunyuan()  ← transformer 已在 GPU        │
  │ vae_decode()      ← vae 已在 GPU                │
  │ 🚀 無任何 offload/reload 操作                    │
  └──────────────────────────────────────────────────┘
```

### medium_vram 第二次執行時 VRAM 峰值估算

- transformer (25.7) + 小模型 (2.05) + DynamicSwap 暫存 (~0.5) + activations (~0.5-1) ≈ **28.8-29.3 GB / 32 GB**
- 在 text encoding 前呼叫 `empty_cache()` 釋放 PyTorch cache 碎片
- 剩餘 ~3 GB 留給中間張量和 PyTorch cache
- 如果解析度較高導致 OOM，可降低 `resolution` 或改回低 VRAM 模式

## 關鍵函式（`diffusers_helper/memory.py`）

| 函式 | 用途 |
|------|------|
| `DynamicSwapInstaller.install_model(model, device=gpu)` | 安裝 DynamicSwap，讓參數在存取時自動搬到 GPU（比 HF 的 sequential_offload 快 3 倍） |
| `DynamicSwapInstaller.uninstall_model(model)` | 移除 DynamicSwap |
| `move_model_to_device_with_memory_preservation(model, device, preserved_gb)` | 逐 module 搬移模型到 GPU，保留指定記憶體量 |
| `offload_model_from_device_for_memory_preservation(model, device, preserved_gb)` | 逐 module 從 GPU 卸載到 CPU，直到釋放足夠記憶體 |
| `load_model_as_complete(model, device)` | 整個模型載入 GPU 並追蹤到 `gpu_complete_modules` |
| `unload_complete_models(*args)` | 卸載所有追蹤中的模型 + 額外指定的模型 |
| `empty_cache()` | 清除 PyTorch CUDA/MPS cache |
| `fake_diffusers_current_device(model, device)` | 只搬移模型的第一個 weight 到目標裝置，讓 diffusers 認為模型在該裝置上 |

