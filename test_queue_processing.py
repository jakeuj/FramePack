#!/usr/bin/env python3
"""
測試隊列處理功能
模擬用戶點擊"開始處理隊列"按鈕的操作
"""

import os
import sys
import time
import numpy as np

def test_queue_processing():
    """測試隊列處理功能"""
    print("🧪 測試隊列處理功能")
    print("=" * 30)
    
    try:
        # 導入必要的模組
        sys.path.insert(0, os.path.dirname(__file__))
        from core.queue_manager import ImageProcessingQueue
        
        # 創建隊列管理器
        queue_manager = ImageProcessingQueue(gpu_id="test", shared_queue=True)
        print("✅ 隊列管理器創建成功")
        
        # 測試 is_empty 方法
        print("\n🔍 測試 is_empty 方法...")
        is_empty = queue_manager.is_empty()
        print(f"隊列是否為空: {is_empty}")
        
        # 如果隊列為空，添加一個測試項目
        if is_empty:
            print("➕ 隊列為空，添加測試項目...")
            test_image = np.random.randint(0, 255, (512, 512, 3), dtype=np.uint8)
            
            item_id = queue_manager.add_item(
                image=test_image,
                prompt="測試隊列處理",
                n_prompt="",
                seed=12345,
                total_second_length=2.0,
                latent_window_size=16,
                steps=20,
                cfg=7.5,
                gs=1.0,
                rs=1.0,
                gpu_memory_preservation=False,
                use_teacache=False,
                mp4_crf=18,
                resolution=512,
                lora_file=None,
                lora_multiplier=1.0,
                use_magcache=False,
                magcache_thresh=0.5,
                magcache_K=10,
                magcache_retention_ratio=0.8
            )
            print(f"✅ 測試項目已添加: {item_id}")
        
        # 再次檢查是否為空
        print("\n🔍 再次檢查隊列狀態...")
        is_empty_after = queue_manager.is_empty()
        print(f"隊列是否為空: {is_empty_after}")
        
        # 獲取隊列狀態
        status = queue_manager.get_queue_status()
        print(f"隊列狀態: {status}")
        
        # 測試獲取下一個項目
        print("\n🔄 測試獲取下一個項目...")
        next_item = queue_manager.get_next_item()
        if next_item:
            print(f"✅ 成功獲取項目: {next_item.id}")
            print(f"   提示詞: {next_item.prompt}")
            print(f"   處理 GPU: {next_item.processing_gpu}")
            
            # 模擬處理完成
            print("✅ 模擬處理完成...")
            queue_manager.complete_item(next_item.id, f"output_{next_item.id}.mp4")
            
        else:
            print("ℹ️  沒有待處理的項目")
        
        # 最終狀態檢查
        print("\n📊 最終隊列狀態...")
        final_status = queue_manager.get_queue_status()
        print(f"最終狀態: {final_status}")
        
        # 測試清理已完成項目
        print("\n🧹 測試清理已完成項目...")
        queue_manager.clear_completed()
        
        after_clear_status = queue_manager.get_queue_status()
        print(f"清理後狀態: {after_clear_status}")
        
        print("\n✅ 隊列處理功能測試完成")
        return True
        
    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_base_app_methods():
    """測試 BaseApp 的隊列相關方法"""
    print("\n🧪 測試 BaseApp 隊列方法")
    print("=" * 30)
    
    try:
        # 導入 BaseApp
        from apps.framepack_f1_app import FramePackF1App
        
        # 創建應用實例
        print("📱 創建應用實例...")
        app = FramePackF1App()
        app.initialize()
        print("✅ 應用實例創建成功")
        
        # 測試 refresh_queue 方法
        print("\n🔄 測試 refresh_queue 方法...")
        status_text, queue_items = app.refresh_queue()
        print(f"狀態文字: {status_text}")
        print(f"隊列項目數量: {len(queue_items)}")
        
        # 測試 clear_completed_items 方法
        print("\n🧹 測試 clear_completed_items 方法...")
        result = app.clear_completed_items()
        print(f"清理結果: {result}")
        
        # 測試 clear_queue 方法
        print("\n🗑️  測試 clear_queue 方法...")
        clear_result = app.clear_queue()
        print(f"清空結果: {clear_result}")
        
        print("\n✅ BaseApp 隊列方法測試完成")
        return True
        
    except Exception as e:
        print(f"❌ BaseApp 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主測試函數"""
    print("🚀 隊列處理功能測試")
    print("=" * 50)
    
    tests = [
        ("隊列處理", test_queue_processing),
        ("BaseApp 方法", test_base_app_methods),
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
        print("\n🎉 所有隊列處理測試都通過了！")
        print("\n📝 現在您可以:")
        print("1. 訪問 http://211.20.19.206:7860 或 http://211.20.19.206:7861")
        print("2. 上傳圖片並添加到隊列")
        print("3. 點擊「開始處理隊列」按鈕")
        print("4. 兩個 GPU 會自動並行處理任務")
        return True
    else:
        print("\n❌ 部分測試失敗，請檢查錯誤信息")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
