# FramePack 跨平台使用指南

## 🎯 概述

FramePack 服務管理腳本現在支援跨平台運行，能夠自動檢測操作系統並配置相應的環境：

- **🍎 macOS**: 開發環境，支援 Apple Silicon MPS
- **🐧 Ubuntu**: 部署環境，支援 NVIDIA CUDA

## 🔍 自動檢測功能

### 操作系統檢測

腳本會自動檢測當前操作系統：

```bash
./start.sh help
```

輸出會顯示：
```
系統信息:
  操作系統: macOS          # 或 Ubuntu 24.04
  工作目錄: /path/to/project
  Python: /path/to/.venv/bin/python
```

### 環境變數自動配置

| 操作系統 | 自動設定的環境變數 | 用途 |
|----------|-------------------|------|
| **macOS** | `PYTORCH_ENABLE_MPS_FALLBACK=1` | Apple Silicon MPS 支援 |
|          | `TOKENIZERS_PARALLELISM=false` | 避免 tokenizer 並行問題 |
| **Ubuntu** | `TOKENIZERS_PARALLELISM=false` | 避免 tokenizer 並行問題 |
|           | `CUDA_VISIBLE_DEVICES=0,1,2,3` | NVIDIA GPU 可見性 |

## 🔧 使用模式

### 1. 開發模式 (推薦用於 macOS)

```bash
./start.sh dev
```

**特點：**
- 互動式選擇要啟動的版本
- 顯示詳細的環境信息
- 適合開發和測試

**輸出示例：**
```
🚀 FramePack 開發模式
操作系統: macOS

✅ macOS 環境變數已設置:
   PYTORCH_ENABLE_MPS_FALLBACK=1
   TOKENIZERS_PARALLELISM=false

✅ 發現虛擬環境: /path/to/.venv
🐍 Python 版本: Python 3.10.0

請選擇要啟動的版本:
1) FramePack 基礎版本 (demo_gradio_refactored.py)
2) FramePack F1 版本 (demo_gradio_f1_refactored.py) - 包含認證和高級功能
3) 退出
```

### 2. 生產模式 (推薦用於 Ubuntu)

```bash
./start.sh start
```

**特點：**
- 自動服務管理
- 後台運行
- 完整的日誌記錄
- 適合部署環境

## 🌐 網路配置差異

### macOS (開發環境)

- **默認監聽**: `127.0.0.1` (本機訪問)
- **訪問地址**: `http://localhost:7860`
- **外部訪問**: 需要設定 `FORCE_EXTERNAL_ACCESS=true`

### Ubuntu (部署環境)

- **默認監聽**: `0.0.0.0` (允許外部訪問)
- **訪問地址**: 
  - 本機: `http://localhost:7860`
  - 外部: `http://YOUR_IP:7860`

### 強制外部訪問 (macOS)

如果在 macOS 上需要外部訪問：

```bash
export FORCE_EXTERNAL_ACCESS=true
./start.sh start
```

## 🤖 GPU 支援差異

### macOS (Apple Silicon)

- **GPU 類型**: Apple Silicon MPS (Metal Performance Shaders)
- **環境變數**: `PYTORCH_ENABLE_MPS_FALLBACK=1`
- **檢測命令**: 無 `nvidia-smi`，使用 CPU 模式顯示

### Ubuntu (NVIDIA)

- **GPU 類型**: NVIDIA CUDA
- **自動偵測**: 使用 `nvidia-smi` 檢測 GPU
- **多 GPU**: 自動啟用第二個服務

## 📋 平台特定配置

### macOS 開發環境設定

1. **安裝依賴**:
   ```bash
   # 安裝 Python 3.10+
   brew install python@3.10
   
   # 創建虛擬環境
   python3 -m venv .venv
   source .venv/bin/activate
   
   # 安裝依賴
   pip install -r requirements.txt
   ```

2. **啟動開發模式**:
   ```bash
   ./start.sh dev
   ```

### Ubuntu 部署環境設定

1. **安裝依賴**:
   ```bash
   # 更新系統
   sudo apt update && sudo apt upgrade -y
   
   # 安裝 Python 和虛擬環境
   sudo apt install python3 python3-venv python3-pip -y
   
   # 創建虛擬環境
   python3 -m venv .venv
   source .venv/bin/activate
   
   # 安裝依賴
   pip install -r requirements.txt
   ```

2. **安裝 NVIDIA 驅動** (如果有 GPU):
   ```bash
   # 安裝 NVIDIA 驅動
   sudo apt install nvidia-driver-535 -y
   
   # 重啟系統
   sudo reboot
   
   # 驗證安裝
   nvidia-smi
   ```

3. **啟動生產服務**:
   ```bash
   ./start.sh start
   ```

## 🔄 工作流程建議

### 開發流程 (macOS)

1. **本地開發**:
   ```bash
   ./start.sh dev
   # 選擇版本進行開發和測試
   ```

2. **測試功能**:
   ```bash
   # 檢查 GPU 配置
   ./start.sh gpu
   
   # 檢查服務狀態
   ./start.sh status
   ```

### 部署流程 (Ubuntu)

1. **部署到服務器**:
   ```bash
   # 上傳代碼到 Ubuntu 服務器
   scp -r . user@server:/path/to/framepack/
   ```

2. **啟動生產服務**:
   ```bash
   ssh user@server
   cd /path/to/framepack/
   ./start.sh start
   ```

3. **監控服務**:
   ```bash
   # 檢查服務狀態
   ./start.sh status
   
   # 查看日誌
   tail -f logs/framepack_7860.log
   ```

## 🛠️ 故障排除

### 常見問題

**1. macOS 上 MPS 不可用**
```bash
# 檢查 PyTorch MPS 支援
python3 -c "import torch; print(torch.backends.mps.is_available())"

# 如果不支援，會自動回退到 CPU
```

**2. Ubuntu 上 CUDA 不可用**
```bash
# 檢查 NVIDIA 驅動
nvidia-smi

# 檢查 CUDA 安裝
nvcc --version

# 檢查 PyTorch CUDA 支援
python3 -c "import torch; print(torch.cuda.is_available())"
```

**3. 虛擬環境問題**
```bash
# 重新創建虛擬環境
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 日誌檢查

```bash
# 查看服務日誌
tail -f logs/framepack_7860.log

# 查看系統日誌 (Ubuntu)
journalctl -f | grep framepack

# 查看系統日誌 (macOS)
log stream --predicate 'process == "python3"'
```

## 🎯 最佳實踐

1. **開發環境 (macOS)**:
   - 使用 `./start.sh dev` 進行開發
   - 定期測試不同版本的兼容性
   - 使用本機訪問進行測試

2. **部署環境 (Ubuntu)**:
   - 使用 `./start.sh start` 啟動生產服務
   - 配置防火牆允許外部訪問
   - 定期監控服務狀態和日誌

3. **跨平台開發**:
   - 在 macOS 上開發和測試
   - 在 Ubuntu 上驗證部署
   - 使用相同的腳本和配置

## 📞 技術支援

如果遇到跨平台相關問題：

1. **檢查操作系統檢測**: `./start.sh help`
2. **檢查環境變數**: 查看輸出中的環境變數部分
3. **檢查 GPU 配置**: `./start.sh gpu`
4. **查看詳細日誌**: `tail -f logs/framepack_*.log`
