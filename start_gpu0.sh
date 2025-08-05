#!/bin/bash
# FramePack GPU 0 啟動腳本
# 專門用於在 GPU 0 上啟動服務

# 設定腳本目錄
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 設定 GPU 環境變數
export CUDA_VISIBLE_DEVICES=0
export PYTORCH_ENABLE_MPS_FALLBACK=1
export TOKENIZERS_PARALLELISM=false

# 設定服務參數
PORT=7860
USERNAME="admin"
PASSWORD="123456"
HOST="0.0.0.0"

# Python 環境設定
PYTHON_BIN="/home/jake/.virtualenvs/FramePack/bin/python"
SCRIPT_NAME="main.py"

# 檢查 Python 環境
if ! command -v "$PYTHON_BIN" &> /dev/null; then
    echo "❌ Python 未找到，請確認 Python 環境已正確安裝"
    echo "嘗試的路徑: $PYTHON_BIN"
    exit 1
fi

# 檢查主程式文件
if [[ ! -f "$SCRIPT_NAME" ]]; then
    echo "❌ 找不到 $SCRIPT_NAME"
    exit 1
fi

# 創建必要的目錄
mkdir -p logs
mkdir -p pids
mkdir -p queue_data

# 檢查端口是否被佔用
if lsof -i :$PORT >/dev/null 2>&1; then
    echo "❌ 端口 $PORT 已被佔用"
    echo "請使用以下命令查看佔用進程："
    echo "lsof -i :$PORT"
    exit 1
fi

echo "🚀 啟動 FramePack GPU 0 服務..."
echo "📍 GPU: 0"
echo "📍 端口: $PORT"
echo "📍 用戶名: $USERNAME"
echo "📍 密碼: $PASSWORD"

# 啟動服務
nohup "$PYTHON_BIN" "$SCRIPT_NAME" \
    --port "$PORT" \
    --server "$HOST" \
    --username "$USERNAME" \
    --password "$PASSWORD" \
    > "logs/framepack_gpu0_${PORT}.log" 2>&1 &

PID=$!

# 保存 PID
echo "$PID" > "pids/framepack_gpu0_${PORT}.pid"

echo "✅ GPU 0 服務已啟動"
echo "📋 PID: $PID"
echo "📋 日誌: logs/framepack_gpu0_${PORT}.log"
echo "📋 訪問地址: http://localhost:$PORT"
echo ""
echo "💡 使用以下命令查看日誌："
echo "tail -f logs/framepack_gpu0_${PORT}.log"
echo ""
echo "💡 使用以下命令停止服務："
echo "kill $PID"
