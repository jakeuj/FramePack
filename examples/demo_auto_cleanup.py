#!/usr/bin/env python3
"""
自動清理功能演示
展示圖生影過程中如何自動清理舊的較短視頻文件
"""

import os
import sys
import tempfile
import time
from unittest.mock import Mock

# 添加項目根目錄到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.video_processor import BaseVideoProcessor


class DemoVideoProcessor(BaseVideoProcessor):
    """演示用的視頻處理器"""
    
    def __init__(self, output_dir):
        self.output_dir = output_dir
        self.model_manager = Mock()
    
    def process_video(self, *args, **kwargs):
        """演示用的空實現"""
        pass


def create_demo_video_file(output_dir, job_id, frame_count, size_mb=1):
    """創建演示視頻文件"""
    filename = f"{job_id}_{frame_count}.mp4"
    filepath = os.path.join(output_dir, filename)
    
    # 創建指定大小的演示文件
    with open(filepath, 'wb') as f:
        f.write(b'DEMO_VIDEO_DATA' * int(size_mb * 1024 * 1024 // 15))
    
    return filepath


def list_videos(output_dir, title="當前視頻文件"):
    """列出目錄中的視頻文件"""
    print(f"\n📁 {title}:")
    mp4_files = [f for f in os.listdir(output_dir) if f.endswith('.mp4')]
    
    if not mp4_files:
        print("   (無視頻文件)")
        return
    
    # 按文件名排序
    mp4_files.sort()
    
    total_size = 0
    for filename in mp4_files:
        filepath = os.path.join(output_dir, filename)
        size_mb = os.path.getsize(filepath) / (1024 * 1024)
        total_size += size_mb
        print(f"   📹 {filename} ({size_mb:.1f}MB)")
    
    print(f"   💾 總大小: {total_size:.1f}MB")


def demo_auto_cleanup():
    """演示自動清理功能"""
    print("🎬 FramePack 自動清理功能演示")
    print("=" * 50)
    
    # 創建臨時演示目錄
    with tempfile.TemporaryDirectory() as demo_dir:
        print(f"📁 演示目錄: {demo_dir}")
        
        # 創建演示處理器
        processor = DemoVideoProcessor(demo_dir)
        
        # 模擬圖生影過程
        job_id = "demo_20250107_123456"
        
        print("\n🎯 模擬圖生影過程...")
        print("假設用戶要求生成 10 秒的視頻，系統會逐步生成更長的視頻")
        
        # 第一步：生成 2 秒視頻 (約 48 幀)
        print("\n⏱️  第1步：生成 2 秒視頻...")
        create_demo_video_file(demo_dir, job_id, 48, 3.2)
        list_videos(demo_dir, "生成 2 秒視頻後")
        time.sleep(1)
        
        # 第二步：擴展到 4 秒視頻 (約 96 幀)
        print("\n⏱️  第2步：擴展到 4 秒視頻...")
        create_demo_video_file(demo_dir, job_id, 96, 6.4)
        
        # 觸發自動清理
        print("🧹 觸發自動清理...")
        processor._cleanup_old_videos(job_id, 96)
        list_videos(demo_dir, "擴展到 4 秒後（自動清理了 2 秒視頻）")
        time.sleep(1)
        
        # 第三步：擴展到 6 秒視頻 (約 144 幀)
        print("\n⏱️  第3步：擴展到 6 秒視頻...")
        create_demo_video_file(demo_dir, job_id, 144, 9.6)
        
        # 觸發自動清理
        print("🧹 觸發自動清理...")
        processor._cleanup_old_videos(job_id, 144)
        list_videos(demo_dir, "擴展到 6 秒後（自動清理了 4 秒視頻）")
        time.sleep(1)
        
        # 第四步：擴展到 8 秒視頻 (約 192 幀)
        print("\n⏱️  第4步：擴展到 8 秒視頻...")
        create_demo_video_file(demo_dir, job_id, 192, 12.8)
        
        # 觸發自動清理
        print("🧹 觸發自動清理...")
        processor._cleanup_old_videos(job_id, 192)
        list_videos(demo_dir, "擴展到 8 秒後（自動清理了 6 秒視頻）")
        time.sleep(1)
        
        # 最終步：完成 10 秒視頻 (約 240 幀)
        print("\n⏱️  最終步：完成 10 秒視頻...")
        create_demo_video_file(demo_dir, job_id, 240, 16.0)
        
        # 觸發自動清理
        print("🧹 觸發自動清理...")
        processor._cleanup_old_videos(job_id, 240)
        list_videos(demo_dir, "完成 10 秒視頻後（只保留最終版本）")
        
        print("\n" + "=" * 50)
        print("✨ 演示完成！")
        print("\n📊 效果總結:")
        print("• 在沒有自動清理的情況下，會產生 5 個視頻文件，總大小約 47.2MB")
        print("• 使用自動清理後，只保留最終的 10 秒視頻，大小 16.0MB")
        print("• 節省了約 31.2MB 的存儲空間 (66% 的空間節省)")
        print("\n🎯 功能特點:")
        print("• 自動清理：每次生成更長視頻時自動刪除較短版本")
        print("• 安全性：只刪除同一任務的文件，不影響其他任務")
        print("• 透明性：清理過程會在控制台顯示詳細信息")
        print("• 容錯性：清理失敗不會影響視頻生成主流程")
        
        # 演示多任務場景
        print("\n🔄 演示多任務場景...")
        
        # 創建另一個任務的視頻
        other_job_id = "demo_20250107_654321"
        create_demo_video_file(demo_dir, other_job_id, 72, 4.8)  # 3秒視頻
        create_demo_video_file(demo_dir, other_job_id, 120, 8.0)  # 5秒視頻
        
        list_videos(demo_dir, "添加第二個任務的視頻後")
        
        # 清理第二個任務的舊視頻
        print("🧹 清理第二個任務的舊視頻...")
        processor._cleanup_old_videos(other_job_id, 120)
        
        list_videos(demo_dir, "清理第二個任務後")
        
        print("\n✅ 多任務演示完成！可以看到兩個任務的視頻互不影響。")


if __name__ == "__main__":
    try:
        demo_auto_cleanup()
    except KeyboardInterrupt:
        print("\n\n⏹️  演示被用戶中斷")
    except Exception as e:
        print(f"\n❌ 演示過程中發生錯誤: {str(e)}")
        import traceback
        traceback.print_exc()
