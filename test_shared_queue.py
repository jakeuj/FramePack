#!/usr/bin/env python3
"""
測試共享隊列功能
驗證多個 GPU 服務實例是否能正確共享隊列
"""

import os
import sys
import time
import numpy as np
from core.queue_manager import ImageProcessingQueue

def test_shared_queue():
    """測試共享隊列功能"""
    print("🧪 測試共享隊列功能")
    print("=" * 50)
    
    # 創建兩個隊列管理器，模擬兩個 GPU 服務
    print("📋 創建兩個隊列管理器...")
    queue_gpu0 = ImageProcessingQueue(gpu_id="0", shared_queue=True)
    queue_gpu1 = ImageProcessingQueue(gpu_id="1", shared_queue=True)
    
    # 創建測試圖片
    print("🖼️  創建測試圖片...")
    test_image1 = np.random.randint(0, 255, (512, 512, 3), dtype=np.uint8)
    test_image2 = np.random.randint(0, 255, (512, 512, 3), dtype=np.uint8)
    
    # GPU 0 添加第一個項目
    print("➕ GPU 0 添加第一個項目...")
    item_id1 = queue_gpu0.add_item(
        image=test_image1,
        prompt="測試提示詞 1",
        n_prompt="負面提示詞 1",
        seed=12345,
        total_second_length=3.0,
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
    print(f"✅ 項目 1 已添加: {item_id1}")
    
    # GPU 1 添加第二個項目
    print("➕ GPU 1 添加第二個項目...")
    item_id2 = queue_gpu1.add_item(
        image=test_image2,
        prompt="測試提示詞 2",
        n_prompt="負面提示詞 2",
        seed=67890,
        total_second_length=4.0,
        latent_window_size=20,
        steps=25,
        cfg=8.0,
        gs=1.2,
        rs=0.9,
        gpu_memory_preservation=True,
        use_teacache=True,
        mp4_crf=20,
        resolution=768,
        lora_file="test.safetensors",
        lora_multiplier=0.8,
        use_magcache=True,
        magcache_thresh=0.6,
        magcache_K=15,
        magcache_retention_ratio=0.9
    )
    print(f"✅ 項目 2 已添加: {item_id2}")
    
    # 檢查隊列狀態
    print("\n📊 檢查隊列狀態...")
    status_gpu0 = queue_gpu0.get_queue_status()
    status_gpu1 = queue_gpu1.get_queue_status()
    
    print(f"GPU 0 看到的隊列狀態: {status_gpu0}")
    print(f"GPU 1 看到的隊列狀態: {status_gpu1}")
    
    # 驗證兩個 GPU 看到相同的隊列
    if status_gpu0['total'] == status_gpu1['total'] == 2:
        print("✅ 兩個 GPU 都看到了 2 個項目")
    else:
        print("❌ 隊列同步失敗")
        return False
    
    # 檢查隊列項目
    print("\n📋 檢查隊列項目...")
    items_gpu0 = queue_gpu0.get_queue_items()
    items_gpu1 = queue_gpu1.get_queue_items()
    
    print(f"GPU 0 看到的項目: {len(items_gpu0)} 個")
    print(f"GPU 1 看到的項目: {len(items_gpu1)} 個")
    
    for i, item in enumerate(items_gpu0):
        print(f"  項目 {i+1}: ID={item[0]}, 狀態={item[1]}, 時間={item[2]}")
    
    # 測試項目處理
    print("\n🔄 測試項目處理...")
    
    # GPU 0 獲取下一個項目
    print("GPU 0 嘗試獲取下一個項目...")
    next_item_gpu0 = queue_gpu0.get_next_item()
    if next_item_gpu0:
        print(f"✅ GPU 0 獲取到項目: {next_item_gpu0.id}")
        print(f"   提示詞: {next_item_gpu0.prompt}")
        print(f"   處理 GPU: {next_item_gpu0.processing_gpu}")
    else:
        print("❌ GPU 0 未獲取到項目")
        return False
    
    # GPU 1 獲取下一個項目
    print("GPU 1 嘗試獲取下一個項目...")
    next_item_gpu1 = queue_gpu1.get_next_item()
    if next_item_gpu1:
        print(f"✅ GPU 1 獲取到項目: {next_item_gpu1.id}")
        print(f"   提示詞: {next_item_gpu1.prompt}")
        print(f"   處理 GPU: {next_item_gpu1.processing_gpu}")
    else:
        print("❌ GPU 1 未獲取到項目")
        return False
    
    # 驗證不同的項目被分配給不同的 GPU
    if next_item_gpu0.id != next_item_gpu1.id:
        print("✅ 不同的項目被分配給不同的 GPU")
    else:
        print("❌ 相同的項目被分配給兩個 GPU")
        return False
    
    # 檢查更新後的隊列狀態
    print("\n📊 檢查處理後的隊列狀態...")
    status_after = queue_gpu0.get_queue_status()
    print(f"處理後狀態: {status_after}")
    
    if status_after['processing'] == 2:
        print("✅ 兩個項目都標記為處理中")
    else:
        print("❌ 項目狀態更新失敗")
        return False
    
    # 測試完成項目
    print("\n✅ 測試完成項目...")
    queue_gpu0.complete_item(next_item_gpu0.id, f"output_{next_item_gpu0.id}.mp4")
    queue_gpu1.complete_item(next_item_gpu1.id, f"output_{next_item_gpu1.id}.mp4")
    
    # 檢查最終狀態
    print("\n📊 檢查最終隊列狀態...")
    final_status = queue_gpu0.get_queue_status()
    print(f"最終狀態: {final_status}")
    
    if final_status['completed'] == 2:
        print("✅ 兩個項目都標記為已完成")
    else:
        print("❌ 項目完成狀態更新失敗")
        return False
    
    print("\n🎉 所有測試通過！共享隊列功能正常工作")
    return True

def test_queue_persistence():
    """測試隊列持久化"""
    print("\n🧪 測試隊列持久化")
    print("=" * 30)
    
    # 創建隊列管理器並添加項目
    queue1 = ImageProcessingQueue(gpu_id="test", shared_queue=True)
    test_image = np.random.randint(0, 255, (256, 256, 3), dtype=np.uint8)
    
    item_id = queue1.add_item(
        image=test_image,
        prompt="持久化測試",
        n_prompt="",
        seed=99999,
        total_second_length=2.0,
        latent_window_size=12,
        steps=15,
        cfg=6.0,
        gs=1.0,
        rs=1.0,
        gpu_memory_preservation=False,
        use_teacache=False,
        mp4_crf=16,
        resolution=256,
        lora_file=None,
        lora_multiplier=1.0,
        use_magcache=False,
        magcache_thresh=0.4,
        magcache_K=8,
        magcache_retention_ratio=0.7
    )
    
    print(f"添加項目: {item_id}")
    
    # 創建新的隊列管理器實例
    queue2 = ImageProcessingQueue(gpu_id="test2", shared_queue=True)
    
    # 檢查是否能看到之前添加的項目
    status = queue2.get_queue_status()
    print(f"新實例看到的狀態: {status}")
    
    if status['total'] > 0:
        print("✅ 隊列持久化測試通過")
        return True
    else:
        print("❌ 隊列持久化測試失敗")
        return False

def cleanup_test_data():
    """清理測試數據"""
    print("\n🧹 清理測試數據...")
    import shutil
    
    if os.path.exists("queue_data"):
        shutil.rmtree("queue_data")
        print("✅ 測試數據已清理")

def main():
    """主測試函數"""
    print("🚀 FramePack 共享隊列功能測試")
    print("=" * 60)
    
    try:
        # 清理之前的測試數據
        cleanup_test_data()
        
        # 測試共享隊列
        if not test_shared_queue():
            print("❌ 共享隊列測試失敗")
            return False
        
        # 測試持久化
        if not test_queue_persistence():
            print("❌ 持久化測試失敗")
            return False
        
        print("\n🎉 所有測試都通過了！")
        print("\n📝 測試總結:")
        print("✅ 多 GPU 服務可以共享同一個隊列")
        print("✅ 項目會自動分配給不同的 GPU")
        print("✅ 隊列狀態在所有服務間同步")
        print("✅ 隊列數據持久化到文件系統")
        
        return True
        
    except Exception as e:
        print(f"❌ 測試過程中發生錯誤: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # 清理測試數據
        cleanup_test_data()

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
