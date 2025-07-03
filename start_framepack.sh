#!/bin/bash
"""
FramePack 啟動腳本
確保正確的環境設置並啟動應用
"""

echo "🚀 FramePack 啟動腳本"
echo "====================="

# 設置 MPS 兼容性環境變數
export PYTORCH_ENABLE_MPS_FALLBACK=1
export TOKENIZERS_PARALLELISM=false

echo "✅ 環境變數已設置:"
echo "   PYTORCH_ENABLE_MPS_FALLBACK=1"
echo "   TOKENIZERS_PARALLELISM=false"

# 檢查虛擬環境
if [ -d ".venv" ]; then
    echo "✅ 發現虛擬環境，正在激活..."
    source .venv/bin/activate
else
    echo "⚠️ 未發現虛擬環境，使用系統 Python"
fi

# 檢查 Python 版本
echo "🐍 Python 版本: $(python --version)"

# 顯示選項
echo ""
echo "請選擇要啟動的版本:"
echo "1) FramePack 基礎版本"
echo "2) FramePack F1 版本 (包含認證和高級功能)"
echo "3) 退出"

read -p "請輸入選項 (1-3): " choice

case $choice in
    1)
        echo "🎬 啟動 FramePack 基礎版本..."
        python demo_gradio_refactored.py
        ;;
    2)
        echo "🎬 啟動 FramePack F1 版本..."
        echo "💡 提示: 默認用戶名/密碼為 admin/123456"
        echo "💡 可以使用 --no-auth 參數禁用認證"
        python demo_gradio_f1_refactored.py
        ;;
    3)
        echo "👋 再見！"
        exit 0
        ;;
    *)
        echo "❌ 無效選項"
        exit 1
        ;;
esac
