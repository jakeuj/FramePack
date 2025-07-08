#!/usr/bin/env python3
"""
簡化的手機端優化測試
"""

import os
import sys
import tempfile
import zipfile
import time
import threading
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

# 模擬QueueItem類
@dataclass
class QueueItem:
    id: str
    image_path: str
    prompt: str
    resolution: int
    status: str = "waiting"
    created_at: float = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()

# 模擬ImageProcessingQueue類的核心方法
class MockImageProcessingQueue:
    def __init__(self):
        self.queue: List[QueueItem] = []
        self.lock = threading.Lock()
        self.current_processing: Optional[QueueItem] = None
    
    def add_item(self, image_path: str, prompt: str, resolution: int) -> str:
        """添加項目到隊列"""
        item_id = f"item_{len(self.queue) + 1}_{int(time.time())}"
        item = QueueItem(
            id=item_id,
            image_path=image_path,
            prompt=prompt,
            resolution=resolution
        )
        with self.lock:
            self.queue.append(item)
        return item_id
    
    def get_queue_items(self) -> List[List[str]]:
        """獲取隊列項目列表（用於顯示）- 手機優化版本，不顯示提示詞"""
        with self.lock:
            items = []
            for item in self.queue:
                # 返回列表的列表，順序對應 UI 中的 headers: ["ID", "狀態", "創建時間"]
                # 移除提示詞欄位以優化手機排版
                items.append([
                    item.id,
                    item.status,
                    time.strftime("%H:%M:%S", time.localtime(item.created_at))
                ])
            return items
    
    def get_queue_items_with_prompt(self) -> List[List[str]]:
        """獲取包含提示詞的隊列項目列表（用於桌面端顯示）"""
        with self.lock:
            items = []
            for item in self.queue:
                # 返回列表的列表，順序對應 UI 中的 headers: ["ID", "提示詞", "狀態", "創建時間"]
                items.append([
                    item.id,
                    item.prompt[:50] + "..." if len(item.prompt) > 50 else item.prompt,
                    item.status,
                    time.strftime("%H:%M:%S", time.localtime(item.created_at))
                ])
            return items

# 模擬FileManager類的批量下載方法
class MockFileManager:
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
    
    def download_all_videos(self):
        """批量下載所有視頻文件為ZIP"""
        import glob
        from datetime import datetime
        
        mp4_files = glob.glob(os.path.join(self.output_dir, "*.mp4"))
        
        if not mp4_files:
            return None, {"visible": False}
        
        try:
            # 創建臨時ZIP文件
            temp_dir = tempfile.gettempdir()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            zip_filename = f"framepack_videos_{timestamp}.zip"
            zip_path = os.path.join(temp_dir, zip_filename)
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for mp4_file in mp4_files:
                    # 只保留文件名，不包含完整路徑
                    arcname = os.path.basename(mp4_file)
                    zipf.write(mp4_file, arcname)
            
            return zip_path, {"visible": True}
            
        except Exception as e:
            print(f"創建ZIP文件時發生錯誤: {str(e)}")
            return None, {"visible": False}


def test_queue_mobile_optimization():
    """測試隊列手機端優化"""
    print("🧪 測試隊列手機端優化...")
    
    # 創建隊列管理器
    queue_manager = MockImageProcessingQueue()
    
    # 添加測試項目
    test_image = "test_image.jpg"
    test_prompt = "This is a very long prompt that would normally cause display issues on mobile devices due to its excessive length and would be truncated"
    
    queue_manager.add_item(test_image, test_prompt, 416)
    
    # 測試手機優化版本（不包含提示詞）
    mobile_items = queue_manager.get_queue_items()
    print(f"手機版隊列項目: {mobile_items}")
    
    # 驗證格式
    assert len(mobile_items) == 1
    assert len(mobile_items[0]) == 3  # ID, 狀態, 創建時間
    assert mobile_items[0][1] == "waiting"  # 狀態
    
    # 測試桌面版本（包含提示詞）
    desktop_items = queue_manager.get_queue_items_with_prompt()
    print(f"桌面版隊列項目: {desktop_items}")
    
    # 驗證格式
    assert len(desktop_items) == 1
    assert len(desktop_items[0]) == 4  # ID, 提示詞, 狀態, 創建時間
    assert "very long prompt" in desktop_items[0][1]  # 提示詞被截斷
    assert desktop_items[0][1].endswith("...")  # 確認截斷
    assert desktop_items[0][2] == "waiting"  # 狀態
    
    print("✅ 隊列手機端優化測試通過")


def test_batch_download():
    """測試批量下載功能"""
    print("🧪 測試批量下載功能...")
    
    # 創建臨時目錄和測試文件
    with tempfile.TemporaryDirectory() as temp_dir:
        # 創建測試MP4文件
        test_files = [
            "video1_20241208_120000_24.mp4",
            "video2_20241208_120100_48.mp4",
            "video3_20241208_120200_72.mp4"
        ]
        
        for filename in test_files:
            filepath = os.path.join(temp_dir, filename)
            with open(filepath, 'w') as f:
                f.write(f"Test video content for {filename}")
        
        # 創建文件管理器
        file_manager = MockFileManager(temp_dir)
        
        # 測試批量下載
        zip_path, update_info = file_manager.download_all_videos()
        
        # 驗證ZIP文件創建
        assert zip_path is not None
        assert os.path.exists(zip_path)
        assert zip_path.endswith('.zip')
        
        # 驗證ZIP文件內容
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            zip_contents = zipf.namelist()
            assert len(zip_contents) == 3
            for test_file in test_files:
                assert test_file in zip_contents
        
        print(f"✅ 批量下載測試通過，ZIP文件: {zip_path}")
        
        # 清理
        if os.path.exists(zip_path):
            os.remove(zip_path)


def test_empty_directory_batch_download():
    """測試空目錄的批量下載"""
    print("🧪 測試空目錄批量下載...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        file_manager = MockFileManager(temp_dir)
        
        # 測試空目錄
        zip_path, update_info = file_manager.download_all_videos()
        
        # 驗證返回None
        assert zip_path is None
        
        print("✅ 空目錄批量下載測試通過")


def main():
    """運行所有測試"""
    print("🚀 開始測試手機端優化和批量下載功能...\n")
    
    try:
        test_queue_mobile_optimization()
        print()
        
        test_batch_download()
        print()
        
        test_empty_directory_batch_download()
        print()
        
        print("🎉 所有測試通過！")
        
    except Exception as e:
        print(f"❌ 測試失敗: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
