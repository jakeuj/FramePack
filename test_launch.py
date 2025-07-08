#!/usr/bin/env python3
"""
測試應用程序實際啟動
"""

import os
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
os.environ['TOKENIZERS_PARALLELISM'] = 'false'

from diffusers_helper.hf_login import login
from apps import FramePackF1App

if __name__ == "__main__":
    print("開始啟動應用程序...")
    
    app = FramePackF1App()
    print("應用程序實例創建完成")
    
    # 初始化
    app.initialize()
    print("應用程序初始化完成")
    
    # 創建界面
    interface = app.create_interface()
    print("界面創建完成")
    
    # 獲取認證設置
    auth_settings = app.config.get_auth_settings() if hasattr(app.config, 'get_auth_settings') else None
    print(f"認證設置: {auth_settings}")
    
    # 啟動應用
    launch_kwargs = {
        'server_name': '0.0.0.0',
        'server_port': 7860,
        'share': False,
        'inbrowser': False,
        'allowed_paths': [app.config.output_dir],
    }
    
    if auth_settings:
        launch_kwargs['auth'] = auth_settings
    
    print(f"啟動參數: {launch_kwargs}")
    print("正在啟動 Gradio 服務器...")
    
    try:
        interface.launch(**launch_kwargs)
    except Exception as e:
        print(f"啟動失敗: {e}")
        import traceback
        traceback.print_exc()
