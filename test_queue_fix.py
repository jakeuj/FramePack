#!/usr/bin/env python3
"""
測試隊列修復功能
"""
import time
import threading
from diffusers_helper.thread_utils import Listener, async_run
from core.queue_manager import ImageProcessingQueue


def test_listener_stop():
    """測試 Listener 停止功能"""
    print("🧪 測試 Listener 停止功能...")

    task_stopped = threading.Event()

    def long_running_task(task_id):
        print(f"開始任務 {task_id}")
        try:
            for i in range(10):
                # 檢查是否需要停止
                if Listener.stop_event.is_set():
                    print(f"任務 {task_id} 被停止")
                    task_stopped.set()
                    return
                time.sleep(0.5)
                print(f"任務 {task_id} 進度: {i+1}/10")
            print(f"任務 {task_id} 完成")
        except Exception as e:
            print(f"任務 {task_id} 異常: {e}")
            task_stopped.set()

    # 添加一些任務
    async_run(long_running_task, "Task1")
    async_run(long_running_task, "Task2")
    async_run(long_running_task, "Task3")

    # 等待一段時間
    time.sleep(2)

    # 停止所有任務
    print("🛑 停止所有任務...")
    Listener.stop_all_tasks()

    # 等待任務停止
    if task_stopped.wait(timeout=3):
        print("✅ 任務成功停止")
    else:
        print("⚠️ 任務可能沒有及時停止")

    print("✅ Listener 停止測試完成")


def test_queue_reset():
    """測試隊列重置功能"""
    print("\n🧪 測試隊列重置功能...")
    
    # 創建隊列管理器
    queue_manager = ImageProcessingQueue(gpu_id="0", shared_queue=False)
    
    # 添加一些測試項目
    import numpy as np
    test_image = np.random.randint(0, 255, (512, 512, 3), dtype=np.uint8)
    
    item_id = queue_manager.add_item(
        image=test_image,
        prompt="test prompt",
        n_prompt="",
        seed=42,
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
    
    print(f"添加項目: {item_id}")
    
    # 獲取項目（模擬開始處理）
    item = queue_manager.get_next_item()
    print(f"開始處理項目: {item.id}, 狀態: {item.status}")
    
    # 重置處理中的項目
    print("🔄 重置處理中的項目...")
    queue_manager.reset_processing_items()
    
    # 檢查狀態
    status = queue_manager.get_queue_status()
    print(f"重置後隊列狀態: {status}")
    
    # 清空隊列
    queue_manager.clear_all()
    print("✅ 隊列重置測試完成")


def test_keyboard_interrupt_handling():
    """測試 KeyboardInterrupt 處理"""
    print("\n🧪 測試 KeyboardInterrupt 處理...")
    
    def task_with_interrupt():
        try:
            for i in range(5):
                time.sleep(0.5)
                print(f"任務進度: {i+1}/5")
                if i == 2:  # 模擬中斷
                    raise KeyboardInterrupt("模擬用戶中斷")
        except KeyboardInterrupt as e:
            print(f"捕獲到中斷: {e}")
            raise
    
    try:
        async_run(task_with_interrupt)
        time.sleep(3)
    except Exception as e:
        print(f"異常處理: {e}")
    
    print("✅ KeyboardInterrupt 處理測試完成")


if __name__ == "__main__":
    print("🚀 開始測試隊列修復功能...\n")
    
    try:
        # 測試 Listener 停止功能
        test_listener_stop()
        
        # 等待一段時間確保線程清理
        time.sleep(1)
        
        # 測試隊列重置功能
        test_queue_reset()
        
        # 測試 KeyboardInterrupt 處理
        test_keyboard_interrupt_handling()
        
        print("\n🎉 所有測試完成！")
        
    except Exception as e:
        print(f"\n❌ 測試過程中發生錯誤: {e}")
        import traceback
        traceback.print_exc()
