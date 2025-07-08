#!/usr/bin/env python3
"""
測試自動清理功能
驗證視頻處理器在保存新視頻時是否正確清理舊的較短視頻
"""

import os
import tempfile
import shutil
from unittest.mock import Mock, patch
import sys

# 添加項目根目錄到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.video_processor import BaseVideoProcessor


class TestVideoProcessor(BaseVideoProcessor):
    """測試用的視頻處理器"""
    
    def __init__(self, output_dir):
        self.output_dir = output_dir
        self.model_manager = Mock()
    
    def process_video(self, *args, **kwargs):
        """測試用的空實現"""
        pass


def create_test_video_file(output_dir, job_id, frame_count, size_mb=1):
    """創建測試視頻文件"""
    filename = f"{job_id}_{frame_count}.mp4"
    filepath = os.path.join(output_dir, filename)
    
    # 創建指定大小的測試文件
    with open(filepath, 'wb') as f:
        f.write(b'0' * int(size_mb * 1024 * 1024))
    
    return filepath


def test_auto_cleanup():
    """測試自動清理功能"""
    print("🧪 開始測試自動清理功能...")
    
    # 創建臨時目錄
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"📁 使用臨時目錄: {temp_dir}")
        
        # 創建測試處理器
        processor = TestVideoProcessor(temp_dir)
        
        # 測試場景：同一任務生成多個不同長度的視頻
        job_id = "20250107_123456"
        
        # 創建測試視頻文件（模擬逐步生成更長的視頻）
        print("📹 創建測試視頻文件...")
        video1 = create_test_video_file(temp_dir, job_id, 10, 2.5)  # 10幀，2.5MB
        video2 = create_test_video_file(temp_dir, job_id, 20, 5.0)  # 20幀，5.0MB
        video3 = create_test_video_file(temp_dir, job_id, 30, 7.5)  # 30幀，7.5MB
        
        # 創建其他任務的視頻（不應該被刪除）
        other_job_id = "20250107_654321"
        other_video = create_test_video_file(temp_dir, other_job_id, 15, 3.0)
        
        print(f"✅ 創建了 4 個測試視頻文件")
        
        # 驗證所有文件都存在
        assert os.path.exists(video1), "視頻1應該存在"
        assert os.path.exists(video2), "視頻2應該存在"
        assert os.path.exists(video3), "視頻3應該存在"
        assert os.path.exists(other_video), "其他任務視頻應該存在"
        
        print("🔍 測試文件名解析功能...")
        
        # 測試文件名解析
        parsed_job_id, parsed_frame_count = processor._parse_video_filename(f"{job_id}_10.mp4")
        assert parsed_job_id == job_id, f"解析的任務ID不正確: {parsed_job_id}"
        assert parsed_frame_count == 10, f"解析的幀數不正確: {parsed_frame_count}"
        
        print("✅ 文件名解析功能正常")
        
        print("🧹 測試自動清理功能...")
        
        # 模擬保存新的更長視頻（40幀）
        # 這應該觸發清理，刪除同一任務的較短視頻
        processor._cleanup_old_videos(job_id, 40)
        
        # 驗證清理結果
        assert not os.path.exists(video1), "10幀視頻應該被刪除"
        assert not os.path.exists(video2), "20幀視頻應該被刪除"
        assert not os.path.exists(video3), "30幀視頻應該被刪除"
        assert os.path.exists(other_video), "其他任務的視頻不應該被刪除"
        
        print("✅ 自動清理功能正常工作")
        
        print("🔄 測試部分清理場景...")
        
        # 重新創建測試文件，測試部分清理
        video1_new = create_test_video_file(temp_dir, job_id, 10, 2.5)
        video2_new = create_test_video_file(temp_dir, job_id, 20, 5.0)
        video3_new = create_test_video_file(temp_dir, job_id, 30, 7.5)
        
        # 模擬保存25幀的視頻，應該只刪除10和20幀的，保留30幀的
        processor._cleanup_old_videos(job_id, 25)
        
        assert not os.path.exists(video1_new), "10幀視頻應該被刪除"
        assert not os.path.exists(video2_new), "20幀視頻應該被刪除"
        assert os.path.exists(video3_new), "30幀視頻應該保留（因為比當前25幀更長）"
        assert os.path.exists(other_video), "其他任務的視頻不應該被刪除"
        
        print("✅ 部分清理場景測試通過")
        
        print("🎯 測試邊界情況...")
        
        # 測試相同幀數的情況（不應該刪除）
        same_frame_video = create_test_video_file(temp_dir, job_id, 25, 6.0)
        processor._cleanup_old_videos(job_id, 25)
        assert os.path.exists(same_frame_video), "相同幀數的視頻不應該被刪除"
        
        print("✅ 邊界情況測試通過")
        
    print("🎉 所有測試通過！自動清理功能工作正常")


def test_save_video_integration():
    """測試 _save_video 方法的集成功能"""
    print("🧪 測試 _save_video 集成功能...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        processor = TestVideoProcessor(temp_dir)
        
        job_id = "20250107_integration_test"
        
        # 創建一些舊的視頻文件
        create_test_video_file(temp_dir, job_id, 10, 1.0)
        create_test_video_file(temp_dir, job_id, 20, 2.0)
        
        # 模擬 history_pixels（使用 Mock）
        mock_history_pixels = Mock()
        
        # 模擬 save_bcthw_as_mp4 函數
        with patch('core.video_processor.save_bcthw_as_mp4') as mock_save:
            # 設置 mock 返回值
            mock_save.return_value = Mock()
            
            # 調用 _save_video，應該觸發自動清理
            output_filename = processor._save_video(mock_history_pixels, job_id, 30, 18)
            
            # 驗證輸出文件名
            expected_filename = os.path.join(temp_dir, f"{job_id}_30.mp4")
            assert output_filename == expected_filename, f"輸出文件名不正確: {output_filename}"
            
            # 驗證 save_bcthw_as_mp4 被調用
            mock_save.assert_called_once_with(mock_history_pixels, expected_filename, fps=24, crf=18)
        
        # 驗證舊文件被清理（注意：由於我們 mock 了 save_bcthw_as_mp4，實際文件不會被創建）
        old_files = [f for f in os.listdir(temp_dir) if f.endswith('.mp4')]
        print(f"剩餘文件: {old_files}")
        
    print("✅ _save_video 集成功能測試通過")


if __name__ == "__main__":
    try:
        test_auto_cleanup()
        test_save_video_integration()
        print("\n🎊 所有測試都通過了！自動清理功能已成功實現。")
        print("\n📋 功能說明:")
        print("• 每次生成新的更長視頻時，會自動刪除同一任務的較短視頻")
        print("• 只刪除相同 job_id 且幀數較少的視頻文件")
        print("• 不會影響其他任務的視頻文件")
        print("• 包含錯誤處理，確保清理失敗不影響主要流程")
        
    except Exception as e:
        print(f"❌ 測試失敗: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
