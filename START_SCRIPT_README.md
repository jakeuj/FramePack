# FramePack Service Manager

重構後的 `start.sh` 腳本，專為 Ubuntu 24.04 設計，提供完整的服務管理功能。

## 功能特色

- ✅ **Ubuntu 24.04 兼容性**: 針對 Ubuntu 24.04 優化
- ✅ **完整服務管理**: 支援 start、stop、restart、status 命令
- ✅ **智能進程管理**: 使用 PID 文件和鎖文件確保服務穩定性
- ✅ **優雅停止**: 先嘗試 SIGTERM，超時後使用 SIGKILL
- ✅ **詳細狀態監控**: 顯示 CPU、記憶體使用率和 GPU 狀態
- ✅ **多 GPU 支援**: 可配置多個 GPU 實例
- ✅ **完整日誌記錄**: 每個服務實例獨立日誌
- ✅ **錯誤處理**: 完善的錯誤檢查和恢復機制

## 使用方法

### 基本命令

```bash
# 啟動服務
./start.sh start

# 停止服務
./start.sh stop

# 重啟服務
./start.sh restart

# 檢查狀態
./start.sh status

# 顯示幫助
./start.sh help
```

### 默認配置

- **監聽地址**: 0.0.0.0 (允許外部訪問)
- **主服務端口**: 7860
- **第二服務端口**: 7861 (可選)
- **默認用戶名**: admin
- **默認密碼**: 123456
- **虛擬環境**: `./.venv/bin/python`
- **腳本文件**: `demo_gradio_f1_refactored.py`

## 配置選項

在腳本頂部的配置區域可以修改以下設置：

```bash
# 網路配置
HOST="0.0.0.0"  # 監聽所有網路介面，允許外部訪問 (對應 --server 參數)

# GPU 配置
GPU_DEVICES=(0)  # 可以添加更多 GPU: (0 1 2)
ENABLE_SECOND_GPU=false  # 設為 true 啟用第二個 GPU

# 端口配置
DEFAULT_PORT=7860
SECOND_PORT=7861

# 認證配置
USERNAME="admin"
PASSWORD="123456"
```

## 外部訪問設定

### 手機/平板訪問

腳本默認設定為 `HOST="0.0.0.0"`，允許從手機、平板等外部設備訪問：

1. **啟動服務後**，腳本會自動顯示本機 IP 地址
2. **手機訪問**: 使用 `http://本機IP:7860`
3. **例如**: `http://192.168.1.100:7860`

> **說明**: `0.0.0.0` 表示監聽所有網路介面，包括 WiFi、有線網路等，這樣同一網路內的其他設備（如手機）就可以通過電腦的 IP 地址訪問服務。

### 防火牆設定

Ubuntu 24.04 可能需要開放端口：

```bash
# 檢查防火牆狀態
sudo ufw status

# 開放端口 (如果防火牆啟用)
sudo ufw allow 7860
sudo ufw allow 7861  # 如果使用第二個服務
```

### 網路故障排除

```bash
# 檢查服務是否正確監聽
ss -tuln | grep :7860

# 檢查本機 IP
hostname -I

# 測試連接 (從其他設備)
curl http://本機IP:7860
```

## 文件結構

腳本會自動創建以下目錄結構：

```
FramePackB/
├── pids/           # PID 文件
├── logs/           # 日誌文件
├── locks/          # 鎖文件
└── start.sh        # 服務管理腳本
```

## 狀態監控

`status` 命令會顯示：

- 服務運行狀態 (PID)
- CPU 使用率
- 記憶體使用率
- 服務啟動時間
- 端口監聽狀態
- 系統記憶體使用情況
- GPU 使用情況 (如果有 NVIDIA GPU)

## 日誌管理

每個服務實例都有獨立的日誌文件：

- 主服務: `logs/framepack_7860.log`
- 第二服務: `logs/framepack_7861.log`

## 安全特性

- 檢查是否以 root 身份運行 (不建議)
- 使用鎖文件防止重複啟動
- 優雅的信號處理 (SIGINT, SIGTERM)
- 端口佔用檢查
- 進程存在性驗證

## 故障排除

### 常見問題

1. **虛擬環境不存在**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **端口被佔用**
   ```bash
   # 檢查端口使用情況
   ss -tuln | grep :7860
   
   # 或使用 netstat
   netstat -tuln | grep :7860
   ```

3. **權限問題**
   ```bash
   chmod +x start.sh
   ```

4. **GPU 不可用**
   - 腳本會自動檢測並切換到 CPU 模式
   - 檢查 NVIDIA 驅動: `nvidia-smi`

5. **手機無法訪問**
   ```bash
   # 確認服務監聽 0.0.0.0
   ss -tuln | grep :7860

   # 檢查防火牆
   sudo ufw status

   # 確認手機和電腦在同一網路
   ping 手機IP  # 從電腦測試
   ```

6. **網路連接問題**
   - 確保手機和電腦連接同一 WiFi
   - 檢查路由器是否阻擋內網通信
   - 嘗試關閉電腦防火牆測試

### 日誌檢查

```bash
# 查看最新日誌
tail -f logs/framepack_7860.log

# 查看錯誤日誌
grep -i error logs/framepack_7860.log
```

## 與原版本的差異

| 功能 | 原版本 | 新版本 |
|------|--------|--------|
| 命令參數 | 無 | start/stop/restart/status |
| 進程管理 | 簡單 kill | PID 文件 + 優雅停止 |
| 狀態監控 | 無 | 詳細狀態信息 |
| 錯誤處理 | 基本 | 完善的錯誤檢查 |
| 日誌管理 | 單一文件 | 分離日誌文件 |
| 鎖機制 | 無 | 防重複啟動 |
| Ubuntu 兼容 | 通用 | Ubuntu 24.04 優化 |

## 系統要求

- Ubuntu 24.04 LTS
- Python 3.8+
- Bash 4.0+
- 可選: NVIDIA GPU + 驅動

## 授權

與主項目相同的授權條款。
