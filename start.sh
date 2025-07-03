#!/bin/bash

# 這裡要改成絕對路徑
cd ~/FramePack

# 這裡要改成虛擬環境路徑
PYTHON_BIN="./.venv312/bin/python"
SCRIPT="demo_gradio_f1_refactored.py"

# 帳號密碼
USERNAME="admin"
PASSWORD="123456"

# 函式：停止已執行的特定實例
stop_if_running() {
    GPU_ID=$1
    PORT=$2
    NAME=$3
    PWD=$4
    PIDS=$(ps aux | grep "$SCRIPT --port $PORT" | grep -v grep | awk '{print $2}')
    if [ -n "$PIDS" ]; then
        echo "🛑 偵測到 GPU $GPU_ID / Port $PORT 已在執行，正在終止：$PIDS"
        kill $PIDS
        sleep 1
    fi
}

# 函式：啟動指定 GPU 和 Port
start_instance() {
    GPU_ID=$1
    PORT=$2
    NAME=$3
    PWD=$4
    LOGFILE="output_${PORT}.log"

    echo "🚀 啟動 GPU $GPU_ID / Port $PORT"
    nohup env CUDA_VISIBLE_DEVICES=$GPU_ID $PYTHON_BIN $SCRIPT --port $PORT --username $NAME --password $PWD > $LOGFILE >
    echo "✅ GPU $GPU_ID 實例已啟動，PID=$!"
}

# === 執行重啟程序 ===
stop_if_running 0 7860 $USERNAME $PASSWORD
start_instance 0 7860 $USERNAME $PASSWORD

# 如果有第二張顯卡
# stop_if_running 1 7861 $USERNAME $PASSWORD
# start_instance 1 7861 $USERNAME $PASSWORD

echo "🔁 所有服務已強制重啟完成"