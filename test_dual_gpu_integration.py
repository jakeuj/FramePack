#!/usr/bin/env python3
"""
雙 GPU 集成測試
測試實際運行中的雙 GPU 服務是否正確共享隊列
"""

import os
import sys
import time
import requests
import json
from typing import Dict, Any

def test_service_availability():
    """測試服務可用性"""
    print("🔍 測試服務可用性...")
    
    services = {
        "GPU 0": "http://localhost:7860",
        "GPU 1": "http://localhost:7861"
    }
    
    available_services = {}
    
    for name, url in services.items():
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                print(f"✅ {name} 服務可用 ({url})")
                available_services[name] = url
            else:
                print(f"❌ {name} 服務不可用 - HTTP {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"❌ {name} 服務連接失敗: {e}")
    
    return available_services

def check_queue_files():
    """檢查共享隊列文件"""
    print("\n📁 檢查共享隊列文件...")
    
    queue_dir = "queue_data"
    queue_file = os.path.join(queue_dir, "queue.json")
    images_dir = os.path.join(queue_dir, "images")
    
    if os.path.exists(queue_dir):
        print(f"✅ 隊列目錄存在: {queue_dir}")
        
        if os.path.exists(queue_file):
            try:
                with open(queue_file, 'r', encoding='utf-8') as f:
                    queue_data = json.load(f)
                print(f"✅ 隊列文件可讀，項目數量: {len(queue_data)}")
                
                # 顯示隊列項目
                for i, item in enumerate(queue_data):
                    status = item.get('status', 'unknown')
                    gpu = item.get('processing_gpu', 'N/A')
                    print(f"   項目 {i+1}: 狀態={status}, GPU={gpu}")
                    
            except Exception as e:
                print(f"❌ 隊列文件讀取失敗: {e}")
        else:
            print("ℹ️  隊列文件不存在（正常，如果沒有任務）")
        
        if os.path.exists(images_dir):
            image_count = len([f for f in os.listdir(images_dir) if f.endswith('.pkl')])
            print(f"✅ 圖片暫存目錄存在，圖片數量: {image_count}")
        else:
            print("ℹ️  圖片暫存目錄不存在（正常，如果沒有任務）")
    else:
        print("❌ 隊列目錄不存在")
        return False
    
    return True

def test_queue_manager_directly():
    """直接測試隊列管理器"""
    print("\n🧪 直接測試隊列管理器...")
    
    try:
        # 導入隊列管理器
        sys.path.insert(0, os.path.dirname(__file__))
        from core.queue_manager import ImageProcessingQueue
        
        # 創建兩個隊列實例，模擬兩個服務
        queue_gpu0 = ImageProcessingQueue(gpu_id="0", shared_queue=True)
        queue_gpu1 = ImageProcessingQueue(gpu_id="1", shared_queue=True)
        
        print("✅ 隊列管理器創建成功")
        
        # 檢查隊列狀態
        status_0 = queue_gpu0.get_queue_status()
        status_1 = queue_gpu1.get_queue_status()
        
        print(f"GPU 0 隊列狀態: {status_0}")
        print(f"GPU 1 隊列狀態: {status_1}")
        
        # 驗證狀態一致性
        if status_0['total'] == status_1['total']:
            print("✅ 兩個 GPU 看到相同的隊列大小")
        else:
            print("❌ 隊列狀態不一致")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ 隊列管理器測試失敗: {e}")
        return False

def check_gpu_processes():
    """檢查 GPU 進程"""
    print("\n🖥️  檢查 GPU 進程...")
    
    try:
        # 檢查 nvidia-smi
        import subprocess
        result = subprocess.run(['nvidia-smi', '--query-compute-apps=pid,process_name,gpu_uuid,used_memory', '--format=csv,noheader'], 
                              capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            if lines and lines[0]:
                print("✅ 檢測到 GPU 進程:")
                for line in lines:
                    if line.strip():
                        print(f"   {line}")
            else:
                print("ℹ️  目前沒有 GPU 進程運行")
        else:
            print("❌ nvidia-smi 執行失敗")
            
    except Exception as e:
        print(f"❌ GPU 進程檢查失敗: {e}")

def check_service_logs():
    """檢查服務日誌"""
    print("\n📋 檢查服務日誌...")
    
    log_files = [
        "logs/framepack_gpu0_7860.log",
        "logs/framepack_gpu1_7861.log"
    ]
    
    for log_file in log_files:
        if os.path.exists(log_file):
            print(f"✅ 日誌文件存在: {log_file}")
            
            # 讀取最後幾行
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    if lines:
                        print(f"   最後一行: {lines[-1].strip()}")
                        
                        # 檢查是否有錯誤
                        recent_lines = lines[-10:]
                        error_count = sum(1 for line in recent_lines if 'error' in line.lower() or 'traceback' in line.lower())
                        if error_count > 0:
                            print(f"   ⚠️  最近 10 行中有 {error_count} 行包含錯誤")
                        else:
                            print("   ✅ 最近沒有錯誤")
            except Exception as e:
                print(f"   ❌ 讀取日誌失敗: {e}")
        else:
            print(f"❌ 日誌文件不存在: {log_file}")

def main():
    """主測試函數"""
    print("🚀 FramePack 雙 GPU 集成測試")
    print("=" * 50)
    
    tests = [
        ("服務可用性", test_service_availability),
        ("隊列文件", check_queue_files),
        ("隊列管理器", test_queue_manager_directly),
        ("GPU 進程", check_gpu_processes),
        ("服務日誌", check_service_logs),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n🔍 執行測試: {test_name}")
        try:
            result = test_func()
            results[test_name] = result
            if result is not False:
                print(f"✅ {test_name} 測試完成")
            else:
                print(f"❌ {test_name} 測試失敗")
        except Exception as e:
            print(f"❌ {test_name} 測試異常: {e}")
            results[test_name] = False
    
    # 總結
    print("\n" + "=" * 50)
    print("📊 測試總結:")
    
    for test_name, result in results.items():
        status = "✅ 通過" if result is not False else "❌ 失敗"
        print(f"  {test_name}: {status}")
    
    # 檢查關鍵測試
    critical_tests = ["服務可用性", "隊列文件", "隊列管理器"]
    critical_passed = sum(1 for test in critical_tests if results.get(test) is not False)
    
    print(f"\n關鍵測試通過率: {critical_passed}/{len(critical_tests)}")
    
    if critical_passed == len(critical_tests):
        print("\n🎉 雙 GPU 系統運行正常！")
        print("\n📝 使用建議:")
        print("1. 可以訪問 http://211.20.19.206:7860 或 http://211.20.19.206:7861")
        print("2. 上傳圖片到任一服務都會進入共享隊列")
        print("3. 兩個 GPU 會自動並行處理隊列中的任務")
        print("4. 使用 ./stop_dual_gpu.sh status 監控服務狀態")
        return True
    else:
        print("\n❌ 系統存在問題，請檢查配置")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
