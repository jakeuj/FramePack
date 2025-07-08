#!/usr/bin/env python3
"""
調試 Gradio 組件問題的測試腳本
"""

import os
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
os.environ['TOKENIZERS_PARALLELISM'] = 'false'

import gradio as gr

def test_gradio_components():
    """測試各個 Gradio 組件是否正常工作"""
    
    print("測試 Gradio 組件...")
    
    try:
        print("1. 測試 Dataframe 組件...")
        df = gr.Dataframe(
            headers=["ID", "提示詞", "狀態", "創建時間"],
            datatype=["str", "str", "str", "str"],
            label="隊列項目",
            max_height=150,
            interactive=False
        )
        print("✓ Dataframe 組件正常")
    except Exception as e:
        print(f"✗ Dataframe 組件錯誤: {e}")
        return False
    
    try:
        print("2. 測試 Image 組件...")
        img = gr.Image(sources='upload', type="numpy", label="單張圖片", height=320)
        print("✓ Image 組件正常")
    except Exception as e:
        print(f"✗ Image 組件錯誤: {e}")
        return False
    
    try:
        print("3. 測試 Video 組件...")
        vid = gr.Video(label="視頻預覽", visible=False, height=300)
        print("✓ Video 組件正常")
    except Exception as e:
        print(f"✗ Video 組件錯誤: {e}")
        return False
    
    try:
        print("4. 測試完整界面創建...")
        with gr.Blocks() as demo:
            gr.Markdown("# 測試界面")
            
            with gr.Row():
                input_image = gr.Image(sources='upload', type="numpy", label="單張圖片", height=320)
                result_video = gr.Video(label="Finished Frames", autoplay=True, show_share_button=False, height=512, loop=True)
            
            queue_list = gr.Dataframe(
                headers=["ID", "提示詞", "狀態", "創建時間"],
                datatype=["str", "str", "str", "str"],
                label="隊列項目",
                max_height=150,
                interactive=False
            )
        
        print("✓ 完整界面創建正常")
        return True
        
    except Exception as e:
        print(f"✗ 完整界面創建錯誤: {e}")
        return False

if __name__ == "__main__":
    print(f"Gradio 版本: {gr.__version__}")
    success = test_gradio_components()
    
    if success:
        print("\n所有測試通過！")
    else:
        print("\n測試失敗！")
