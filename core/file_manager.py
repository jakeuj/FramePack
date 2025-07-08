"""
文件管理模組
負責處理輸出文件的管理、清理和下載功能
"""
import os
import glob
import zipfile
import tempfile
from datetime import datetime
from typing import List, Tuple, Dict, Optional
import gradio as gr


class FileManager:
    """文件管理類"""
    
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        
    def get_output_videos(self) -> Tuple:
        """獲取輸出文件夾中的所有MP4文件"""
        mp4_files = glob.glob(os.path.join(self.output_dir, "*.mp4"))
        if not mp4_files:
            return (
                "沒有找到任何視頻文件", 
                gr.update(choices=[], value=None, visible=False), 
                gr.update(visible=False),  # preview_btn
                gr.update(visible=False),  # download_btn
                gr.update(visible=False)   # preview_video
            )
        
        # 按修改時間排序，最新的在前
        mp4_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        
        # 創建文件信息列表
        file_info = []
        file_choices = []
        for file_path in mp4_files:
            filename = os.path.basename(file_path)
            file_size = os.path.getsize(file_path) / (1024 * 1024)  # MB
            mod_time = datetime.fromtimestamp(os.path.getmtime(file_path)).strftime("%Y-%m-%d %H:%M:%S")
            file_info.append(f"📹 {filename} ({file_size:.1f}MB) - {mod_time}")
            file_choices.append(file_path)
        
        file_list_text = "\n".join(file_info)
        return (
            file_list_text, 
            gr.update(choices=file_choices, value=file_choices[0] if file_choices else None, visible=True), 
            gr.update(visible=True),   # preview_btn
            gr.update(visible=True),   # download_btn
            gr.update(visible=False)   # preview_video (隱藏直到用戶點擊預覽)
        )
    
    def download_selected_video(self, selected_file: Optional[str]) -> Tuple:
        """處理視頻文件下載"""
        if selected_file is None:
            return None, gr.update(visible=False)
        return selected_file, gr.update(visible=True)

    def download_all_videos(self) -> Tuple:
        """批量下載所有視頻文件為ZIP"""
        mp4_files = glob.glob(os.path.join(self.output_dir, "*.mp4"))

        if not mp4_files:
            return None, gr.update(visible=False)

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

            return zip_path, gr.update(visible=True)

        except Exception as e:
            print(f"創建ZIP文件時發生錯誤: {str(e)}")
            return None, gr.update(visible=False)
    
    def parse_video_filename(self, filename: str) -> Tuple[Optional[str], Optional[int]]:
        """解析視頻文件名，提取任務ID和幀數信息"""
        try:
            # 移除.mp4擴展名
            name_without_ext = filename.replace('.mp4', '')
            # 分割文件名，格式假設為: timestamp_jobid_framecount
            parts = name_without_ext.split('_')
            if len(parts) >= 3:
                # 最後一個數字是幀數
                frame_count = int(parts[-1])
                # 前面的部分是任務標識符
                job_id = '_'.join(parts[:-1])
                return job_id, frame_count
            return None, None
        except:
            return None, None
    
    def get_cleanup_preview(self) -> Tuple[str, gr.update]:
        """獲取清理預覽信息"""
        mp4_files = glob.glob(os.path.join(self.output_dir, "*.mp4"))
        if not mp4_files:
            return "沒有找到任何視頻文件", gr.update(visible=False)
        
        # 按任務分組
        job_groups = {}
        for file_path in mp4_files:
            filename = os.path.basename(file_path)
            job_id, frame_count = self.parse_video_filename(filename)
            
            if job_id and frame_count is not None:
                if job_id not in job_groups:
                    job_groups[job_id] = []
                job_groups[job_id].append((file_path, frame_count, filename))
        
        if not job_groups:
            return "沒有找到有效的視頻文件", gr.update(visible=False)
        
        # 生成清理預覽
        preview_info = []
        total_to_delete = 0
        total_size_to_free = 0
        
        for job_id, files in job_groups.items():
            if len(files) <= 1:
                continue  # 只有一個文件的任務不需要清理
            
            # 按幀數排序，幀數最大的是最新最長的
            files.sort(key=lambda x: x[1], reverse=True)
            latest_file = files[0]
            files_to_delete = files[1:]
            
            preview_info.append(f"📂 任務: {job_id}")
            preview_info.append(f"  ✅ 保留: {latest_file[2]} ({latest_file[1]} 幀)")
            
            for file_path, frame_count, filename in files_to_delete:
                file_size = os.path.getsize(file_path) / (1024 * 1024)  # MB
                preview_info.append(f"  ❌ 刪除: {filename} ({frame_count} 幀, {file_size:.1f}MB)")
                total_to_delete += 1
                total_size_to_free += file_size
            
            preview_info.append("")  # 空行分隔
        
        if total_to_delete == 0:
            return "沒有需要清理的文件（每個任務都只有一個視頻文件）", gr.update(visible=False)
        
        summary = f"總計將刪除 {total_to_delete} 個文件，釋放約 {total_size_to_free:.1f}MB 空間\n\n"
        preview_text = summary + "\n".join(preview_info)
        
        return preview_text, gr.update(visible=True)
    
    def cleanup_videos(self) -> Tuple[str, str]:
        """執行視頻清理"""
        mp4_files = glob.glob(os.path.join(self.output_dir, "*.mp4"))
        if not mp4_files:
            return "沒有找到任何視頻文件", "❌ 清理失敗"
        
        # 按任務分組
        job_groups = {}
        for file_path in mp4_files:
            filename = os.path.basename(file_path)
            job_id, frame_count = self.parse_video_filename(filename)
            
            if job_id and frame_count is not None:
                if job_id not in job_groups:
                    job_groups[job_id] = []
                job_groups[job_id].append((file_path, frame_count, filename))
        
        if not job_groups:
            return "沒有找到有效的視頻文件", "❌ 清理失敗"
        
        # 執行清理
        deleted_count = 0
        deleted_size = 0
        result_info = []
        
        try:
            for job_id, files in job_groups.items():
                if len(files) <= 1:
                    continue  # 只有一個文件的任務不需要清理
                
                # 按幀數排序，幀數最大的是最新最長的
                files.sort(key=lambda x: x[1], reverse=True)
                latest_file = files[0]
                files_to_delete = files[1:]
                
                result_info.append(f"📂 任務: {job_id}")
                result_info.append(f"  ✅ 保留: {latest_file[2]}")
                
                for file_path, frame_count, filename in files_to_delete:
                    try:
                        file_size = os.path.getsize(file_path) / (1024 * 1024)  # MB
                        os.remove(file_path)
                        result_info.append(f"  ✅ 已刪除: {filename} ({file_size:.1f}MB)")
                        deleted_count += 1
                        deleted_size += file_size
                    except Exception as e:
                        result_info.append(f"  ❌ 刪除失敗: {filename} - {str(e)}")
                
                result_info.append("")  # 空行分隔
            
            if deleted_count == 0:
                return "沒有需要清理的文件", "ℹ️ 無需清理"
            
            summary = f"✅ 清理完成！共刪除 {deleted_count} 個文件，釋放了 {deleted_size:.1f}MB 空間\n\n"
            result_text = summary + "\n".join(result_info)
            
            return result_text, "✅ 清理成功"
            
        except Exception as e:
            return f"清理過程中發生錯誤: {str(e)}", "❌ 清理失敗"
    
    def get_all_files_preview(self) -> Tuple[str, gr.update]:
        """獲取所有文件的刪除預覽"""
        # 支持的文件類型
        file_patterns = ["*.mp4", "*.png", "*.jpg", "*.jpeg", "*.gif", "*.bmp", "*.tiff", "*.webp"]
        
        all_files = []
        for pattern in file_patterns:
            all_files.extend(glob.glob(os.path.join(self.output_dir, pattern)))
        
        if not all_files:
            return "輸出文件夾中沒有找到任何文件", gr.update(visible=False)
        
        # 按文件類型分組統計
        file_stats = {}
        total_size = 0
        
        for file_path in all_files:
            filename = os.path.basename(file_path)
            file_ext = os.path.splitext(filename)[1].lower()
            file_size = os.path.getsize(file_path) / (1024 * 1024)  # MB
            
            if file_ext not in file_stats:
                file_stats[file_ext] = {"count": 0, "size": 0, "files": []}
            
            file_stats[file_ext]["count"] += 1
            file_stats[file_ext]["size"] += file_size
            file_stats[file_ext]["files"].append((filename, file_size))
            total_size += file_size
        
        # 生成預覽信息
        preview_info = []
        preview_info.append("⚠️ 警告：此操作將刪除輸出文件夾中的所有文件！")
        preview_info.append(f"📊 總計: {len(all_files)} 個文件，約 {total_size:.1f}MB")
        preview_info.append("")
        
        for file_ext, stats in sorted(file_stats.items()):
            preview_info.append(f"📄 {file_ext.upper() if file_ext else '無擴展名'} 文件: {stats['count']} 個，{stats['size']:.1f}MB")
            
            # 顯示文件列表（如果文件太多只顯示前10個）
            files_to_show = stats['files'][:10]
            for filename, file_size in files_to_show:
                preview_info.append(f"   • {filename} ({file_size:.1f}MB)")
            
            if len(stats['files']) > 10:
                preview_info.append(f"   ... 還有 {len(stats['files']) - 10} 個文件")
            
            preview_info.append("")
        
        preview_text = "\n".join(preview_info)
        return preview_text, gr.update(visible=True)
    
    def delete_all_files(self) -> Tuple[str, str]:
        """刪除所有文件"""
        # 支持的文件類型
        file_patterns = ["*.mp4", "*.png", "*.jpg", "*.jpeg", "*.gif", "*.bmp", "*.tiff", "*.webp"]
        
        all_files = []
        for pattern in file_patterns:
            all_files.extend(glob.glob(os.path.join(self.output_dir, pattern)))
        
        if not all_files:
            return "輸出文件夾中沒有找到任何文件", "ℹ️ 無文件可刪除"
        
        # 執行刪除
        deleted_count = 0
        failed_count = 0
        total_size_freed = 0
        result_info = []
        
        try:
            result_info.append("🗑️ 開始刪除所有文件...")
            result_info.append("")
            
            for file_path in all_files:
                filename = os.path.basename(file_path)
                try:
                    file_size = os.path.getsize(file_path) / (1024 * 1024)  # MB
                    os.remove(file_path)
                    result_info.append(f"✅ 已刪除: {filename} ({file_size:.1f}MB)")
                    deleted_count += 1
                    total_size_freed += file_size
                except Exception as e:
                    result_info.append(f"❌ 刪除失敗: {filename} - {str(e)}")
                    failed_count += 1
            
            result_info.append("")
            
            if deleted_count > 0:
                summary = f"✅ 刪除完成！\n"
                summary += f"• 成功刪除: {deleted_count} 個文件\n"
                if failed_count > 0:
                    summary += f"• 刪除失敗: {failed_count} 個文件\n"
                summary += f"• 釋放空間: {total_size_freed:.1f}MB\n\n"
                
                result_text = summary + "\n".join(result_info)
                status = "✅ 刪除完成"
            else:
                result_text = "❌ 沒有成功刪除任何文件\n\n" + "\n".join(result_info)
                status = "❌ 刪除失敗"
            
            return result_text, status
            
        except Exception as e:
            return f"刪除過程中發生嚴重錯誤: {str(e)}", "❌ 刪除失敗"
