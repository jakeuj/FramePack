#!/usr/bin/env python3
"""
重構後的 FramePack 應用程式入口
基於原始 demo_gradio.py，使用物件導向設計重構
"""

import os
# 在導入任何 PyTorch 相關模組之前設置 MPS 回退
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
os.environ['TOKENIZERS_PARALLELISM'] = 'false'

from diffusers_helper.hf_login import login
from apps import FramePackApp

if __name__ == "__main__":
    app = FramePackApp()
    app.launch()
