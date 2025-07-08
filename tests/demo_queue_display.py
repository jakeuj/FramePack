#!/usr/bin/env python3
"""
演示隊列顯示修復效果
創建一個簡單的 Gradio 界面來展示修復前後的差異
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gradio as gr
from core.queue_manager import ImageProcessingQueue
import numpy as np

def create_demo_data():
    """創建演示數據"""
    queue_manager = ImageProcessingQueue()
    test_image = np.zeros((100, 100, 3), dtype=np.uint8)
    
    # 添加幾個測試項目
    test_items = [
        ("短提示詞", "測試項目1"),
        ("這是一個很長的提示詞，用來測試截斷功能是否正常工作，應該會被截斷", "測試項目2"),
        ("Another test prompt", "測試項目3"),
        ("最後一個測試提示詞", "測試項目4")
    ]
    
    for prompt, desc in test_items:
        queue_manager.add_item(
            image=test_image,
            prompt=prompt,
            n_prompt="",
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
    
    return queue_manager

def get_correct_format():
    """獲取修復後的正確格式"""
    queue_manager = create_demo_data()
    return queue_manager.get_queue_items()

def get_wrong_format():
    """模擬修復前的錯誤格式（返回字典列表）"""
    queue_manager = create_demo_data()
    
    # 模擬舊的錯誤格式
    items = []
    for item in queue_manager.queue:
        items.append({
            "id": item.id,
            "prompt": item.prompt[:50] + "..." if len(item.prompt) > 50 else item.prompt,
            "status": item.status,
            "created_at": f"{item.created_at:.0f}"
        })
    return items

def refresh_correct():
    """刷新正確格式的數據"""
    return get_correct_format()

def refresh_wrong():
    """刷新錯誤格式的數據"""
    return get_wrong_format()

# 創建 Gradio 界面
with gr.Blocks(title="隊列顯示修復演示") as demo:
    gr.Markdown("# 🔧 FramePack 隊列顯示修復演示")
    gr.Markdown("這個演示展示了修復前後隊列顯示的差異")
    
    with gr.Row():
        with gr.Column():
            gr.Markdown("## ✅ 修復後（正確格式）")
            gr.Markdown("返回 `List[List[str]]` - 每行是一個列表")
            
            correct_df = gr.Dataframe(
                headers=["ID", "提示詞", "狀態", "創建時間"],
                datatype=["str", "str", "str", "str"],
                label="正確格式 - 顯示正常",
                max_height=200,
                interactive=False,
                value=get_correct_format()
            )
            
            refresh_correct_btn = gr.Button("🔄 刷新正確格式", variant="primary")
            
        with gr.Column():
            gr.Markdown("## ❌ 修復前（錯誤格式）")
            gr.Markdown("返回 `List[Dict]` - 顯示為 '[object Object]'")
            
            wrong_df = gr.Dataframe(
                headers=["ID", "提示詞", "狀態", "創建時間"],
                datatype=["str", "str", "str", "str"],
                label="錯誤格式 - 顯示異常",
                max_height=200,
                interactive=False,
                value=get_wrong_format()
            )
            
            refresh_wrong_btn = gr.Button("🔄 刷新錯誤格式", variant="secondary")
    
    # 說明
    with gr.Row():
        gr.Markdown("""
        ### 📝 說明
        
        **修復前的問題:**
        - `get_queue_items()` 返回 `List[Dict[str, Any]]`
        - Gradio Dataframe 無法正確顯示字典，顯示為 `[object Object]`
        
        **修復後的解決方案:**
        - `get_queue_items()` 返回 `List[List[str]]`
        - 每個內部列表包含按順序排列的字段值
        - Gradio Dataframe 可以正確顯示每個字段
        
        **修復的核心代碼:**
        ```python
        # 修復前
        items.append({
            "id": item.id,
            "prompt": item.prompt,
            "status": item.status,
            "created_at": time.strftime("%H:%M:%S", time.localtime(item.created_at))
        })
        
        # 修復後
        items.append([
            item.id,  # ID
            item.prompt,  # 提示詞
            item.status,  # 狀態
            time.strftime("%H:%M:%S", time.localtime(item.created_at))  # 創建時間
        ])
        ```
        """)
    
    # 事件處理
    refresh_correct_btn.click(
        fn=refresh_correct,
        outputs=correct_df
    )
    
    refresh_wrong_btn.click(
        fn=refresh_wrong,
        outputs=wrong_df
    )

if __name__ == "__main__":
    print("🚀 啟動隊列顯示修復演示...")
    print("📱 打開瀏覽器查看修復前後的差異")
    demo.launch(
        server_name="0.0.0.0",
        server_port=7863,
        share=False,
        show_error=True
    )
