# FramePack VRAM 優化文檔

## 概述

本文檔說明 FramePack 在 NVIDIA RTX 5090 (32GB) 上的 VRAM 優化方案——`medium_vram` 模式。
透過讓 transformer 與小型模型常駐 GPU，消除取樣迴圈中的反覆搬移，大幅提升影片生成速度。

## 模型 VRAM 佔用

| 模型 | dtype | VRAM |
|------|-------|------|
| text_encoder (LlamaModel) | fp16 | ~14 GB |
| text_encoder_2 (CLIPTextModel) | fp16 | ~0.24 GB |
| vae (AutoencoderKLHunyuanVideo) | fp16 | ~0.97 GB |
| image_encoder (SiglipVisionModel) | fp16 | ~0.84 GB |
| transformer (HunyuanVideoTransformer3DModelPacked) | bf16 | ~25.7 GB |
| **合計** | | **~41.75 GB** |

## VRAM 模式

| 模式 | 觸發條件 | GPU 常駐模型 | 取樣迴圈搬移 |
|------|---------|-------------|-------------|
| high_vram | VRAM > 60 GB | 全部 (~42 GB) | 無 |
| **medium_vram** | `--medium-vram` 或 VRAM > 28 GB | transformer + vae + 小模型 (~28 GB) | **無** |
| 低 VRAM（預設） | VRAM ≤ 28 GB | 無（動態搬移） | 每個 section 搬移 transformer (~25.7 GB) |

## 優化效果

- **優化前**：每個 section 需搬移 ~25.7 GB transformer 進出 GPU → 嚴重拖慢速度
- **優化後**：transformer 常駐 GPU，取樣迴圈零搬移，僅首次編碼時 text_encoder 透過 DynamicSwap 串流

## 推論流程圖

- [原始 FramePack 推論流程（低 VRAM）](原始%20FramePack%20推論流程.md)
- [RTX 5090 優化後推論流程（medium_vram）](RTX%205090%20優化後推論流程.md)

## 使用方式

```bash
# 自動偵測（VRAM > 28GB 自動啟用 medium_vram）
python demo_gradio.py

# 手動強制啟用
python demo_gradio.py --medium-vram
python demo_gradio_f1.py --medium-vram
```

## VRAM 峰值估算（medium_vram，第二次執行）

| 項目 | VRAM |
|------|------|
| transformer | 25.7 GB |
| vae + image_encoder + text_encoder_2 | 2.05 GB |
| DynamicSwap text_encoder 暫存 (~1 layer) | ~0.5 GB |
| Forward pass activations | ~0.5-1 GB |
| **峰值合計** | **~28.8-29.3 GB / 32 GB** |

> 剩餘 ~3 GB 作為緩衝。text encoding 前會呼叫 `empty_cache()` 釋放 PyTorch cache 碎片。

