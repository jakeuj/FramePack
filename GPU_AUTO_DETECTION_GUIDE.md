# GPU 自動偵測功能指南

## 🎯 功能概述

FramePack 服務管理腳本現在支援智能 GPU 自動偵測，會根據系統中的 NVIDIA GPU 數量自動配置服務：

- **0 張 GPU**: CPU 模式，單一服務 (端口 7860)
- **1 張 GPU**: 單 GPU 模式，單一服務 (端口 7860)
- **2+ 張 GPU**: 多 GPU 模式，雙服務 (端口 7860 + 7861)

## 🔍 自動偵測邏輯

### 偵測流程

1. **檢查 nvidia-smi**: 確認 NVIDIA 驅動是否安裝
2. **獲取 GPU 列表**: 查詢所有可用的 GPU 設備
3. **分析 GPU 信息**: 獲取每個 GPU 的型號和記憶體
4. **自動配置服務**: 根據 GPU 數量決定啟動的服務數量

### 配置決策表

| 偵測結果 | 主服務 (7860) | 第二服務 (7861) | 說明 |
|----------|---------------|-----------------|------|
| 無 nvidia-smi | ✅ 設備 0 (CPU) | ❌ | CPU 模式 |
| 0 張 GPU | ✅ 設備 0 (CPU) | ❌ | CPU 模式 |
| 1 張 GPU | ✅ GPU 0 | ❌ | 單 GPU 模式 |
| 2 張 GPU | ✅ GPU 0 | ✅ GPU 1 | 雙 GPU 並行 |
| 3+ 張 GPU | ✅ GPU 0 | ✅ GPU 1 | 使用前兩張 GPU |

## 🚀 使用方法

### 查看 GPU 信息
```bash
./start.sh gpu
```

**輸出示例 (雙 GPU 系統):**
```
GPU 信息檢查...
自動偵測 GPU 設備...
檢測到 2 張 NVIDIA GPU
GPU 0: NVIDIA GeForce RTX 4090, 24564 MiB
GPU 1: NVIDIA GeForce RTX 4080, 16376 MiB
GPU 配置: 0 1
第二個 GPU 服務: 自動啟用

詳細 GPU 信息:
+-----------------------------------------------------------------------------+
| NVIDIA-SMI 535.86.10    Driver Version: 535.86.10    CUDA Version: 12.2     |
|-------------------------------+----------------------+----------------------+
| GPU  Name        Persistence-M| Bus-Id        Disp.A | Volatile Uncorr. ECC |
| Fan  Temp  Perf  Pwr:Usage/Cap|         Memory-Usage | GPU-Util  Compute M. |
|                               |                      |               MIG M. |
|===============================+======================+======================|
|   0  NVIDIA GeForce ...  Off  | 00000000:01:00.0  On |                  N/A |
| 30%   45C    P8    25W / 450W |    500MiB / 24564MiB |      0%      Default |
|                               |                      |                  N/A |
+-------------------------------+----------------------+----------------------+
|   1  NVIDIA GeForce ...  Off  | 00000000:02:00.0 Off |                  N/A |
| 30%   42C    P8    20W / 320W |      2MiB / 16376MiB |      0%      Default |
|                               |                      |                  N/A |
+-------------------------------+----------------------+----------------------+
```

### 啟動服務
```bash
./start.sh start
```

**輸出示例:**
```
自動偵測 GPU 設備...
檢測到 2 張 NVIDIA GPU
GPU 0: NVIDIA GeForce RTX 4090, 24564 MiB
GPU 1: NVIDIA GeForce RTX 4080, 16376 MiB
自動啟用第二個 GPU 服務

啟動主要服務 (GPU 0, 端口 7860)...
啟動第二個 GPU 服務...
啟動第二個服務 (GPU 1, 端口 7861)...

訪問地址:
  主服務 (GPU 0): http://localhost:7860 (本機)
  主服務 (GPU 0): http://192.168.1.107:7860 (外部訪問)
  第二服務 (GPU 1): http://localhost:7861 (本機)
  第二服務 (GPU 1): http://192.168.1.107:7861 (外部訪問)
```

## ⚙️ 手動配置

### 覆蓋自動偵測

如果需要手動控制 GPU 配置，可以編輯 `start.sh`：

```bash
# 強制使用特定 GPU
GPU_DEVICES=(0 2)  # 使用 GPU 0 和 GPU 2，跳過 GPU 1
ENABLE_SECOND_GPU=true

# 強制單 GPU 模式（即使有多張 GPU）
GPU_DEVICES=(1)  # 只使用 GPU 1
ENABLE_SECOND_GPU=false

# 強制 CPU 模式
GPU_DEVICES=(0)  # 使用設備 0（通常是 CPU）
ENABLE_SECOND_GPU=false
```

### 重新啟用自動偵測

要恢復自動偵測，將配置改回：

```bash
# GPU 配置 - 自動偵測
GPU_DEVICES=()  # 空陣列，將自動偵測
ENABLE_SECOND_GPU=false  # 將根據 GPU 數量自動設定
```

## 🔧 故障排除

### 常見問題

**1. 偵測不到 GPU**
```bash
# 檢查 NVIDIA 驅動
nvidia-smi

# 檢查 CUDA 安裝
nvcc --version

# 檢查 GPU 可見性
echo $CUDA_VISIBLE_DEVICES
```

**2. 第二個服務未啟動**
```bash
# 檢查 GPU 偵測結果
./start.sh gpu

# 檢查服務狀態
./start.sh status

# 查看日誌
tail -f logs/framepack_7861.log
```

**3. GPU 記憶體不足**
```bash
# 檢查 GPU 記憶體使用
nvidia-smi

# 手動指定較小的 GPU
# 編輯 start.sh，設定 GPU_DEVICES=(1) 使用第二張 GPU
```

### 日誌檢查

```bash
# 主服務日誌
tail -f logs/framepack_7860.log

# 第二服務日誌（如果啟用）
tail -f logs/framepack_7861.log

# 系統日誌
journalctl -f | grep framepack
```

## 📊 性能優化

### 多 GPU 負載均衡

當啟用雙 GPU 服務時：

1. **主服務 (7860)**: 使用 GPU 0，處理主要請求
2. **第二服務 (7861)**: 使用 GPU 1，分擔負載

### 使用建議

- **開發測試**: 使用單 GPU 模式節省資源
- **生產環境**: 使用多 GPU 模式提高並發處理能力
- **演示展示**: 可以同時展示兩個不同的模型或配置

## 🎯 最佳實踐

1. **定期檢查**: 使用 `./start.sh gpu` 確認 GPU 狀態
2. **監控資源**: 使用 `./start.sh status` 監控服務狀態
3. **日誌管理**: 定期清理日誌文件避免磁碟空間不足
4. **溫度監控**: 注意 GPU 溫度，避免過熱
5. **記憶體管理**: 監控 GPU 記憶體使用，避免 OOM 錯誤

## 🔄 版本更新

此功能在以下版本中引入：
- **v2.0**: 基礎 GPU 自動偵測
- **v2.1**: 智能第二服務啟用
- **v2.2**: 詳細 GPU 信息顯示

如需更新到最新版本，請重新下載 `start.sh` 腳本。
