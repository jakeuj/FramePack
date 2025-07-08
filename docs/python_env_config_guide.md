# 🐍 FramePack Python 環境配置指南

## 📋 功能概述

FramePack 現在支援透過 `config.env` 文件來配置 Python 虛擬環境路徑，讓您可以：

- ✅ **自定義虛擬環境路徑**：指定任意位置的虛擬環境
- ✅ **直接指定 Python 解釋器**：使用特定的 Python 解釋器路徑
- ✅ **靈活的環境管理**：支援本地和遠端開發環境
- ✅ **向後兼容**：未配置時自動使用默認的 `.venv` 目錄

## 🚀 配置選項

### 1. 本地虛擬環境路徑 (LOCAL_VENV_PATH)

指定虛擬環境的根目錄路徑：

```bash
# 使用自定義虛擬環境目錄
LOCAL_VENV_PATH=/home/user/.virtualenvs/FramePackB

# 使用相對路徑
LOCAL_VENV_PATH=../my_venv

# 留空使用默認 .venv 目錄
LOCAL_VENV_PATH=
```

### 2. 本地 Python 解釋器 (LOCAL_PYTHON)

直接指定 Python 解釋器的完整路徑：

```bash
# 直接指定 Python 解釋器路徑
LOCAL_PYTHON=/home/jake/.virtualenvs/FramePackB/bin/python

# 使用系統 Python (不建議)
LOCAL_PYTHON=/usr/bin/python3

# 留空自動從虛擬環境推導
LOCAL_PYTHON=
```

### 3. 優先級順序

配置的優先級順序如下：

1. **LOCAL_PYTHON** (最高優先級) - 直接使用指定的 Python 解釋器
2. **LOCAL_VENV_PATH** - 使用指定虛擬環境的 Python 解釋器
3. **默認行為** - 使用工作目錄下的 `.venv/bin/python`

## 🎯 使用場景

### 場景 1: 使用 pyenv 管理的虛擬環境

```bash
# config.env
LOCAL_VENV_PATH=/Users/username/.pyenv/versions/framepack-env
```

### 場景 2: 使用 virtualenv 創建的環境

```bash
# config.env
LOCAL_VENV_PATH=/home/user/.virtualenvs/FramePackB
```

### 場景 3: 直接指定 Python 解釋器

```bash
# config.env
LOCAL_PYTHON=/home/jake/.virtualenvs/FramePackB/bin/python
```

### 場景 4: 遠端開發環境

```bash
# config.env
ENABLE_REMOTE=true
REMOTE_PYTHON=/home/jake/.virtualenvs/FramePackB/bin/python
```

## 📖 配置步驟

### 1. 複製範例配置文件

```bash
cp config.env.example config.env
```

### 2. 編輯配置文件

```bash
# 使用文本編輯器編輯
nano config.env

# 或使用內建配置管理工具
./start.sh config
```

### 3. 配置 Python 環境

根據您的需求選擇以下其中一種方式：

#### 方式 A: 指定虛擬環境目錄
```bash
LOCAL_VENV_PATH=/path/to/your/venv
LOCAL_PYTHON=
```

#### 方式 B: 直接指定 Python 解釋器
```bash
LOCAL_VENV_PATH=
LOCAL_PYTHON=/path/to/your/venv/bin/python
```

#### 方式 C: 使用默認設置
```bash
LOCAL_VENV_PATH=
LOCAL_PYTHON=
```

### 4. 驗證配置

```bash
./start.sh help
```

查看 "Python 環境" 部分確認配置是否正確載入。

## 🔧 配置範例

### 完整的 config.env 範例

```bash
# FramePack 用戶配置文件

# =============================================================================
# 服務配置
# =============================================================================

USERNAME=admin
PASSWORD=123456
DEFAULT_PORT=7860
SECOND_PORT=7861
HOST=0.0.0.0

# =============================================================================
# Python 環境配置
# =============================================================================

# 本地虛擬環境路徑 (留空使用默認 .venv)
LOCAL_VENV_PATH=/home/user/.virtualenvs/FramePackB

# 本地 Python 解釋器路徑 (留空自動從虛擬環境推導)
LOCAL_PYTHON=

# =============================================================================
# 遠端開發配置
# =============================================================================

ENABLE_REMOTE=false
REMOTE_HOST=192.168.1.104
REMOTE_USER=jake
REMOTE_PYTHON=/home/jake/.virtualenvs/FramePackB/bin/python
REMOTE_PROJECT_DIR=/tmp/pycharm_project_662

# =============================================================================
# 高級配置
# =============================================================================

FORCE_EXTERNAL_ACCESS=false
CUDA_VISIBLE_DEVICES=
ENABLE_SECOND_GPU=
```

## 🛠️ 故障排除

### 問題 1: Python 解釋器不存在

**錯誤信息**: `Python 虛擬環境不存在: /path/to/python`

**解決方案**:
1. 檢查路徑是否正確
2. 確認虛擬環境已正確安裝
3. 檢查文件權限

### 問題 2: 虛擬環境路徑無效

**錯誤信息**: 找不到 Python 解釋器

**解決方案**:
1. 確認 `LOCAL_VENV_PATH` 指向正確的虛擬環境根目錄
2. 檢查 `{LOCAL_VENV_PATH}/bin/python` 是否存在
3. 嘗試直接使用 `LOCAL_PYTHON` 指定完整路徑

### 問題 3: 權限問題

**錯誤信息**: Permission denied

**解決方案**:
```bash
# 檢查文件權限
ls -la /path/to/your/venv/bin/python

# 如果需要，修復權限
chmod +x /path/to/your/venv/bin/python
```

## 💡 最佳實踐

### 1. 環境隔離
- 為每個項目使用獨立的虛擬環境
- 避免使用系統 Python

### 2. 路徑管理
- 使用絕對路徑避免相對路徑問題
- 定期檢查虛擬環境的有效性

### 3. 配置管理
- 將 `config.env` 加入 `.gitignore`
- 使用 `config.env.example` 作為範本
- 定期備份重要配置

### 4. 遠端開發
- 確保遠端和本地使用相同的 Python 版本
- 使用 SSH 密鑰認證提高安全性

## 🔮 進階功能

### 自動環境檢測

系統會自動檢測並顯示當前使用的 Python 環境：

```bash
./start.sh help
```

輸出範例：
```
Python 環境:
  Python 解釋器: /home/user/.virtualenvs/FramePackB/bin/python (配置指定)
```

### 配置驗證

啟動服務前會自動驗證 Python 環境：

```bash
./start.sh start
```

如果配置有問題，系統會提供詳細的錯誤信息和解決建議。

---

*這個功能讓 FramePack 的 Python 環境管理更加靈活和強大！* 🚀
