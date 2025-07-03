"""
FramePack 應用程式
基於原始 demo_gradio.py 的重構版本
"""
from core.base_app import BaseApp
from core.video_processor import FramePackVideoProcessor


class FramePackApp(BaseApp):
    """FramePack 應用程式類"""
    
    def __init__(self):
        super().__init__(
            model_path='lllyasviel/FramePackI2V_HY',
            app_title='FramePack'
        )
        self.video_processor = None
    
    def get_video_processor(self):
        """獲取視頻處理器"""
        if self.video_processor is None:
            self.video_processor = FramePackVideoProcessor(
                model_manager=self.model_manager,
                output_dir=self.config.output_dir
            )
        return self.video_processor
    
    def enable_advanced_features(self) -> bool:
        """不啟用高級功能"""
        return False


def main():
    """主函數"""
    app = FramePackApp()
    app.launch()


if __name__ == "__main__":
    main()
