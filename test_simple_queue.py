#!/usr/bin/env python3
"""
簡化的共享隊列功能測試
不依賴 numpy，使用基本的 Python 功能
"""

import os
import sys
import time
import json

def test_file_operations():
    """測試基本的文件操作功能"""
    print("🧪 測試基本文件操作")
    print("=" * 30)
    
    # 創建測試目錄
    test_dir = "test_queue_data"
    os.makedirs(test_dir, exist_ok=True)
    os.makedirs(os.path.join(test_dir, "images"), exist_ok=True)
    
    # 測試 JSON 文件操作
    queue_file = os.path.join(test_dir, "queue.json")
    test_data = [
        {
            "id": "test_item_1",
            "prompt": "測試提示詞 1",
            "status": "waiting",
            "created_at": time.time(),
            "gpu_id": "0"
        },
        {
            "id": "test_item_2", 
            "prompt": "測試提示詞 2",
            "status": "waiting",
            "created_at": time.time(),
            "gpu_id": "1"
        }
    ]
    
    # 保存測試數據
    with open(queue_file, 'w', encoding='utf-8') as f:
        json.dump(test_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 已創建測試隊列文件: {queue_file}")
    
    # 讀取測試數據
    with open(queue_file, 'r', encoding='utf-8') as f:
        loaded_data = json.load(f)
    
    print(f"✅ 成功讀取 {len(loaded_data)} 個項目")
    
    # 測試文件鎖（簡化版本）
    lock_file = os.path.join(test_dir, "queue.lock")
    
    try:
        # 創建鎖文件
        with open(lock_file, 'w') as f:
            f.write(str(os.getpid()))
        print("✅ 文件鎖創建成功")
        
        # 模擬並發操作
        for i in range(3):
            # 讀取當前數據
            with open(queue_file, 'r', encoding='utf-8') as f:
                current_data = json.load(f)
            
            # 修改數據
            if i < len(current_data):
                current_data[i]['status'] = 'processing'
                current_data[i]['processing_gpu'] = f'gpu_{i}'
            
            # 寫回數據
            with open(queue_file, 'w', encoding='utf-8') as f:
                json.dump(current_data, f, ensure_ascii=False, indent=2)
            
            print(f"✅ 模擬操作 {i+1} 完成")
        
    finally:
        # 清理鎖文件
        if os.path.exists(lock_file):
            os.remove(lock_file)
        print("✅ 文件鎖已清理")
    
    # 驗證最終結果
    with open(queue_file, 'r', encoding='utf-8') as f:
        final_data = json.load(f)
    
    processing_count = sum(1 for item in final_data if item['status'] == 'processing')
    print(f"✅ 最終有 {processing_count} 個項目標記為處理中")
    
    # 清理測試數據
    import shutil
    shutil.rmtree(test_dir)
    print("✅ 測試數據已清理")
    
    return True

def test_queue_manager_import():
    """測試隊列管理器模組導入"""
    print("\n🧪 測試隊列管理器模組導入")
    print("=" * 35)
    
    try:
        # 嘗試導入核心模組
        sys.path.insert(0, os.path.dirname(__file__))
        
        from core.queue_manager import SharedQueueManager
        print("✅ SharedQueueManager 導入成功")
        
        # 創建實例
        manager = SharedQueueManager(queue_dir="test_shared_queue")
        print("✅ SharedQueueManager 實例創建成功")
        
        # 測試基本方法
        queue_data = manager._load_queue()
        print(f"✅ 隊列加載成功，項目數量: {len(queue_data)}")
        
        # 清理測試目錄
        import shutil
        if os.path.exists("test_shared_queue"):
            shutil.rmtree("test_shared_queue")
        
        return True
        
    except ImportError as e:
        print(f"❌ 模組導入失敗: {e}")
        return False
    except Exception as e:
        print(f"❌ 測試過程中發生錯誤: {e}")
        return False

def test_environment_setup():
    """測試環境設置"""
    print("\n🧪 測試環境設置")
    print("=" * 20)
    
    # 檢查 Python 版本
    python_version = sys.version_info
    print(f"Python 版本: {python_version.major}.{python_version.minor}.{python_version.micro}")
    
    if python_version >= (3, 6):
        print("✅ Python 版本符合要求")
    else:
        print("❌ Python 版本過低")
        return False
    
    # 檢查必要的模組
    required_modules = ['json', 'os', 'time', 'threading']
    for module in required_modules:
        try:
            __import__(module)
            print(f"✅ {module} 模組可用")
        except ImportError:
            print(f"❌ {module} 模組不可用")
            return False
    
    # 檢查文件系統權限
    try:
        test_file = "test_permissions.tmp"
        with open(test_file, 'w') as f:
            f.write("test")
        os.remove(test_file)
        print("✅ 文件系統權限正常")
    except Exception as e:
        print(f"❌ 文件系統權限問題: {e}")
        return False
    
    return True

def main():
    """主測試函數"""
    print("🚀 FramePack 共享隊列基礎功能測試")
    print("=" * 50)
    
    tests = [
        ("環境設置", test_environment_setup),
        ("文件操作", test_file_operations),
        ("模組導入", test_queue_manager_import),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🔍 執行測試: {test_name}")
        try:
            if test_func():
                print(f"✅ {test_name} 測試通過")
                passed += 1
            else:
                print(f"❌ {test_name} 測試失敗")
        except Exception as e:
            print(f"❌ {test_name} 測試異常: {e}")
    
    print(f"\n📊 測試結果: {passed}/{total} 通過")
    
    if passed == total:
        print("\n🎉 所有基礎測試都通過了！")
        print("\n📝 下一步:")
        print("1. 確保安裝了必要的依賴 (numpy, gradio 等)")
        print("2. 使用 start_dual_gpu.sh 啟動雙 GPU 服務")
        print("3. 測試實際的圖片上傳和處理功能")
        return True
    else:
        print("\n❌ 部分測試失敗，請檢查環境配置")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
