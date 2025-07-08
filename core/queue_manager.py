"""
圖片處理隊列管理器
負責管理批量圖片上傳和處理隊列
"""
import uuid
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from threading import Lock
import numpy as np


@dataclass
class QueueItem:
    """隊列項目數據類"""
    id: str
    image: np.ndarray
    prompt: str
    n_prompt: str
    seed: int
    total_second_length: float
    latent_window_size: int
    steps: int
    cfg: float
    gs: float
    rs: float
    gpu_memory_preservation: bool
    use_teacache: bool
    mp4_crf: int
    resolution: int
    lora_file: Optional[str]
    lora_multiplier: float
    use_magcache: bool
    magcache_thresh: float
    magcache_K: int
    magcache_retention_ratio: float
    status: str = "waiting"  # waiting, processing, completed, failed
    created_at: float = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    output_file: Optional[str] = None
    error_message: Optional[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()


class ImageProcessingQueue:
    """圖片處理隊列管理器"""
    
    def __init__(self):
        self.queue: List[QueueItem] = []
        self.lock = Lock()
        self.current_processing: Optional[QueueItem] = None
    
    def add_item(self, image: np.ndarray, prompt: str, n_prompt: str, seed: int,
                 total_second_length: float, latent_window_size: int, steps: int,
                 cfg: float, gs: float, rs: float, gpu_memory_preservation: bool,
                 use_teacache: bool, mp4_crf: int, resolution: int,
                 lora_file: Optional[str], lora_multiplier: float,
                 use_magcache: bool, magcache_thresh: float, magcache_K: int,
                 magcache_retention_ratio: float) -> str:
        """添加項目到隊列"""
        item_id = str(uuid.uuid4())
        
        item = QueueItem(
            id=item_id,
            image=image,
            prompt=prompt,
            n_prompt=n_prompt,
            seed=seed,
            total_second_length=total_second_length,
            latent_window_size=latent_window_size,
            steps=steps,
            cfg=cfg,
            gs=gs,
            rs=rs,
            gpu_memory_preservation=gpu_memory_preservation,
            use_teacache=use_teacache,
            mp4_crf=mp4_crf,
            resolution=resolution,
            lora_file=lora_file,
            lora_multiplier=lora_multiplier,
            use_magcache=use_magcache,
            magcache_thresh=magcache_thresh,
            magcache_K=magcache_K,
            magcache_retention_ratio=magcache_retention_ratio
        )
        
        with self.lock:
            self.queue.append(item)
        
        return item_id
    
    def add_batch_items(self, images: List[np.ndarray], prompt: str, n_prompt: str,
                       seed: int, total_second_length: float, latent_window_size: int,
                       steps: int, cfg: float, gs: float, rs: float,
                       gpu_memory_preservation: bool, use_teacache: bool, mp4_crf: int,
                       resolution: int, lora_file: Optional[str], lora_multiplier: float,
                       use_magcache: bool, magcache_thresh: float, magcache_K: int,
                       magcache_retention_ratio: float) -> List[str]:
        """批量添加項目到隊列"""
        item_ids = []
        
        for image in images:
            item_id = self.add_item(
                image, prompt, n_prompt, seed, total_second_length,
                latent_window_size, steps, cfg, gs, rs, gpu_memory_preservation,
                use_teacache, mp4_crf, resolution, lora_file, lora_multiplier,
                use_magcache, magcache_thresh, magcache_K, magcache_retention_ratio
            )
            item_ids.append(item_id)
        
        return item_ids
    
    def get_next_item(self) -> Optional[QueueItem]:
        """獲取下一個待處理項目"""
        with self.lock:
            for item in self.queue:
                if item.status == "waiting":
                    item.status = "processing"
                    item.started_at = time.time()
                    self.current_processing = item
                    return item
        return None
    
    def complete_item(self, item_id: str, output_file: str):
        """標記項目為完成"""
        with self.lock:
            for item in self.queue:
                if item.id == item_id:
                    item.status = "completed"
                    item.completed_at = time.time()
                    item.output_file = output_file
                    if self.current_processing and self.current_processing.id == item_id:
                        self.current_processing = None
                    break
    
    def fail_item(self, item_id: str, error_message: str):
        """標記項目為失敗"""
        with self.lock:
            for item in self.queue:
                if item.id == item_id:
                    item.status = "failed"
                    item.completed_at = time.time()
                    item.error_message = error_message
                    if self.current_processing and self.current_processing.id == item_id:
                        self.current_processing = None
                    break
    
    def remove_item(self, item_id: str) -> bool:
        """從隊列中移除項目"""
        with self.lock:
            for i, item in enumerate(self.queue):
                if item.id == item_id and item.status == "waiting":
                    self.queue.pop(i)
                    return True
        return False
    
    def clear_completed(self):
        """清理已完成的項目"""
        with self.lock:
            self.queue = [item for item in self.queue if item.status not in ["completed", "failed"]]
    
    def get_queue_status(self) -> Dict[str, Any]:
        """獲取隊列狀態"""
        with self.lock:
            waiting = sum(1 for item in self.queue if item.status == "waiting")
            processing = sum(1 for item in self.queue if item.status == "processing")
            completed = sum(1 for item in self.queue if item.status == "completed")
            failed = sum(1 for item in self.queue if item.status == "failed")
            
            return {
                "total": len(self.queue),
                "waiting": waiting,
                "processing": processing,
                "completed": completed,
                "failed": failed,
                "current_processing": self.current_processing.id if self.current_processing else None
            }
    
    def get_queue_items(self) -> List[List[str]]:
        """獲取隊列項目列表（用於顯示）"""
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
    
    def is_empty(self) -> bool:
        """檢查隊列是否為空"""
        with self.lock:
            return len([item for item in self.queue if item.status == "waiting"]) == 0
    
    def has_processing(self) -> bool:
        """檢查是否有正在處理的項目"""
        with self.lock:
            return self.current_processing is not None
