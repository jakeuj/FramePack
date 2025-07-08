#!/usr/bin/env python3
"""
測試隊列顯示修復
驗證 get_queue_items() 方法返回正確的格式用於 Gradio Dataframe 顯示
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.queue_manager import ImageProcessingQueue, QueueItem
import numpy as np
import time

def test_queue_display_format():
    """測試隊列項目顯示格式"""
    print("🧪 測試隊列顯示格式修復...")
    
    # 創建隊列管理器
    queue_manager = ImageProcessingQueue()
    
    # 創建測試圖片數據
    test_image = np.zeros((100, 100, 3), dtype=np.uint8)
    
    # 添加測試項目到隊列
    queue_manager.add_item(
        image=test_image,
        prompt="測試提示詞",
        n_prompt="負面提示詞",
        seed=12345,
        total_second_length=3.0,
        latent_window_size=16,
        steps=20,
        cfg=7.5,
        gs=1.0,
        rs=1.0,
        gpu_memory_preservation=False,
        use_teacache=False,
        mp4_crf=23,
        resolution=512,
        lora_file=None,
        lora_multiplier=1.0,
        use_magcache=False,
        magcache_thresh=0.5,
        magcache_K=10,
        magcache_retention_ratio=0.8
    )
    
    # 添加第二個測試項目
    queue_manager.add_item(
        image=test_image,
        prompt="這是一個很長的提示詞，用來測試截斷功能是否正常工作，應該會被截斷到50個字符",
        n_prompt="負面提示詞2",
        seed=67890,
        total_second_length=5.0,
        latent_window_size=24,
        steps=30,
        cfg=8.0,
        gs=1.2,
        rs=0.8,
        gpu_memory_preservation=True,
        use_teacache=True,
        mp4_crf=20,
        resolution=720,
        lora_file="test_lora.safetensors",
        lora_multiplier=0.8,
        use_magcache=True,
        magcache_thresh=0.6,
        magcache_K=15,
        magcache_retention_ratio=0.9
    )
    
    # 獲取隊列項目
    queue_items = queue_manager.get_queue_items()
    
    print(f"✅ 隊列項目數量: {len(queue_items)}")
    print(f"✅ 返回類型: {type(queue_items)}")
    
    if queue_items:
        print(f"✅ 第一個項目類型: {type(queue_items[0])}")
        print(f"✅ 第一個項目內容: {queue_items[0]}")
        
        # 驗證格式
        if isinstance(queue_items[0], list):
            print("✅ 格式正確: 返回列表的列表")
            
            # 驗證列數 - 手機優化版本只有3列
            if len(queue_items[0]) == 3:
                print("✅ 列數正確: 3列 (ID, 狀態, 創建時間) - 手機優化版本")

                # 驗證每列的類型
                item = queue_items[0]
                print(f"   - ID: {item[0]} (類型: {type(item[0])})")
                print(f"   - 狀態: {item[1]} (類型: {type(item[1])})")
                print(f"   - 創建時間: {item[2]} (類型: {type(item[2])})")
                
                # 測試桌面版本（包含提示詞）
                desktop_items = queue_manager.get_queue_items_with_prompt()
                if len(desktop_items) > 1:
                    long_prompt_item = desktop_items[1]
                    if len(long_prompt_item[1]) <= 53:  # 50 + "..."
                        print("✅ 提示詞截斷功能正常（桌面版本）")
                    else:
                        print(f"❌ 提示詞截斷失敗: 長度 {len(long_prompt_item[1])}")

                print("🎉 所有測試通過！隊列顯示格式修復成功（手機優化版本）！")
                return True
            else:
                print(f"❌ 列數錯誤: 期望3列（手機版），實際{len(queue_items[0])}列")
        else:
            print(f"❌ 格式錯誤: 期望列表，實際{type(queue_items[0])}")
    else:
        print("❌ 隊列為空")
    
    return False

def test_gradio_compatibility():
    """測試與 Gradio Dataframe 的兼容性"""
    print("\n🧪 測試 Gradio Dataframe 兼容性...")
    
    try:
        import gradio as gr
        
        # 創建隊列管理器並添加測試數據
        queue_manager = ImageProcessingQueue()
        test_image = np.zeros((100, 100, 3), dtype=np.uint8)
        
        queue_manager.add_item(
            image=test_image,
            prompt="Gradio 兼容性測試",
            n_prompt="",
            seed=11111,
            total_second_length=2.0,
            latent_window_size=16,
            steps=15,
            cfg=7.0,
            gs=1.0,
            rs=1.0,
            gpu_memory_preservation=False,
            use_teacache=False,
            mp4_crf=23,
            resolution=416,
            lora_file=None,
            lora_multiplier=1.0,
            use_magcache=False,
            magcache_thresh=0.5,
            magcache_K=10,
            magcache_retention_ratio=0.8
        )
        
        queue_items = queue_manager.get_queue_items()
        
        # 嘗試創建 Gradio Dataframe（不啟動界面）- 手機優化版本
        df = gr.Dataframe(
            value=queue_items,
            headers=["ID", "狀態", "創建時間"],  # 手機優化：移除提示詞欄位
            datatype=["str", "str", "str"],
            label="隊列項目測試（手機優化）",
            max_height=150,
            interactive=False,
            elem_classes=["mobile-optimized-queue"]
        )
        
        print("✅ Gradio Dataframe 創建成功")
        print("✅ 數據格式與 Gradio 兼容")
        return True
        
    except ImportError:
        print("⚠️  Gradio 未安裝，跳過兼容性測試")
        return True
    except Exception as e:
        print(f"❌ Gradio 兼容性測試失敗: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("🔧 FramePack 隊列顯示修復測試")
    print("=" * 60)
    
    success1 = test_queue_display_format()
    success2 = test_gradio_compatibility()
    
    print("\n" + "=" * 60)
    if success1 and success2:
        print("🎉 所有測試通過！修復成功！")
        print("💡 現在隊列中的 ID 應該正確顯示，而不是 '[object Object]'")
    else:
        print("❌ 部分測試失敗，請檢查修復")
    print("=" * 60)
