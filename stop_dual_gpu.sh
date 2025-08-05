#!/bin/bash
# FramePack 雙 GPU 停止腳本
# 停止 GPU 0 和 GPU 1 服務

# 設定腳本目錄
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印函數
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# 停止單個服務
stop_service() {
    local gpu_id=$1
    local port=$2
    local pid_file="pids/framepack_gpu${gpu_id}_${port}.pid"
    
    if [[ -f "$pid_file" ]]; then
        local pid
        pid=$(cat "$pid_file")
        
        if kill -0 "$pid" 2>/dev/null; then
            print_info "停止 GPU $gpu_id 服務 (PID: $pid)..."
            kill "$pid"
            
            # 等待進程結束
            local count=0
            while kill -0 "$pid" 2>/dev/null && [[ $count -lt 10 ]]; do
                sleep 1
                ((count++))
            done
            
            if kill -0 "$pid" 2>/dev/null; then
                print_warning "進程未正常結束，強制終止..."
                kill -9 "$pid"
            fi
            
            print_success "GPU $gpu_id 服務已停止"
        else
            print_warning "GPU $gpu_id 服務進程不存在 (PID: $pid)"
        fi
        
        rm -f "$pid_file"
    else
        print_warning "找不到 GPU $gpu_id 的 PID 文件"
    fi
}

# 檢查服務狀態
check_status() {
    local services=(
        "0:7860"
        "1:7861"
    )
    
    print_info "📊 服務狀態檢查："
    echo ""
    
    for service in "${services[@]}"; do
        local gpu_id="${service%:*}"
        local port="${service#*:}"
        local pid_file="pids/framepack_gpu${gpu_id}_${port}.pid"
        
        echo -n "  🖥️  GPU $gpu_id (端口 $port): "
        
        if [[ -f "$pid_file" ]]; then
            local pid
            pid=$(cat "$pid_file")
            
            if kill -0 "$pid" 2>/dev/null; then
                echo -e "${GREEN}運行中${NC} (PID: $pid)"
                
                # 檢查端口是否真的在監聽
                if lsof -i :$port >/dev/null 2>&1; then
                    echo "    📡 端口 $port 正在監聽"
                else
                    echo -e "    ${YELLOW}⚠️  端口 $port 未監聽${NC}"
                fi
            else
                echo -e "${RED}已停止${NC} (PID 文件存在但進程不存在)"
            fi
        else
            if lsof -i :$port >/dev/null 2>&1; then
                echo -e "${YELLOW}未知狀態${NC} (端口被佔用但無 PID 文件)"
            else
                echo -e "${RED}已停止${NC}"
            fi
        fi
    done
    
    echo ""
    
    # 檢查共享隊列狀態
    if [[ -d "queue_data" ]]; then
        print_info "📋 共享隊列狀態："
        if [[ -f "queue_data/queue.json" ]]; then
            local queue_size
            queue_size=$(jq length "queue_data/queue.json" 2>/dev/null || echo "未知")
            echo "  📄 隊列文件存在，項目數量: $queue_size"
        else
            echo "  📄 隊列文件不存在"
        fi
        
        local image_count
        image_count=$(find "queue_data/images" -name "*.pkl" 2>/dev/null | wc -l)
        echo "  🖼️  暫存圖片數量: $image_count"
    else
        echo "  📁 隊列目錄不存在"
    fi
}

# 清理隊列數據
clean_queue() {
    print_info "清理共享隊列數據..."
    
    if [[ -d "queue_data" ]]; then
        rm -rf queue_data/*
        print_success "隊列數據已清理"
    else
        print_info "隊列目錄不存在，無需清理"
    fi
}

# 主函數
main() {
    case "${1:-stop}" in
        "status")
            echo "🔍 FramePack 雙 GPU 服務狀態"
            echo "================================"
            check_status
            ;;
        "clean")
            echo "🧹 清理 FramePack 隊列數據"
            echo "================================"
            clean_queue
            ;;
        "stop"|"")
            echo "🛑 停止 FramePack 雙 GPU 服務"
            echo "================================"
            
            print_info "停止所有服務..."
            
            # 停止 GPU 0 服務
            stop_service 0 7860
            
            # 停止 GPU 1 服務
            stop_service 1 7861
            
            echo ""
            print_success "所有服務已停止"
            
            # 顯示最終狀態
            echo ""
            check_status
            ;;
        *)
            echo "用法: $0 [stop|status|clean]"
            echo ""
            echo "命令："
            echo "  stop   - 停止所有服務 (默認)"
            echo "  status - 檢查服務狀態"
            echo "  clean  - 清理隊列數據"
            exit 1
            ;;
    esac
}

# 執行主函數
main "$@"
