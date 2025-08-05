#!/bin/bash
# FramePack 雙 GPU 啟動腳本
# 同時啟動 GPU 0 和 GPU 1 服務，共享隊列

# 設定腳本目錄
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 讀取配置文件
CONFIG_FILE="config.env"
if [[ -f "$CONFIG_FILE" ]]; then
    source "$CONFIG_FILE"
fi

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

# 檢查 GPU
check_gpu() {
    if command -v nvidia-smi >/dev/null 2>&1; then
        local gpu_count
        gpu_count=$(nvidia-smi --query-gpu=index --format=csv,noheader,nounits | wc -l)
        
        if [[ $gpu_count -lt 2 ]]; then
            print_warning "檢測到 $gpu_count 張 GPU，建議至少有 2 張 GPU 以發揮雙 GPU 模式的優勢"
            read -p "是否繼續？(y/N): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                exit 1
            fi
        else
            print_success "檢測到 $gpu_count 張 GPU，適合雙 GPU 模式"
        fi
    else
        print_warning "無法檢測 GPU 信息，將繼續啟動"
    fi
}

# 檢查端口
check_ports() {
    local ports=(7860 7861)
    local occupied_ports=()
    
    for port in "${ports[@]}"; do
        if lsof -i :$port >/dev/null 2>&1; then
            occupied_ports+=($port)
        fi
    done
    
    if [[ ${#occupied_ports[@]} -gt 0 ]]; then
        print_error "以下端口已被佔用: ${occupied_ports[*]}"
        print_info "請使用以下命令查看佔用進程："
        for port in "${occupied_ports[@]}"; do
            echo "  lsof -i :$port"
        done
        exit 1
    fi
}

# 創建必要目錄
create_directories() {
    mkdir -p logs pids queue_data
    print_info "已創建必要目錄"
}

# 啟動服務
start_services() {
    print_info "啟動雙 GPU 服務..."
    
    # 啟動 GPU 0 服務
    print_info "啟動 GPU 0 服務 (端口 7860)..."
    if [[ -f "start_gpu0.sh" ]]; then
        chmod +x start_gpu0.sh
        ./start_gpu0.sh
        if [[ $? -eq 0 ]]; then
            print_success "GPU 0 服務啟動成功"
        else
            print_error "GPU 0 服務啟動失敗"
            return 1
        fi
    else
        print_error "找不到 start_gpu0.sh"
        return 1
    fi
    
    # 等待一下讓第一個服務完全啟動
    sleep 3
    
    # 啟動 GPU 1 服務
    print_info "啟動 GPU 1 服務 (端口 7861)..."
    if [[ -f "start_gpu1.sh" ]]; then
        chmod +x start_gpu1.sh
        ./start_gpu1.sh
        if [[ $? -eq 0 ]]; then
            print_success "GPU 1 服務啟動成功"
        else
            print_error "GPU 1 服務啟動失敗"
            return 1
        fi
    else
        print_error "找不到 start_gpu1.sh"
        return 1
    fi
}

# 顯示服務信息
show_service_info() {
    # 從配置文件讀取端口和登錄信息
    local gpu0_port=${DEFAULT_PORT:-7860}
    local gpu1_port=${SECOND_PORT:-7861}
    local display_username=${USERNAME:-"admin"}
    local display_password=${PASSWORD:-"123456"}

    echo ""
    print_success "🎉 雙 GPU 服務啟動完成！"
    echo ""
    print_info "📋 服務信息："
    echo "  🖥️  GPU 0 服務: http://localhost:$gpu0_port"
    echo "  🖥️  GPU 1 服務: http://localhost:$gpu1_port"
    echo ""
    print_info "🔑 登錄信息："
    echo "  👤 用戶名: $display_username"
    echo "  🔒 密碼: $display_password"
    echo ""
    print_info "📊 隊列共享："
    echo "  ✅ 兩個服務共享同一個處理隊列"
    echo "  ✅ 上傳到任一服務的圖片都會進入共享隊列"
    echo "  ✅ 兩個 GPU 會自動分配處理隊列中的任務"
    echo ""
    print_info "📝 日誌文件："
    echo "  📄 GPU 0: logs/framepack_gpu0_7860.log"
    echo "  📄 GPU 1: logs/framepack_gpu1_7861.log"
    echo ""
    print_info "🛠️  管理命令："
    echo "  📊 查看狀態: ./stop_dual_gpu.sh status"
    echo "  🛑 停止服務: ./stop_dual_gpu.sh"
    echo "  📋 查看日誌: tail -f logs/framepack_gpu*.log"
}

# 主函數
main() {
    echo "🚀 FramePack 雙 GPU 啟動腳本"
    echo "================================"
    
    check_gpu
    check_ports
    create_directories
    start_services
    
    if [[ $? -eq 0 ]]; then
        show_service_info
    else
        print_error "服務啟動失敗，請檢查日誌文件"
        exit 1
    fi
}

# 執行主函數
main "$@"
