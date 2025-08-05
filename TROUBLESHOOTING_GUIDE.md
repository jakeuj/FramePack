# 🔧 FramePack 雙 GPU 故障排除指南

## 🚨 常見問題及解決方案

### 1. 點擊「開始處理隊列」顯示 Error

**問題描述：** 用戶點擊「開始處理隊列」按鈕後，界面顯示錯誤信息。

**可能原因：**
- 共享隊列模式下的方法不兼容
- 缺少必要的屬性或方法

**解決方案：**
```bash
# 1. 檢查服務日誌
ssh jake@211.20.19.206 -p 10222 "cd /tmp/pycharm_project_23 && tail -20 logs/framepack_gpu0_7860.log"

# 2. 重啟服務
ssh jake@211.20.19.206 -p 10222 "cd /tmp/pycharm_project_23 && ./stop_dual_gpu.sh && ./start_dual_gpu.sh"

# 3. 測試隊列功能
ssh jake@211.20.19.206 -p 10222 "cd /tmp/pycharm_project_23 && /home/jake/.virtualenvs/FramePack/bin/python test_queue_processing.py"
```

**狀態：** ✅ 已修復 - 更新了所有隊列方法以支援共享隊列模式

---

### 2. 服務啟動失敗

**問題描述：** GPU 服務無法啟動或啟動後立即停止。

**診斷步驟：**
```bash
# 檢查服務狀態
ssh jake@211.20.19.206 -p 10222 "cd /tmp/pycharm_project_23 && ./stop_dual_gpu.sh status"

# 檢查端口佔用
ssh jake@211.20.19.206 -p 10222 "lsof -i :7860 && lsof -i :7861"

# 檢查 GPU 狀態
ssh jake@211.20.19.206 -p 10222 "nvidia-smi"
```

**解決方案：**
```bash
# 1. 強制停止所有服務
ssh jake@211.20.19.206 -p 10222 "cd /tmp/pycharm_project_23 && ./stop_dual_gpu.sh"

# 2. 清理進程（如果需要）
ssh jake@211.20.19.206 -p 10222 "pkill -f 'main.py'"

# 3. 重新啟動
ssh jake@211.20.19.206 -p 10222 "cd /tmp/pycharm_project_23 && ./start_dual_gpu.sh"
```

---

### 3. 隊列不同步

**問題描述：** 兩個服務看到不同的隊列狀態。

**診斷：**
```bash
# 檢查隊列文件
ssh jake@211.20.19.206 -p 10222 "cd /tmp/pycharm_project_23 && cat queue_data/queue.json"

# 測試隊列同步
ssh jake@211.20.19.206 -p 10222 "cd /tmp/pycharm_project_23 && /home/jake/.virtualenvs/FramePack/bin/python test_shared_queue.py"
```

**解決方案：**
```bash
# 清理隊列數據
ssh jake@211.20.19.206 -p 10222 "cd /tmp/pycharm_project_23 && ./stop_dual_gpu.sh clean"

# 重啟服務
ssh jake@211.20.19.206 -p 10222 "cd /tmp/pycharm_project_23 && ./start_dual_gpu.sh"
```

---

### 4. GPU 記憶體不足

**問題描述：** 處理過程中出現 CUDA out of memory 錯誤。

**診斷：**
```bash
# 檢查 GPU 記憶體使用
ssh jake@211.20.19.206 -p 10222 "nvidia-smi"

# 檢查正在運行的進程
ssh jake@211.20.19.206 -p 10222 "nvidia-smi pmon"
```

**解決方案：**
```bash
# 1. 重啟服務釋放記憶體
ssh jake@211.20.19.206 -p 10222 "cd /tmp/pycharm_project_23 && ./stop_dual_gpu.sh && ./start_dual_gpu.sh"

# 2. 如果問題持續，檢查是否有其他程序佔用 GPU
ssh jake@211.20.19.206 -p 10222 "fuser -v /dev/nvidia*"
```

---

### 5. 網路連接問題

**問題描述：** 無法訪問服務網頁界面。

**診斷：**
```bash
# 檢查服務是否運行
ssh jake@211.20.19.206 -p 10222 "cd /tmp/pycharm_project_23 && ./stop_dual_gpu.sh status"

# 測試本地連接
ssh jake@211.20.19.206 -p 10222 "curl -s -o /dev/null -w '%{http_code}' http://localhost:7860"
```

**解決方案：**
- 確認服務正在運行
- 檢查防火牆設置
- 確認端口 7860 和 7861 沒有被其他程序佔用

---

## 🛠️ 維護命令

### 日常監控
```bash
# 檢查服務狀態
ssh jake@211.20.19.206 -p 10222 "cd /tmp/pycharm_project_23 && ./stop_dual_gpu.sh status"

# 查看實時日誌
ssh jake@211.20.19.206 -p 10222 "cd /tmp/pycharm_project_23 && tail -f logs/framepack_gpu*.log"

# 檢查 GPU 使用情況
ssh jake@211.20.19.206 -p 10222 "watch -n 1 nvidia-smi"
```

### 清理和重置
```bash
# 清理隊列數據
ssh jake@211.20.19.206 -p 10222 "cd /tmp/pycharm_project_23 && ./stop_dual_gpu.sh clean"

# 清理日誌文件
ssh jake@211.20.19.206 -p 10222 "cd /tmp/pycharm_project_23 && rm -f logs/*.log"

# 完全重置
ssh jake@211.20.19.206 -p 10222 "cd /tmp/pycharm_project_23 && ./stop_dual_gpu.sh && rm -rf queue_data logs pids && ./start_dual_gpu.sh"
```

### 性能優化
```bash
# 檢查系統資源
ssh jake@211.20.19.206 -p 10222 "htop"

# 檢查磁碟空間
ssh jake@211.20.19.206 -p 10222 "df -h"

# 檢查記憶體使用
ssh jake@211.20.19.206 -p 10222 "free -h"
```

---

## 📊 測試腳本

### 功能測試
```bash
# 基礎功能測試
ssh jake@211.20.19.206 -p 10222 "cd /tmp/pycharm_project_23 && /home/jake/.virtualenvs/FramePack/bin/python test_simple_queue.py"

# 共享隊列測試
ssh jake@211.20.19.206 -p 10222 "cd /tmp/pycharm_project_23 && /home/jake/.virtualenvs/FramePack/bin/python test_shared_queue.py"

# 隊列處理測試
ssh jake@211.20.19.206 -p 10222 "cd /tmp/pycharm_project_23 && /home/jake/.virtualenvs/FramePack/bin/python test_queue_processing.py"

# 集成測試
ssh jake@211.20.19.206 -p 10222 "cd /tmp/pycharm_project_23 && /home/jake/.virtualenvs/FramePack/bin/python test_dual_gpu_integration.py"
```

---

## 🚨 緊急恢復

如果系統完全無法使用，請按以下步驟恢復：

```bash
# 1. 停止所有服務
ssh jake@211.20.19.206 -p 10222 "cd /tmp/pycharm_project_23 && ./stop_dual_gpu.sh"

# 2. 強制終止相關進程
ssh jake@211.20.19.206 -p 10222 "pkill -f 'main.py' || true"

# 3. 清理所有數據
ssh jake@211.20.19.206 -p 10222 "cd /tmp/pycharm_project_23 && rm -rf queue_data logs pids"

# 4. 重新啟動
ssh jake@211.20.19.206 -p 10222 "cd /tmp/pycharm_project_23 && ./start_dual_gpu.sh"

# 5. 驗證功能
ssh jake@211.20.19.206 -p 10222 "cd /tmp/pycharm_project_23 && /home/jake/.virtualenvs/FramePack/bin/python test_dual_gpu_integration.py"
```

---

## 📞 支援信息

- **服務地址**: http://211.20.19.206:7860 和 http://211.20.19.206:7861
- **登錄信息**: 用戶名 `admin`，密碼 `123456`
- **日誌位置**: `/tmp/pycharm_project_23/logs/`
- **隊列數據**: `/tmp/pycharm_project_23/queue_data/`

如果問題仍然存在，請提供具體的錯誤信息和日誌內容以便進一步診斷。
