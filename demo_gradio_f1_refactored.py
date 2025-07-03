#!/usr/bin/env python3
"""
重構後的 FramePack F1 應用程式入口
基於原始 demo_gradio_f1.py，使用物件導向設計重構，包含認證和高級文件管理功能
"""

import os
# 在導入任何 PyTorch 相關模組之前設置 MPS 回退
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
os.environ['TOKENIZERS_PARALLELISM'] = 'false'

from diffusers_helper.hf_login import login
from apps import FramePackF1App

if __name__ == "__main__":
    app = FramePackF1App()
    app.launch()
