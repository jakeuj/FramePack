"""
配置管理模組
負責處理應用程式的配置參數
"""
import argparse
import os
from typing import Optional, Tuple


class AppConfig:
    """應用程式配置管理類"""
    
    def __init__(self):
        self.parser = argparse.ArgumentParser()
        self._setup_base_arguments()
        self.args = None
        
    def _setup_base_arguments(self):
        """設置基礎命令行參數"""
        self.parser.add_argument('--share', action='store_true')
        self.parser.add_argument("--server", type=str, default='0.0.0.0')
        self.parser.add_argument("--port", type=int, required=False)
        self.parser.add_argument("--inbrowser", action='store_true')
        self.parser.add_argument("--output_dir", type=str, default='./outputs')
        
    def add_auth_arguments(self):
        """添加認證相關參數"""
        self.parser.add_argument("--username", type=str, default='admin', help='認證用戶名 (默認: admin)')
        self.parser.add_argument("--password", type=str, default='123456', help='認證密碼 (默認: 123456)')
        self.parser.add_argument("--no-auth", action='store_true', help='禁用認證')
        return self
        
    def parse_args(self):
        """解析命令行參數"""
        self.args = self.parser.parse_args()
        return self.args
        
    def get_auth_settings(self) -> Optional[Tuple[str, str]]:
        """獲取認證設置"""
        if not hasattr(self.args, 'no_auth') or self.args.no_auth:
            print('認證已禁用')
            return None
        
        auth_settings = (self.args.username, self.args.password)
        print(f'啟用認證 - 用戶名: {self.args.username}, 密碼: {"*" * len(self.args.password)}')
        return auth_settings
        
    def setup_environment(self):
        """設置環境變數"""
        os.environ['HF_HOME'] = os.path.abspath(
            os.path.realpath(
                os.path.join(os.path.dirname(__file__), '../hf_download')
            )
        )
        os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
        os.environ['TOKENIZERS_PARALLELISM'] = 'false'
        
    def create_output_dir(self):
        """創建輸出目錄"""
        os.makedirs(self.args.output_dir, exist_ok=True)
        
    @property
    def output_dir(self) -> str:
        """獲取輸出目錄"""
        return self.args.output_dir if self.args else './outputs'
        
    @property
    def server_name(self) -> str:
        """獲取服務器名稱"""
        return self.args.server if self.args else '0.0.0.0'
        
    @property
    def server_port(self) -> Optional[int]:
        """獲取服務器端口"""
        return self.args.port if self.args else None
        
    @property
    def share(self) -> bool:
        """是否分享"""
        return self.args.share if self.args else False
        
    @property
    def inbrowser(self) -> bool:
        """是否在瀏覽器中打開"""
        return self.args.inbrowser if self.args else False
