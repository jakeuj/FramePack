#!/usr/bin/env python3
"""
調試完整應用程序啟動流程
"""

import os
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
os.environ['TOKENIZERS_PARALLELISM'] = 'false'

def debug_app_startup():
    """調試應用程序啟動流程"""
    
    try:
        print("1. 導入模組...")
        from diffusers_helper.hf_login import login
        from apps import FramePackF1App
        print("✓ 模組導入成功")
    except Exception as e:
        print(f"✗ 模組導入失敗: {e}")
        return False
    
    try:
        print("2. 創建應用程序實例...")
        app = FramePackF1App()
        print("✓ 應用程序實例創建成功")
    except Exception as e:
        print(f"✗ 應用程序實例創建失敗: {e}")
        return False
    
    try:
        print("3. 初始化應用程序...")
        app.initialize()
        print("✓ 應用程序初始化成功")
    except Exception as e:
        print(f"✗ 應用程序初始化失敗: {e}")
        return False
    
    try:
        print("4. 創建界面...")
        interface = app.create_interface()
        print("✓ 界面創建成功")
        print(f"界面類型: {type(interface)}")
    except Exception as e:
        print(f"✗ 界面創建失敗: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    try:
        print("5. 測試界面啟動（不實際啟動服務器）...")
        # 不實際啟動，只是測試配置
        auth_settings = app.config.get_auth_settings() if hasattr(app.config, 'get_auth_settings') else None
        launch_kwargs = {
            'server_name': app.config.server_name,
            'server_port': app.config.server_port,
            'share': app.config.share,
            'inbrowser': app.config.inbrowser,
            'allowed_paths': [app.config.output_dir],
        }
        
        if auth_settings:
            launch_kwargs['auth'] = auth_settings
        
        print(f"啟動參數: {launch_kwargs}")
        print("✓ 啟動配置正常")
    except Exception as e:
        print(f"✗ 啟動配置失敗: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("開始調試應用程序啟動流程...")
    success = debug_app_startup()
    
    if success:
        print("\n所有調試步驟通過！應用程序應該可以正常啟動。")
    else:
        print("\n調試失敗！請檢查錯誤信息。")
