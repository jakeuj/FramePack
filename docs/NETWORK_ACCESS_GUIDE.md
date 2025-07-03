# 手機訪問 FramePack 服務指南

## 🎯 問題解決

您原本設定服務監聽 `0.0.0.0` 以便手機訪問，重構後的腳本已經正確配置了這個功能。

## 🔧 配置確認

重構後的 `start.sh` 腳本已經包含以下配置：

```bash
HOST="0.0.0.0"  # 監聽所有網路介面，允許外部訪問
```

這個設定會傳遞給 Gradio 應用的 `--server` 參數。

## 📱 手機訪問步驟

### 1. 啟動服務
```bash
./start.sh start
```

### 2. 獲取訪問地址
啟動後，腳本會自動偵測 GPU 並顯示：
```
自動偵測 GPU 設備...
檢測到 2 張 NVIDIA GPU
GPU 0: NVIDIA GeForce RTX 4090, 24564 MiB
GPU 1: NVIDIA GeForce RTX 4080, 16376 MiB
自動啟用第二個 GPU 服務

訪問地址:
  主服務 (GPU 0): http://localhost:7860 (本機)
  主服務 (GPU 0): http://192.168.1.107:7860 (外部訪問)
  第二服務 (GPU 1): http://localhost:7861 (本機)
  第二服務 (GPU 1): http://192.168.1.107:7861 (外部訪問)
```

### 3. 手機訪問
根據您的 GPU 配置，在手機瀏覽器中輸入：

**單 GPU 或 CPU 模式：**
```
http://192.168.1.107:7860
```

**多 GPU 模式（有兩個服務）：**
```
http://192.168.1.107:7860  # 主服務 (GPU 0)
http://192.168.1.107:7861  # 第二服務 (GPU 1)
```
（請替換為您實際的 IP 地址）

### 4. 登錄
- 用戶名: `admin`
- 密碼: `123456`

## 🔍 故障排除

### 檢查服務狀態
```bash
./start.sh status
```

### 檢查 GPU 配置
```bash
./start.sh gpu
```

這會顯示：
- 偵測到的 GPU 數量和型號
- 每個 GPU 的記憶體大小
- 第二個 GPU 服務是否啟用

### 檢查網路監聽
```bash
# Ubuntu/Linux
ss -tuln | grep :7860

# 或使用 netstat
netstat -tuln | grep :7860
```

應該看到類似輸出：
```
tcp   LISTEN   0   128   0.0.0.0:7860   0.0.0.0:*
```

### 檢查防火牆
```bash
# 檢查 UFW 狀態
sudo ufw status

# 如果防火牆啟用，開放端口
sudo ufw allow 7860
```

### 檢查本機 IP
```bash
# 方法 1
hostname -I

# 方法 2
ip addr show | grep inet

# 方法 3
ifconfig | grep inet
```

## 🌐 網路要求

1. **同一網路**: 手機和電腦必須連接到同一個 WiFi 網路
2. **路由器設定**: 確保路由器允許內網設備互相通信
3. **防火牆**: 確保防火牆不阻擋 7860 端口

## 🚀 快速測試

### 從電腦測試
```bash
# 測試本機訪問
curl http://localhost:7860

# 測試外部訪問
curl http://192.168.1.107:7860
```

### 從手機測試
1. 打開手機瀏覽器
2. 輸入 `http://您的IP:7860`
3. 應該看到 FramePack 登錄頁面

## 📋 完整檢查清單

- [ ] 服務已啟動 (`./start.sh start`)
- [ ] 服務監聽 0.0.0.0 (`ss -tuln | grep :7860`)
- [ ] 獲取正確的本機 IP (`hostname -I`)
- [ ] 防火牆允許端口 7860
- [ ] 手機和電腦在同一 WiFi
- [ ] 手機瀏覽器可以訪問服務

## 🔧 進階配置

### 修改監聽地址
如果需要修改監聽地址，編輯 `start.sh`：

```bash
# 只允許本機訪問
HOST="127.0.0.1"

# 允許所有外部訪問（默認）
HOST="0.0.0.0"

# 指定特定網路介面
HOST="192.168.1.107"
```

### 修改端口
```bash
DEFAULT_PORT=7860  # 主服務端口
SECOND_PORT=7861   # 第二服務端口（如果啟用）
```

## 📞 技術支援

如果仍然無法從手機訪問，請檢查：

1. **網路連接**: `ping 電腦IP` (從手機的終端應用)
2. **服務日誌**: `tail -f logs/framepack_7860.log`
3. **系統日誌**: `journalctl -f` (Ubuntu)

## 🎉 成功標誌

當一切正常時，您應該能夠：
- 從電腦訪問 `http://localhost:7860`
- 從手機訪問 `http://您的IP:7860`
- 看到相同的 FramePack 界面
- 正常登錄和使用所有功能
