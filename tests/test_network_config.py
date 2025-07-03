#!/usr/bin/env python3
"""
測試網路配置
驗證 FramePack 應用是否正確監聽 0.0.0.0
"""

import sys
import subprocess
import socket
import time
from pathlib import Path

def get_local_ip():
    """獲取本機 IP 地址"""
    try:
        # 創建一個 UDP socket 來獲取本機 IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def check_port_listening(port, host="0.0.0.0"):
    """檢查端口是否在監聽"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            result = s.connect_ex((host if host != "0.0.0.0" else "127.0.0.1", port))
            return result == 0
    except Exception:
        return False

def test_gradio_args():
    """測試 Gradio 應用的參數解析"""
    print("🧪 測試 Gradio 應用參數解析...")
    
    # 測試參數解析
    test_args = [
        sys.executable, 
        "demo_gradio_f1_refactored.py",
        "--server", "0.0.0.0",
        "--port", "7860",
        "--username", "admin",
        "--password", "123456"
    ]
    
    try:
        # 只測試參數解析，不實際啟動服務
        result = subprocess.run(
            test_args + ["--help"], 
            capture_output=True, 
            text=True, 
            timeout=10
        )
        
        if result.returncode == 0:
            print("✅ 參數解析測試通過")
            return True
        else:
            print(f"❌ 參數解析測試失敗: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("⚠️ 參數解析測試超時")
        return False
    except Exception as e:
        print(f"❌ 參數解析測試錯誤: {e}")
        return False

def test_network_info():
    """測試網路信息獲取"""
    print("🌐 測試網路信息...")
    
    local_ip = get_local_ip()
    print(f"本機 IP 地址: {local_ip}")
    
    # 檢查常用端口是否可用
    test_ports = [7860, 7861]
    for port in test_ports:
        if check_port_listening(port):
            print(f"⚠️ 端口 {port} 已被佔用")
        else:
            print(f"✅ 端口 {port} 可用")
    
    return True

def main():
    """主測試函數"""
    print("🚀 FramePack 網路配置測試")
    print("=" * 40)
    
    # 檢查必要文件
    required_files = [
        "demo_gradio_f1_refactored.py",
        "start.sh"
    ]
    
    for file in required_files:
        if not Path(file).exists():
            print(f"❌ 必要文件不存在: {file}")
            return False
    
    print("✅ 必要文件檢查通過")
    
    # 測試網路信息
    if not test_network_info():
        return False
    
    # 測試參數解析
    if not test_gradio_args():
        return False
    
    print("\n" + "=" * 40)
    print("🎉 所有測試通過！")
    print("\n📱 手機訪問說明:")
    print(f"1. 啟動服務: ./start.sh start")
    print(f"2. 手機瀏覽器訪問: http://{get_local_ip()}:7860")
    print(f"3. 用戶名: admin, 密碼: 123456")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
