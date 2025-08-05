#!/usr/bin/env python3
"""
測試真實場景的隊列處理修復
模擬實際的 FramePack 使用情況
"""
import time
import threading
import numpy as np
from diffusers_helper.thread_utils import Listener, AsyncStream, async_run
from core.queue_manager import ImageProcessingQueue


class MockVideoProcessor:
    """模擬視頻處理器"""
    
    def __init__(self):
        self.stop_requested = False
    
    def process_video(self, stream, item_id, steps=10):
        """模擬視頻處理過程"""
        print(f"🎬 開始處理視頻 {item_id}")
        
        try:
            for i in range(steps):
                # 檢查是否需要停止
                if stream.input_queue.top() == 'end':
                    print(f"⏹️ 收到停止信號，中斷處理 {item_id}")
                    stream.output_queue.push(('end', None))
                    raise KeyboardInterrupt('User ends the task.')
                
                # 模擬處理進度
                time.sleep(0.3)
                progress = int(100 * (i + 1) / steps)
                stream.output_queue.push(('progress', f"處理進度: {progress}%"))
                print(f"📊 {item_id} 進度: {progress}%")
            
            # 處理完成
            output_file = f"output_{item_id}.mp4"
            stream.output_queue.push(('file', output_file))
            print(f"✅ {item_id} 處理完成: {output_file}")
            
        except KeyboardInterrupt as e:
            print(f"⚠️ {item_id} 被用戶中斷: {e}")
            raise
        except Exception as e:
            print(f"❌ {item_id} 處理失敗: {e}")
            raise
        finally:
            stream.output_queue.push(('end', None))


def simulate_queue_processing():
    """模擬隊列處理"""
    print("🚀 開始模擬隊列處理...")
    
    # 創建隊列管理器
    queue_manager = ImageProcessingQueue(gpu_id="0", shared_queue=False)
    processor = MockVideoProcessor()
    is_processing = True
    
    # 添加測試項目
    test_image = np.random.randint(0, 255, (512, 512, 3), dtype=np.uint8)
    
    item_ids = []
    for i in range(3):
        item_id = queue_manager.add_item(
            image=test_image,
            prompt=f"test prompt {i+1}",
            n_prompt="",
            seed=42 + i,
            total_second_length=3,
            latent_window_size=16,
            steps=20,
            cfg=7.5,
            gs=6.0,
            rs=1.0,
            gpu_memory_preservation=False,
            use_teacache=False,
            mp4_crf=23,
            resolution=416,
            lora_file=None,
            lora_multiplier=1.0,
            use_magcache=False,
            magcache_thresh=0.1,
            magcache_K=3,
            magcache_retention_ratio=0.2
        )
        item_ids.append(item_id)
        print(f"📝 添加項目: {item_id}")
    
    def process_queue():
        """處理隊列的工作函數"""
        nonlocal is_processing
        
        while is_processing and not queue_manager.is_empty():
            # 獲取下一個項目
            item = queue_manager.get_next_item()
            if item is None:
                break
            
            try:
                # 創建 stream
                stream = AsyncStream()
                
                # 處理項目
                processor.process_video(stream, item.id, steps=5)
                
                # 等待處理完成
                output_filename = None
                while True:
                    if not is_processing:
                        queue_manager.fail_item(item.id, "Processing stopped by user")
                        break
                    
                    flag, data = stream.output_queue.next()
                    
                    if flag == 'file':
                        output_filename = data
                    elif flag == 'progress':
                        print(f"📈 {data}")
                    elif flag == 'end':
                        break
                
                # 標記完成
                if is_processing and output_filename:
                    queue_manager.complete_item(item.id, output_filename)
                    print(f"✅ 項目 {item.id} 處理完成")
                
            except KeyboardInterrupt:
                queue_manager.fail_item(item.id, "Interrupted by user")
                print(f"⚠️ 項目 {item.id} 被中斷")
                break
            except Exception as e:
                queue_manager.fail_item(item.id, str(e))
                print(f"❌ 項目 {item.id} 處理失敗: {e}")
        
        is_processing = False
        print("🏁 隊列處理結束")
    
    # 開始異步處理
    async_run(process_queue)
    
    # 等待一段時間後停止
    time.sleep(3)
    
    print("\n🛑 模擬用戶停止處理...")
    is_processing = False
    Listener.stop_all_tasks()
    queue_manager.reset_processing_items()
    
    # 檢查最終狀態
    time.sleep(1)
    status = queue_manager.get_queue_status()
    print(f"📊 最終隊列狀態: {status}")
    
    return queue_manager


def test_restart_scenario():
    """測試重啟場景"""
    print("\n🔄 測試重啟場景...")
    
    # 第一次運行，模擬程式崩潰
    print("1️⃣ 第一次運行（模擬崩潰）...")
    queue_manager1 = simulate_queue_processing()
    
    # 模擬重啟
    print("\n2️⃣ 模擬程式重啟...")
    queue_manager2 = ImageProcessingQueue(gpu_id="0", shared_queue=False)
    
    # 在真實場景中，這裡會從持久化存儲加載隊列
    # 我們手動設置一些處理中的項目來模擬
    test_image = np.random.randint(0, 255, (512, 512, 3), dtype=np.uint8)
    item_id = queue_manager2.add_item(
        image=test_image, prompt="restart test", n_prompt="", seed=42,
        total_second_length=3, latent_window_size=16, steps=20, cfg=7.5,
        gs=6.0, rs=1.0, gpu_memory_preservation=False, use_teacache=False,
        mp4_crf=23, resolution=416, lora_file=None, lora_multiplier=1.0,
        use_magcache=False, magcache_thresh=0.1, magcache_K=3,
        magcache_retention_ratio=0.2
    )
    
    # 模擬項目正在處理中
    item = queue_manager2.get_next_item()
    print(f"📋 重啟前狀態 - 項目 {item.id}: {item.status}")
    
    # 重置處理中的項目（這是修復的關鍵）
    print("🔧 重置處理中的項目...")
    queue_manager2.reset_processing_items()
    
    status = queue_manager2.get_queue_status()
    print(f"✅ 重置後狀態: {status}")
    
    print("✅ 重啟場景測試完成")


if __name__ == "__main__":
    print("🧪 開始真實場景測試...\n")
    
    try:
        # 測試隊列處理和停止
        simulate_queue_processing()
        
        # 等待清理
        time.sleep(1)
        
        # 測試重啟場景
        test_restart_scenario()
        
        print("\n🎉 真實場景測試完成！")
        
    except Exception as e:
        print(f"\n❌ 測試過程中發生錯誤: {e}")
        import traceback
        traceback.print_exc()
