# FramePack 重構說明

## 重構目標

將原始的 `demo_gradio.py` 和 `demo_gradio_f1.py` 重構為符合 SOLID 原則的物件導向設計，提高代碼的可維護性、可擴展性和可測試性。

## 架構設計

### 核心模組 (core/)

#### 1. AppConfig (config.py)
- **職責**: 管理應用程式配置和命令行參數
- **SOLID 原則**: 單一職責原則 (SRP)
- **功能**:
  - 解析命令行參數
  - 管理環境變數設置
  - 提供認證配置

#### 2. ModelManager (model_manager.py)
- **職責**: 管理所有 AI 模型的載入和初始化
- **SOLID 原則**: 單一職責原則 (SRP)
- **功能**:
  - 模型載入和初始化
  - VRAM 管理和優化
  - LoRA 權重應用

#### 3. FileManager (file_manager.py)
- **職責**: 處理文件管理功能
- **SOLID 原則**: 單一職責原則 (SRP)
- **功能**:
  - 視頻文件列表管理
  - 智能清理功能
  - 文件下載處理

#### 4. BaseVideoProcessor (video_processor.py)
- **職責**: 定義視頻處理的抽象接口
- **SOLID 原則**: 
  - 單一職責原則 (SRP)
  - 開放封閉原則 (OCP)
  - 依賴反轉原則 (DIP)
- **功能**:
  - 抽象視頻處理流程
  - 提供共同的處理方法
  - 支持不同的處理策略

#### 5. FramePackVideoProcessor & FramePackF1VideoProcessor
- **職責**: 實現具體的視頻處理邏輯
- **SOLID 原則**: 里氏替換原則 (LSP)
- **功能**:
  - 實現不同版本的採樣邏輯
  - 處理模型特定的參數

#### 6. UIBuilder (ui_builder.py)
- **職責**: 構建 Gradio 用戶界面
- **SOLID 原則**: 單一職責原則 (SRP)
- **功能**:
  - 創建 UI 組件
  - 設置事件處理
  - 支持功能開關

#### 7. BaseApp (base_app.py)
- **職責**: 提供應用程式的基礎框架
- **SOLID 原則**: 
  - 開放封閉原則 (OCP)
  - 依賴反轉原則 (DIP)
- **功能**:
  - 應用程式生命週期管理
  - 組件協調
  - 抽象應用程式接口

### 應用程式模組 (apps/)

#### 1. FramePackApp (framepack_app.py)
- **職責**: 實現基礎版本的 FramePack 應用
- **SOLID 原則**: 里氏替換原則 (LSP)
- **功能**:
  - 使用原始模型路徑
  - 基本功能集

#### 2. FramePackF1App (framepack_f1_app.py)
- **職責**: 實現增強版本的 FramePack F1 應用
- **SOLID 原則**: 里氏替換原則 (LSP)
- **功能**:
  - 使用 F1 模型路徑
  - 包含認證功能
  - 高級文件管理功能

## 使用方式

### 運行基礎版本
```bash
python demo_gradio_refactored.py
```

### 運行 F1 版本
```bash
python demo_gradio_f1_refactored.py
```

### 命令行參數
所有原始的命令行參數都被保留，例如：
```bash
python demo_gradio_f1_refactored.py --server 127.0.0.1 --port 7860 --username admin --password 123456
```

## SOLID 原則的體現

### 1. 單一職責原則 (SRP)
- 每個類都有明確的單一職責
- `ModelManager` 只負責模型管理
- `FileManager` 只負責文件操作
- `UIBuilder` 只負責界面構建

### 2. 開放封閉原則 (OCP)
- `BaseVideoProcessor` 定義了擴展點
- 新的視頻處理策略可以通過繼承添加
- `BaseApp` 允許新的應用類型擴展

### 3. 里氏替換原則 (LSP)
- `FramePackVideoProcessor` 和 `FramePackF1VideoProcessor` 可以互相替換
- `FramePackApp` 和 `FramePackF1App` 可以互相替換

### 4. 接口隔離原則 (ISP)
- 每個組件只依賴它需要的接口
- UI 組件不直接依賴模型實現

### 5. 依賴反轉原則 (DIP)
- 高層模組不依賴低層模組的具體實現
- 通過抽象類和接口進行依賴注入

## 優勢

1. **可維護性**: 代碼結構清晰，職責分離
2. **可擴展性**: 容易添加新功能和新模型
3. **可測試性**: 每個組件可以獨立測試
4. **可重用性**: 組件可以在不同應用中重用
5. **向後兼容**: 保持原有的功能和接口

## MPS (Apple Silicon) 兼容性

### 問題說明
在 Apple Silicon (M1/M2/M3) 設備上，PyTorch 的 MPS 後端不支持某些操作（如 `avg_pool3d`），可能會導致運行時錯誤。

### 解決方案
我們已經在重構版本中內建了 MPS 兼容性修復：

1. **自動回退設置**: 在應用啟動時自動設置 `PYTORCH_ENABLE_MPS_FALLBACK=1`
2. **環境變數配置**: 正確配置相關環境變數
3. **記憶體管理優化**: 改進了 MPS 設備的記憶體檢測邏輯

### 使用建議

**推薦方式 - 使用啟動腳本**:
```bash
./start_framepack.sh
```

**手動啟動**:
```bash
export PYTORCH_ENABLE_MPS_FALLBACK=1
export TOKENIZERS_PARALLELISM=false
python demo_gradio_f1_refactored.py
```

**測試 MPS 兼容性**:
```bash
python fix_mps_compatibility.py
```

### 性能說明
- 當遇到不支持的操作時，會自動回退到 CPU 執行
- 這可能會稍微影響性能，但確保了穩定性
- 大部分操作仍然在 GPU 上執行，整體性能影響有限

## 未來擴展

基於這個架構，可以輕鬆添加：
- 新的模型支持
- 新的視頻處理策略
- 新的 UI 主題
- 新的文件格式支持
- 更多的認證方式
- 更好的 MPS 優化
