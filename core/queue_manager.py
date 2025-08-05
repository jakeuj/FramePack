"""
圖片處理隊列管理器
負責管理批量圖片上傳和處理隊列
支援多服務實例共享隊列
"""
import uuid
import time
import json
import os
import pickle
import fcntl
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
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
    processing_gpu: Optional[str] = None  # 記錄處理此項目的 GPU ID

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式（用於序列化）"""
        data = asdict(self)
        # 將 numpy 陣列轉換為可序列化的格式
        if isinstance(self.image, np.ndarray):
            data['image'] = {
                'data': self.image.tolist(),
                'shape': self.image.shape,
                'dtype': str(self.image.dtype)
            }
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QueueItem':
        """從字典格式創建實例"""
        # 重建 numpy 陣列
        if isinstance(data['image'], dict) and 'data' in data['image']:
            image_data = data['image']
            data['image'] = np.array(image_data['data'], dtype=image_data['dtype']).reshape(image_data['shape'])
        return cls(**data)


class SharedQueueManager:
    """共享隊列管理器 - 基於文件系統的多服務實例隊列共享"""

    def __init__(self, queue_dir: str = "./queue_data"):
        self.queue_dir = queue_dir
        self.queue_file = os.path.join(queue_dir, "queue.json")
        self.lock_file = os.path.join(queue_dir, "queue.lock")
        self.images_dir = os.path.join(queue_dir, "images")

        # 創建必要的目錄
        os.makedirs(queue_dir, exist_ok=True)
        os.makedirs(self.images_dir, exist_ok=True)

        # 初始化隊列文件
        if not os.path.exists(self.queue_file):
            self._save_queue([])

    def _get_file_lock(self):
        """獲取文件鎖"""
        lock_fd = os.open(self.lock_file, os.O_CREAT | os.O_WRONLY)
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        return lock_fd

    def _release_file_lock(self, lock_fd):
        """釋放文件鎖"""
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)

    def _save_image(self, image: np.ndarray, item_id: str) -> str:
        """保存圖片到文件系統"""
        image_path = os.path.join(self.images_dir, f"{item_id}.pkl")
        with open(image_path, 'wb') as f:
            pickle.dump(image, f)
        return image_path

    def _load_image(self, image_path: str) -> np.ndarray:
        """從文件系統加載圖片"""
        with open(image_path, 'rb') as f:
            return pickle.load(f)

    def _save_queue(self, queue_data: List[Dict[str, Any]]):
        """保存隊列到文件"""
        with open(self.queue_file, 'w', encoding='utf-8') as f:
            json.dump(queue_data, f, ensure_ascii=False, indent=2)

    def _load_queue(self) -> List[Dict[str, Any]]:
        """從文件加載隊列"""
        try:
            with open(self.queue_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []


class ImageProcessingQueue:
    """圖片處理隊列管理器 - 支援多服務實例共享"""

    def __init__(self, gpu_id: str = "0", shared_queue: bool = True):
        self.gpu_id = gpu_id
        self.shared_queue = shared_queue

        if shared_queue:
            self.shared_manager = SharedQueueManager()
        else:
            # 本地隊列模式（向後兼容）
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

        if self.shared_queue:
            return self._add_item_shared(item)
        else:
            with self.lock:
                self.queue.append(item)
            return item_id

    def _add_item_shared(self, item: QueueItem) -> str:
        """添加項目到共享隊列"""
        lock_fd = self.shared_manager._get_file_lock()
        try:
            # 保存圖片到文件系統
            image_path = self.shared_manager._save_image(item.image, item.id)

            # 加載當前隊列
            queue_data = self.shared_manager._load_queue()

            # 創建項目數據（不包含圖片數據）
            item_data = item.to_dict()
            item_data['image_path'] = image_path
            del item_data['image']  # 移除圖片數據，使用路徑引用

            # 添加到隊列
            queue_data.append(item_data)

            # 保存隊列
            self.shared_manager._save_queue(queue_data)

            return item.id
        finally:
            self.shared_manager._release_file_lock(lock_fd)
    
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
        if self.shared_queue:
            return self._get_next_item_shared()
        else:
            with self.lock:
                for item in self.queue:
                    if item.status == "waiting":
                        item.status = "processing"
                        item.started_at = time.time()
                        self.current_processing = item
                        return item
            return None

    def _get_next_item_shared(self) -> Optional[QueueItem]:
        """從共享隊列獲取下一個待處理項目"""
        lock_fd = self.shared_manager._get_file_lock()
        try:
            queue_data = self.shared_manager._load_queue()

            # 尋找第一個等待中的項目
            for item_data in queue_data:
                if item_data['status'] == "waiting":
                    # 標記為處理中
                    item_data['status'] = "processing"
                    item_data['started_at'] = time.time()
                    item_data['processing_gpu'] = self.gpu_id

                    # 保存更新後的隊列
                    self.shared_manager._save_queue(queue_data)

                    # 加載圖片並創建 QueueItem
                    image = self.shared_manager._load_image(item_data['image_path'])
                    item_data['image'] = image
                    del item_data['image_path']

                    return QueueItem.from_dict(item_data)

            return None
        finally:
            self.shared_manager._release_file_lock(lock_fd)
    
    def complete_item(self, item_id: str, output_file: str):
        """標記項目為完成"""
        if self.shared_queue:
            self._complete_item_shared(item_id, output_file)
        else:
            with self.lock:
                for item in self.queue:
                    if item.id == item_id:
                        item.status = "completed"
                        item.completed_at = time.time()
                        item.output_file = output_file
                        if self.current_processing and self.current_processing.id == item_id:
                            self.current_processing = None
                        break

    def _complete_item_shared(self, item_id: str, output_file: str):
        """在共享隊列中標記項目為完成"""
        lock_fd = self.shared_manager._get_file_lock()
        try:
            queue_data = self.shared_manager._load_queue()

            for item_data in queue_data:
                if item_data['id'] == item_id:
                    item_data['status'] = "completed"
                    item_data['completed_at'] = time.time()
                    item_data['output_file'] = output_file
                    break

            self.shared_manager._save_queue(queue_data)
        finally:
            self.shared_manager._release_file_lock(lock_fd)
    
    def fail_item(self, item_id: str, error_message: str):
        """標記項目為失敗"""
        if self.shared_queue:
            self._fail_item_shared(item_id, error_message)
        else:
            with self.lock:
                for item in self.queue:
                    if item.id == item_id:
                        item.status = "failed"
                        item.completed_at = time.time()
                        item.error_message = error_message
                        if self.current_processing and self.current_processing.id == item_id:
                            self.current_processing = None
                        break

    def _fail_item_shared(self, item_id: str, error_message: str):
        """在共享隊列中標記項目為失敗"""
        lock_fd = self.shared_manager._get_file_lock()
        try:
            queue_data = self.shared_manager._load_queue()

            for item_data in queue_data:
                if item_data['id'] == item_id:
                    item_data['status'] = "failed"
                    item_data['completed_at'] = time.time()
                    item_data['error_message'] = error_message
                    break

            self.shared_manager._save_queue(queue_data)
        finally:
            self.shared_manager._release_file_lock(lock_fd)
    
    def remove_item(self, item_id: str) -> bool:
        """從隊列中移除項目"""
        if self.shared_queue:
            return self._remove_item_shared(item_id)
        else:
            with self.lock:
                for i, item in enumerate(self.queue):
                    if item.id == item_id and item.status == "waiting":
                        self.queue.pop(i)
                        return True
            return False

    def _remove_item_shared(self, item_id: str) -> bool:
        """從共享隊列中移除項目"""
        lock_fd = self.shared_manager._get_file_lock()
        try:
            queue_data = self.shared_manager._load_queue()

            for i, item in enumerate(queue_data):
                if item['id'] == item_id and item['status'] == "waiting":
                    # 刪除對應的圖片文件
                    if 'image_path' in item:
                        try:
                            if os.path.exists(item['image_path']):
                                os.remove(item['image_path'])
                        except Exception:
                            pass  # 忽略文件刪除錯誤

                    # 從隊列中移除
                    queue_data.pop(i)
                    self.shared_manager._save_queue(queue_data)
                    return True

            return False
        finally:
            self.shared_manager._release_file_lock(lock_fd)
    
    def clear_completed(self):
        """清理已完成的項目"""
        if self.shared_queue:
            self._clear_completed_shared()
        else:
            with self.lock:
                self.queue = [item for item in self.queue if item.status not in ["completed", "failed"]]

    def _clear_completed_shared(self):
        """清理共享隊列中已完成的項目"""
        lock_fd = self.shared_manager._get_file_lock()
        try:
            queue_data = self.shared_manager._load_queue()

            # 獲取要刪除的項目的圖片路徑
            to_remove = [item for item in queue_data if item['status'] in ["completed", "failed"]]

            # 刪除對應的圖片文件
            for item in to_remove:
                if 'image_path' in item:
                    try:
                        if os.path.exists(item['image_path']):
                            os.remove(item['image_path'])
                    except Exception:
                        pass  # 忽略文件刪除錯誤

            # 保留未完成的項目
            filtered_data = [item for item in queue_data if item['status'] not in ["completed", "failed"]]
            self.shared_manager._save_queue(filtered_data)
        finally:
            self.shared_manager._release_file_lock(lock_fd)
    
    def get_queue_status(self) -> Dict[str, Any]:
        """獲取隊列狀態"""
        if self.shared_queue:
            return self._get_queue_status_shared()
        else:
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

    def _get_queue_status_shared(self) -> Dict[str, Any]:
        """獲取共享隊列狀態"""
        lock_fd = self.shared_manager._get_file_lock()
        try:
            queue_data = self.shared_manager._load_queue()

            waiting = sum(1 for item in queue_data if item['status'] == "waiting")
            processing = sum(1 for item in queue_data if item['status'] == "processing")
            completed = sum(1 for item in queue_data if item['status'] == "completed")
            failed = sum(1 for item in queue_data if item['status'] == "failed")

            # 找到當前 GPU 正在處理的項目
            current_processing = None
            for item in queue_data:
                if item['status'] == "processing" and item.get('processing_gpu') == self.gpu_id:
                    current_processing = item['id']
                    break

            return {
                "total": len(queue_data),
                "waiting": waiting,
                "processing": processing,
                "completed": completed,
                "failed": failed,
                "current_processing": current_processing,
                "gpu_id": self.gpu_id
            }
        finally:
            self.shared_manager._release_file_lock(lock_fd)
    
    def get_queue_items(self) -> List[List[str]]:
        """獲取隊列項目列表（用於顯示）- 手機優化版本，不顯示提示詞"""
        if self.shared_queue:
            return self._get_queue_items_shared()
        else:
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

    def _get_queue_items_shared(self) -> List[List[str]]:
        """獲取共享隊列項目列表"""
        lock_fd = self.shared_manager._get_file_lock()
        try:
            queue_data = self.shared_manager._load_queue()
            items = []
            for item_data in queue_data:
                # 添加 GPU 信息到狀態顯示
                status = item_data['status']
                if status == "processing" and item_data.get('processing_gpu'):
                    status = f"processing (GPU {item_data['processing_gpu']})"

                items.append([
                    item_data['id'],
                    status,
                    time.strftime("%H:%M:%S", time.localtime(item_data['created_at']))
                ])
            return items
        finally:
            self.shared_manager._release_file_lock(lock_fd)

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
    
    def is_empty(self) -> bool:
        """檢查隊列是否為空"""
        if self.shared_queue:
            return self._is_empty_shared()
        else:
            with self.lock:
                return len([item for item in self.queue if item.status == "waiting"]) == 0

    def _is_empty_shared(self) -> bool:
        """檢查共享隊列是否為空"""
        lock_fd = self.shared_manager._get_file_lock()
        try:
            queue_data = self.shared_manager._load_queue()
            return len([item for item in queue_data if item['status'] == "waiting"]) == 0
        finally:
            self.shared_manager._release_file_lock(lock_fd)
    
    def has_processing(self) -> bool:
        """檢查是否有正在處理的項目"""
        if self.shared_queue:
            return self._has_processing_shared()
        else:
            with self.lock:
                return self.current_processing is not None

    def _has_processing_shared(self) -> bool:
        """檢查共享隊列是否有正在處理的項目"""
        lock_fd = self.shared_manager._get_file_lock()
        try:
            queue_data = self.shared_manager._load_queue()
            return any(item['status'] == 'processing' for item in queue_data)
        finally:
            self.shared_manager._release_file_lock(lock_fd)

    def clear_all(self):
        """清空所有隊列項目（僅清空等待中的項目）"""
        if self.shared_queue:
            self._clear_all_shared()
        else:
            with self.lock:
                self.queue = [item for item in self.queue if item.status != "waiting"]

    def _clear_all_shared(self):
        """清空共享隊列中等待的項目"""
        lock_fd = self.shared_manager._get_file_lock()
        try:
            queue_data = self.shared_manager._load_queue()

            # 只保留非等待狀態的項目
            filtered_data = [item for item in queue_data if item['status'] != 'waiting']

            # 刪除等待項目的圖片文件
            for item in queue_data:
                if item['status'] == 'waiting' and 'image_path' in item:
                    try:
                        if os.path.exists(item['image_path']):
                            os.remove(item['image_path'])
                    except Exception:
                        pass  # 忽略文件刪除錯誤

            self.shared_manager._save_queue(filtered_data)
        finally:
            self.shared_manager._release_file_lock(lock_fd)
