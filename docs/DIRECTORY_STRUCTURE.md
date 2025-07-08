# FramePackB 目錄結構

## 根目錄
- `README.md` - 主要說明文檔
- `LICENSE` - 授權文件
- `requirements.txt` - Python 依賴
- `start.sh` - Ubuntu 啟動腳本
- `start_framepack.sh` - macOS 啟動腳本

## 主要模組
- `apps/` - 應用程式主要入口
- `core/` - 核心功能模組
- `diffusers_helper/` - Diffusers 相關輔助工具
- `utils/` - 通用工具函數

## 文檔
- `docs/` - 所有文檔文件
  - `CROSS_PLATFORM_GUIDE.md` - 跨平台指南
  - `GPU_AUTO_DETECTION_GUIDE.md` - GPU 自動檢測指南
  - `NETWORK_ACCESS_GUIDE.md` - 網路存取指南
  - `REFACTORING_README.md` - 重構說明
  - `START_SCRIPT_README.md` - 啟動腳本說明

## 測試
- `tests/` - 所有測試文件
  - `test_*.py` - 單元測試
  - `verify_refactoring.py` - 重構驗證腳本

## 範例
- `examples/` - 示例和演示腳本
  - `demo_gradio*.py` - Gradio 演示腳本

## 其他
- `hf_download/` - Hugging Face 下載相關
- `outputs/` - 輸出文件
