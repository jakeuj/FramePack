# 🔧 FramePack 配置系統改進

## 📋 改進概述

根據用戶需求，我們已經成功實現了虛擬環境路徑的可配置化功能，讓 `config.env` 機制更加完善和靈活。

## ✅ 已實現的功能

### 1. 新增配置選項

在 `config.env` 和 `config.env.example` 中新增了以下配置選項：

```bash
# =============================================================================
# Python 環境配置
# =============================================================================

# 本地虛擬環境路徑 (留空使用默認 .venv)
LOCAL_VENV_PATH=

# 本地 Python 解釋器路徑 (留空自動從虛擬環境推導)
LOCAL_PYTHON=

# =============================================================================
# 高級配置
# =============================================================================

# 強制外部訪問 (當 HOST=0.0.0.0 時在 macOS 上也允許外部訪問)
FORCE_EXTERNAL_ACCESS=false

# GPU 設備配置 (留空自動檢測)
CUDA_VISIBLE_DEVICES=

# 第二個 GPU 服務 (留空自動檢測)
ENABLE_SECOND_GPU=
```

### 2. 智能 Python 環境設置

實現了 `setup_python_env()` 函數，支援三種配置方式：

1. **直接指定 Python 解釋器** (`LOCAL_PYTHON`)
   ```bash
   LOCAL_PYTHON=/home/jake/.virtualenvs/FramePackB/bin/python
   ```

2. **指定虛擬環境目錄** (`LOCAL_VENV_PATH`)
   ```bash
   LOCAL_VENV_PATH=/home/jake/.virtualenvs/FramePackB
   ```

3. **使用默認設置** (兩者都留空)
   ```bash
   # 自動使用 ${WORK_DIR}/.venv/bin/python
   ```

### 3. 配置優先級

系統按以下優先級處理配置：

1. `LOCAL_PYTHON` (最高優先級)
2. `LOCAL_VENV_PATH` 
3. 默認 `.venv` 目錄

### 4. 增強的配置管理

- **配置載入**: 自動載入並驗證所有新配置選項
- **配置創建**: 互動式配置創建工具支援新選項
- **配置顯示**: `./start.sh help` 顯示當前 Python 環境配置
- **配置驗證**: 啟動前自動驗證 Python 環境有效性

## 🎯 使用範例

### 範例 1: 使用自定義虛擬環境

```bash
# config.env
LOCAL_VENV_PATH=/home/jake/.virtualenvs/FramePackB
LOCAL_PYTHON=
```

系統輸出：
```
[INFO] 使用配置的虛擬環境: /home/jake/.virtualenvs/FramePackB
Python 環境:
  虛擬環境: /home/jake/.virtualenvs/FramePackB (配置指定)
  Python 解釋器: /home/jake/.virtualenvs/FramePackB/bin/python
```

### 範例 2: 直接指定 Python 解釋器

```bash
# config.env
LOCAL_VENV_PATH=
LOCAL_PYTHON=/home/jake/.virtualenvs/FramePackB/bin/python
```

系統輸出：
```
[INFO] 使用配置的 Python 解釋器: /home/jake/.virtualenvs/FramePackB/bin/python
Python 環境:
  Python 解釋器: /home/jake/.virtualenvs/FramePackB/bin/python (配置指定)
```

### 範例 3: 使用默認設置

```bash
# config.env
LOCAL_VENV_PATH=
LOCAL_PYTHON=
```

系統輸出：
```
[INFO] 使用默認虛擬環境: /Users/user/project/.venv
Python 環境:
  虛擬環境: /Users/user/project/.venv (默認)
  Python 解釋器: /Users/user/project/.venv/bin/python
```

## 🔧 技術實現

### 1. 配置載入機制

修改了 `load_user_config()` 函數來支援新的配置選項：

```bash
case "$key" in
    LOCAL_VENV_PATH)
        LOCAL_VENV_PATH="$value"
        ;;
    LOCAL_PYTHON)
        LOCAL_PYTHON="$value"
        ;;
    FORCE_EXTERNAL_ACCESS)
        FORCE_EXTERNAL_ACCESS="$value"
        ;;
    # ... 其他選項
esac
```

### 2. Python 環境設置

新增 `setup_python_env()` 函數：

```bash
setup_python_env() {
    # 如果配置了 LOCAL_PYTHON，直接使用
    if [[ -n "$LOCAL_PYTHON" ]]; then
        PYTHON_BIN="$LOCAL_PYTHON"
        VENV_PATH=$(dirname "$(dirname "$LOCAL_PYTHON")")
        print_info "使用配置的 Python 解釋器: $PYTHON_BIN"
        return 0
    fi
    
    # 如果配置了 LOCAL_VENV_PATH，使用該虛擬環境
    if [[ -n "$LOCAL_VENV_PATH" ]]; then
        VENV_PATH="$LOCAL_VENV_PATH"
        PYTHON_BIN="${VENV_PATH}/bin/python"
        print_info "使用配置的虛擬環境: $VENV_PATH"
        return 0
    fi
    
    # 默認使用工作目錄下的 .venv
    VENV_PATH="${WORK_DIR}/.venv"
    PYTHON_BIN="${VENV_PATH}/bin/python"
    print_info "使用默認虛擬環境: $VENV_PATH"
}
```

### 3. 配置文件更新

更新了 `config.env.example` 和配置創建工具，包含：

- 詳細的使用說明
- 配置範例
- 安全提醒
- 最佳實踐建議

## 📁 修改的文件

### 1. `config.env.example`
- 新增 Python 環境配置部分
- 新增高級配置選項
- 更新使用說明和範例

### 2. `start.sh`
- 新增 `setup_python_env()` 函數
- 更新 `load_user_config()` 支援新選項
- 更新配置創建工具
- 增強幫助信息顯示

### 3. `config.env`
- 新增 Python 環境配置部分
- 新增高級配置選項
- 保持向後兼容性

### 4. 新增文檔
- `docs/python_env_config_guide.md` - 詳細使用指南
- `docs/config_env_improvements.md` - 改進總結

## 🎉 用戶體驗改進

### 1. 靈活性提升
- 支援任意位置的虛擬環境
- 支援直接指定 Python 解釋器
- 保持默認行為的向後兼容性

### 2. 配置透明度
- 啟動時顯示使用的 Python 環境
- 幫助信息顯示當前配置狀態
- 配置載入過程的詳細日誌

### 3. 錯誤處理
- 自動驗證 Python 環境有效性
- 提供詳細的錯誤信息
- 給出解決問題的建議

### 4. 開發體驗
- 支援多種開發環境設置
- 簡化遠端開發配置
- 統一的配置管理介面

## 🔮 未來擴展

可能的功能擴展：

1. **環境自動檢測**: 自動檢測常見的虛擬環境管理工具
2. **多環境支援**: 支援不同服務使用不同的 Python 環境
3. **環境健康檢查**: 定期檢查虛擬環境的完整性
4. **依賴管理**: 整合 pip/conda 依賴管理功能

---

*這個改進讓 FramePack 的環境配置更加靈活和用戶友好！* 🚀
