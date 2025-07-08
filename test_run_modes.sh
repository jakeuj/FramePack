#!/bin/bash

# FramePack 運行模式測試腳本
# 用於測試不同運行模式的行為

set -euo pipefail

echo "=== FramePack 運行模式測試 ==="
echo ""

# 測試 1: 自動檢測模式
echo "測試 1: 自動檢測模式"
echo "命令: ./start.sh help"
echo "預期: 根據當前環境自動選擇模式"
echo "---"
./start.sh help | grep -E "(運行模式已手動設定|檢測到|最終運行模式|模式:)"
echo ""

# 測試 2: 強制本地模式
echo "測試 2: 強制本地模式"
echo "命令: ./start.sh --local help"
echo "預期: 強制使用本地模式"
echo "---"
./start.sh --local help | grep -E "(強制使用本地模式|運行模式已手動設定|模式:)"
echo ""

# 測試 3: 強制遠端模式
echo "測試 3: 強制遠端模式"
echo "命令: ./start.sh --remote help"
echo "預期: 強制使用遠端模式"
echo "---"
./start.sh --remote help | grep -E "(強制使用遠端模式|運行模式已手動設定|模式:)"
echo ""

# 測試 4: 檢查配置文件中的 RUN_MODE 設定
echo "測試 4: 檢查配置文件設定"
echo "當前 config.env 中的 RUN_MODE 設定:"
echo "---"
if [[ -f "config.env" ]]; then
    grep "RUN_MODE" config.env || echo "未找到 RUN_MODE 設定"
else
    echo "config.env 文件不存在"
fi
echo ""

echo "=== 測試完成 ==="
echo ""
echo "使用說明:"
echo "1. 在 Mac 上遠端開發: ./start.sh start (自動使用遠端模式)"
echo "2. 在遠端伺服器上直接執行: ./start.sh start (自動切換到本地模式)"
echo "3. 強制本地模式: ./start.sh --local start"
echo "4. 強制遠端模式: ./start.sh --remote start"
