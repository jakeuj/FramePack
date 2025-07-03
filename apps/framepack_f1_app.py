"""
FramePack F1 應用程式
基於原始 demo_gradio_f1.py 的重構版本，包含認證和高級文件管理功能
"""
from core.base_app import BaseApp
from core.video_processor import FramePackF1VideoProcessor


class FramePackF1App(BaseApp):
    """FramePack F1 應用程式類"""
    
    def __init__(self):
        super().__init__(
            model_path='lllyasviel/FramePack_F1_I2V_HY_20250503',
            app_title='FramePack-F1'
        )
        self.video_processor = None
        
        # 設置認證功能
        self.setup_auth()
    
    def get_video_processor(self):
        """獲取視頻處理器"""
        if self.video_processor is None:
            self.video_processor = FramePackF1VideoProcessor(
                model_manager=self.model_manager,
                output_dir=self.config.output_dir
            )
        return self.video_processor
    
    def enable_advanced_features(self) -> bool:
        """啟用高級功能"""
        return True


def main():
    """主函數"""
    app = FramePackF1App()
    app.launch()


if __name__ == "__main__":
    main()
