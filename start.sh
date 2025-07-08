#!/bin/bash

# FramePack Service Manager - 跨平台版本
# 支援 macOS (開發環境) 和 Ubuntu (部署環境)
# Usage: ./start.sh [start|stop|restart|status|dev]

set -euo pipefail  # Exit on error, undefined vars, pipe failures

# =============================================================================
# 操作系統檢測和環境設定
# =============================================================================

# 操作系統檢測
detect_os() {
    case "$(uname -s)" in
        Darwin*)
            OS="macOS"
            IS_MACOS=true
            IS_UBUNTU=false
            ;;
        Linux*)
            if [[ -f /etc/os-release ]]; then
                . /etc/os-release
                if [[ "$ID" == "ubuntu" ]]; then
                    OS="Ubuntu $VERSION_ID"
                    IS_UBUNTU=true
                    IS_MACOS=false
                else
                    OS="Linux ($ID)"
                    IS_UBUNTU=true  # 假設其他 Linux 發行版使用類似 Ubuntu 的配置
                    IS_MACOS=false
                fi
            else
                OS="Linux"
                IS_UBUNTU=true
                IS_MACOS=false
            fi
            ;;
        *)
            OS="Unknown"
            IS_UBUNTU=false
            IS_MACOS=false
            ;;
    esac
}

# 設定平台特定的環境變數
setup_platform_env() {
    if [[ "$IS_MACOS" == true ]]; then
        # macOS 特定環境變數 (Apple Silicon MPS 支援)
        export PYTORCH_ENABLE_MPS_FALLBACK=1
        export TOKENIZERS_PARALLELISM=false
        # 如果是遠端模式，保持 0.0.0.0 以允許外部訪問
        if [[ "$HOST" == "0.0.0.0" ]] && [[ "${FORCE_EXTERNAL_ACCESS:-false}" != "true" ]] && [[ "$ENABLE_REMOTE" != "true" ]]; then
            HOST="127.0.0.1"  # macOS 開發環境默認本機訪問
        fi
    elif [[ "$IS_UBUNTU" == true ]]; then
        # Ubuntu/Linux 特定環境變數
        export TOKENIZERS_PARALLELISM=false
        # 設定 CUDA 相關環境變數（如果有 GPU）
        if command -v nvidia-smi >/dev/null 2>&1; then
            export CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-"0,1,2,3"}
        fi
    fi
}

# 初始化操作系統檢測
detect_os

# =============================================================================
# Configuration Section
# =============================================================================

# 工作目錄 - 改為當前腳本所在目錄
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK_DIR="${SCRIPT_DIR}"

# 載入用戶配置文件
CONFIG_FILE="${WORK_DIR}/config.env"
load_user_config() {
    if [[ -f "$CONFIG_FILE" ]]; then
        print_info "載入用戶配置文件: $CONFIG_FILE"
        # 安全地載入配置文件，只允許特定變數
        while IFS='=' read -r key value; do
            # 跳過註釋和空行
            [[ $key =~ ^[[:space:]]*# ]] && continue
            [[ -z "$key" ]] && continue

            # 移除前後空白
            key=$(echo "$key" | xargs)
            value=$(echo "$value" | xargs)

            # 只允許特定的配置變數
            case "$key" in
                USERNAME)
                    USERNAME="$value"
                    ;;
                PASSWORD)
                    PASSWORD="$value"
                    ;;
                DEFAULT_PORT)
                    DEFAULT_PORT="$value"
                    ;;
                SECOND_PORT)
                    SECOND_PORT="$value"
                    ;;
                HOST)
                    HOST="$value"
                    ;;
                REMOTE_HOST)
                    REMOTE_HOST="$value"
                    ;;
                REMOTE_USER)
                    REMOTE_USER="$value"
                    ;;
                REMOTE_PYTHON)
                    REMOTE_PYTHON="$value"
                    ;;
                REMOTE_PROJECT_DIR)
                    REMOTE_PROJECT_DIR="$value"
                    ;;
                ENABLE_REMOTE)
                    ENABLE_REMOTE="$value"
                    ;;
            esac
        done < "$CONFIG_FILE"
    else
        print_info "未找到用戶配置文件，將使用默認配置"
        print_info "可以創建 $CONFIG_FILE 來自定義配置"
    fi
}

# Python 環境設置
VENV_PATH="${WORK_DIR}/.venv"
PYTHON_BIN="${VENV_PATH}/bin/python"
SCRIPT_NAME="main.py"
SCRIPT_PATH="${WORK_DIR}/${SCRIPT_NAME}"

# 默認服務配置 (可被配置文件覆蓋)
USERNAME="admin"
PASSWORD="123456"
DEFAULT_PORT=7860
SECOND_PORT=7861
HOST="0.0.0.0"  # 監聽所有網路介面，允許外部訪問

# 遠端開發配置 (可被配置文件覆蓋)
ENABLE_REMOTE=false
REMOTE_HOST="192.168.1.104"
REMOTE_USER="jake"
REMOTE_PYTHON="/home/jake/.virtualenvs/FramePackB/bin/python"
REMOTE_PROJECT_DIR="/tmp/pycharm_project_662"

# 系統配置
PID_DIR="${WORK_DIR}/pids"
LOG_DIR="${WORK_DIR}/logs"
LOCK_DIR="${WORK_DIR}/locks"

# GPU 配置 - 自動偵測
GPU_DEVICES=()  # 將自動偵測可用的 GPU
ENABLE_SECOND_GPU=false  # 將根據 GPU 數量自動設定

# =============================================================================
# Utility Functions
# =============================================================================

# 顏色輸出函數
print_info() { echo -e "\033[1;34m[INFO]\033[0m $1"; }
print_success() { echo -e "\033[1;32m[SUCCESS]\033[0m $1"; }
print_warning() { echo -e "\033[1;33m[WARNING]\033[0m $1"; }
print_error() { echo -e "\033[1;31m[ERROR]\033[0m $1"; }

# 創建必要目錄
create_directories() {
    mkdir -p "$PID_DIR" "$LOG_DIR" "$LOCK_DIR"
}

# 自動偵測 GPU
detect_gpus() {
    print_info "自動偵測 GPU 設備..."

    GPU_DEVICES=()

    if command -v nvidia-smi >/dev/null 2>&1; then
        # 獲取可用的 GPU 數量和信息
        local gpu_count
        gpu_count=$(nvidia-smi --query-gpu=index --format=csv,noheader,nounits | wc -l)

        if [[ $gpu_count -gt 0 ]]; then
            print_success "檢測到 $gpu_count 張 NVIDIA GPU"

            # 獲取 GPU 索引
            while IFS= read -r gpu_index; do
                GPU_DEVICES+=("$gpu_index")
                local gpu_info
                gpu_info=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits -i "$gpu_index")
                print_info "GPU $gpu_index: $gpu_info"
            done < <(nvidia-smi --query-gpu=index --format=csv,noheader,nounits)

            # 自動啟用第二個 GPU（如果有）
            if [[ ${#GPU_DEVICES[@]} -gt 1 ]]; then
                ENABLE_SECOND_GPU=true
                print_success "自動啟用第二個 GPU 服務"
            else
                ENABLE_SECOND_GPU=false
                print_info "只有一張 GPU，不啟用第二個服務"
            fi
        else
            print_warning "未檢測到可用的 NVIDIA GPU"
            GPU_DEVICES=(0)  # 默認使用 GPU 0（可能是 CPU 模式）
            ENABLE_SECOND_GPU=false
        fi
    else
        print_warning "nvidia-smi 不可用，將使用 CPU 模式"
        GPU_DEVICES=(0)  # 默認使用設備 0
        ENABLE_SECOND_GPU=false
    fi

    print_info "GPU 配置: ${GPU_DEVICES[*]}"
    print_info "第二個 GPU 服務: $([ "$ENABLE_SECOND_GPU" = true ] && echo "啟用" || echo "禁用")"
}

# 檢查依賴
check_dependencies() {
    print_info "檢查系統依賴..."

    # 如果是遠端模式，跳過本地 Python 環境檢查
    if [[ "$ENABLE_REMOTE" == "true" ]]; then
        print_info "遠端模式：跳過本地 Python 環境檢查"

        # 檢查 SSH 連接
        if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "$REMOTE_USER@$REMOTE_HOST" exit 2>/dev/null; then
            print_error "無法連接到遠端主機: $REMOTE_USER@$REMOTE_HOST"
            print_info "請確保 SSH 免密登錄已設置"
            exit 1
        fi
        print_success "遠端 SSH 連接正常"

    else
        # 檢查本地 Python 虛擬環境
        if [[ ! -f "$PYTHON_BIN" ]]; then
            print_error "Python 虛擬環境不存在: $PYTHON_BIN"
            print_info "請先創建虛擬環境: python3 -m venv $VENV_PATH"
            exit 1
        fi
        print_success "本地 Python 環境正常"
    fi

    # 檢查腳本文件
    if [[ ! -f "$SCRIPT_PATH" ]]; then
        print_error "腳本文件不存在: $SCRIPT_PATH"
        exit 1
    fi

    print_success "依賴檢查完成"
}

# 檢查網路設定
check_network() {
    print_info "檢查網路設定..."

    if [[ "$HOST" == "0.0.0.0" ]]; then
        # 獲取本機 IP 地址 (跨平台兼容)
        if [[ "$IS_MACOS" == true ]]; then
            local_ip=$(ifconfig | grep "inet " | grep -v 127.0.0.1 | awk '{print $2}' | head -1)
        else
            local_ip=$(hostname -I | awk '{print $1}' 2>/dev/null)
        fi

        if [[ -n "$local_ip" ]]; then
            print_success "本機 IP 地址: $local_ip"
            print_info "外部設備可通過此 IP 訪問服務"
        else
            print_warning "無法獲取本機 IP 地址"
        fi

        # 檢查防火牆狀態
        if command -v ufw >/dev/null 2>&1; then
            if ufw status | grep -q "Status: active"; then
                print_warning "UFW 防火牆已啟用，可能需要開放端口"
                print_info "開放端口命令: sudo ufw allow $DEFAULT_PORT"
                [[ "$ENABLE_SECOND_GPU" == "true" ]] && print_info "開放端口命令: sudo ufw allow $SECOND_PORT"
            fi
        fi

        # 檢查 iptables (如果存在)
        if command -v iptables >/dev/null 2>&1; then
            if iptables -L INPUT 2>/dev/null | grep -q "DROP\|REJECT"; then
                print_warning "檢測到 iptables 規則，可能影響外部訪問"
            fi
        fi
    else
        print_info "服務將監聽: $HOST"
    fi
}
# =============================================================================
# Service Management Functions
# =============================================================================

# 獲取服務實例的 PID 文件路徑
get_pid_file() {
    local port=$1
    echo "${PID_DIR}/framepack_${port}.pid"
}

# 獲取服務實例的日誌文件路徑
get_log_file() {
    local port=$1
    echo "${LOG_DIR}/framepack_${port}.log"
}

# 獲取服務實例的鎖文件路徑
get_lock_file() {
    local port=$1
    echo "${LOCK_DIR}/framepack_${port}.lock"
}

# 檢查端口是否被佔用
is_port_in_use() {
    local port=$1
    if command -v ss >/dev/null 2>&1; then
        ss -tuln | grep -q ":${port} "
    elif command -v netstat >/dev/null 2>&1; then
        netstat -tuln | grep -q ":${port} "
    else
        # 使用 lsof 作為後備
        lsof -i ":${port}" >/dev/null 2>&1
    fi
}

# 檢查進程是否存在
is_process_running() {
    local pid=$1
    # 檢查輸入是否為空
    [[ -z "$pid" ]] && return 1

    # 清理 PID 並檢查是否為有效數字
    local clean_pid
    clean_pid=$(echo "$pid" | tr -d '\r\n\t ' | grep -o '[0-9]*')

    # 檢查清理後的 PID 是否有效
    [[ -n "$clean_pid" ]] && [[ "$clean_pid" -gt 0 ]] 2>/dev/null && kill -0 "$clean_pid" 2>/dev/null
}

# 從 PID 文件獲取 PID
get_pid_from_file() {
    local pid_file=$1
    if [[ -f "$pid_file" ]]; then
        local pid
        pid=$(cat "$pid_file" 2>/dev/null)
        if is_process_running "$pid"; then
            echo "$pid"
            return 0
        else
            # PID 文件存在但進程不存在，清理文件
            rm -f "$pid_file"
            return 1
        fi
    fi
    return 1
}

# 等待進程停止
wait_for_process_stop() {
    local pid=$1
    local timeout=${2:-10}
    local count=0

    while is_process_running "$pid" && [[ $count -lt $timeout ]]; do
        sleep 1
        ((count++))
    done

    ! is_process_running "$pid"
}

# 強制終止進程
force_kill_process() {
    local pid=$1
    if is_process_running "$pid"; then
        print_warning "強制終止進程 $pid"
        kill -9 "$pid" 2>/dev/null || true
        sleep 1
    fi
}
# =============================================================================
# Core Service Functions
# =============================================================================

# 啟動單個服務實例
start_instance() {
    local gpu_id=$1
    local port=$2
    local username=$3
    local password=$4

    local pid_file
    local log_file
    local lock_file

    pid_file=$(get_pid_file "$port")
    log_file=$(get_log_file "$port")
    lock_file=$(get_lock_file "$port")

    # 檢查是否已經在運行
    if get_pid_from_file "$pid_file" >/dev/null; then
        print_warning "GPU $gpu_id / Port $port 服務已在運行"
        return 0
    fi

    # 檢查端口是否被其他程序佔用
    if is_port_in_use "$port"; then
        print_error "端口 $port 已被其他程序佔用"
        return 1
    fi

    # 檢查並清理舊的鎖文件
    if [[ -f "$lock_file" ]]; then
        local lock_pid
        if lock_pid=$(cat "$lock_file" 2>/dev/null) && [[ -n "$lock_pid" ]]; then
            if ! is_process_running "$lock_pid"; then
                print_warning "清理舊的鎖文件 (PID $lock_pid 已不存在)"
                rm -f "$lock_file"
            else
                print_error "另一個實例正在啟動 (PID: $lock_pid)"
                return 1
            fi
        else
            print_warning "清理無效的鎖文件"
            rm -f "$lock_file"
        fi
    fi

    # 創建鎖文件
    if ! (set -C; echo $$ > "$lock_file") 2>/dev/null; then
        print_error "無法創建鎖文件，可能有其他實例正在啟動"
        return 1
    fi

    print_info "啟動 GPU $gpu_id / Port $port 服務..."

    # 根據是否啟用遠端模式選擇啟動方式
    if [[ "$ENABLE_REMOTE" == "true" ]]; then
        start_remote_instance "$gpu_id" "$port" "$username" "$password" "$pid_file" "$log_file" "$lock_file"
    else
        start_local_instance "$gpu_id" "$port" "$username" "$password" "$pid_file" "$log_file" "$lock_file"
    fi
}

# 啟動本地服務實例
start_local_instance() {
    local gpu_id=$1
    local port=$2
    local username=$3
    local password=$4
    local pid_file=$5
    local log_file=$6
    local lock_file=$7

    # 設置環境變數
    export CUDA_VISIBLE_DEVICES=$gpu_id
    export PYTORCH_ENABLE_MPS_FALLBACK=1
    export TOKENIZERS_PARALLELISM=false

    # 啟動服務
    cd "$WORK_DIR"
    nohup "$PYTHON_BIN" "$SCRIPT_NAME" \
        --port "$port" \
        --server "$HOST" \
        --username "$username" \
        --password "$password" \
        > "$log_file" 2>&1 &

    local pid=$!

    # 清理 PID 變數中的任何不可見字符
    pid=$(echo "$pid" | tr -d '\r\n\t ' | grep -o '[0-9]*')

    # 檢查 PID 是否有效
    if [[ -z "$pid" ]] || [[ "$pid" -eq 0 ]] 2>/dev/null; then
        print_error "無法獲取有效的進程 PID"
        rm -f "$lock_file"
        return 1
    fi

    # 保存 PID
    echo "$pid" > "$pid_file"

    # 清理鎖文件
    rm -f "$lock_file"

    # 等待服務啟動 - 增加等待時間因為模型加載需要時間
    print_info "等待服務啟動 (模型加載中...)..."
    sleep 5

    if is_process_running "$pid"; then
        print_success "GPU $gpu_id 服務已啟動，PID=$pid，端口=$port"
        print_info "日誌文件: $log_file"
        print_info "服務正在加載模型，請稍候..."
        return 0
    else
        print_error "GPU $gpu_id 服務啟動失敗"
        print_info "請檢查日誌文件: $log_file"
        rm -f "$pid_file"
        return 1
    fi
}

# 啟動遠端服務實例
start_remote_instance() {
    local gpu_id=$1
    local port=$2
    local username=$3
    local password=$4
    local pid_file=$5
    local log_file=$6
    local lock_file=$7

    print_info "使用遠端模式啟動服務..."
    print_info "遠端主機: $REMOTE_USER@$REMOTE_HOST"
    print_info "遠端項目目錄: $REMOTE_PROJECT_DIR"
    print_info "遠端 Python: $REMOTE_PYTHON"

    # 構建遠端命令
    local remote_cmd="cd $REMOTE_PROJECT_DIR && CUDA_VISIBLE_DEVICES=$gpu_id TOKENIZERS_PARALLELISM=false $REMOTE_PYTHON $SCRIPT_NAME --port $port --server $HOST --username $username --password $password"

    # 啟動遠端服務
    ssh "$REMOTE_USER@$REMOTE_HOST" "$remote_cmd" > "$log_file" 2>&1 &
    local raw_pid=$!

    # 清理 PID 變數中的任何不可見字符
    local pid
    pid=$(echo "$raw_pid" | tr -d '\r\n\t ' | sed 's/[^0-9]//g')

    # 檢查 PID 是否有效
    if [[ -z "$pid" ]] || [[ "$pid" -eq 0 ]] 2>/dev/null; then
        print_error "無法獲取有效的進程 PID (原始: '$raw_pid', 清理後: '$pid')"
        rm -f "$lock_file"
        return 1
    fi

    # 保存 PID (這是本地 SSH 進程的 PID)
    echo "$pid" > "$pid_file"

    # 清理鎖文件
    rm -f "$lock_file"

    # 等待服務啟動 - 遠端啟動需要更長時間
    print_info "等待遠端服務啟動 (模型加載中...)..."

    # 等待遠端服務啟動，檢查端口是否可用
    local max_attempts=30
    local attempt=0
    local service_started=false

    while [[ $attempt -lt $max_attempts ]]; do
        if ssh -o ConnectTimeout=5 "$REMOTE_USER@$REMOTE_HOST" "lsof -i :$port" >/dev/null 2>&1; then
            service_started=true
            break
        fi
        sleep 2
        ((attempt++))
        if [[ $((attempt % 5)) -eq 0 ]]; then
            print_info "等待中... ($attempt/$max_attempts)"
        fi
    done

    if [[ "$service_started" == "true" ]]; then
        print_success "遠端 GPU $gpu_id 服務已啟動，端口=$port"
        print_info "日誌文件: $log_file"
        print_info "遠端服務正在加載模型，請稍候..."
        return 0
    else
        print_error "遠端 GPU $gpu_id 服務啟動失敗或超時"
        print_info "請檢查日誌文件: $log_file"
        rm -f "$pid_file"
        return 1
    fi
}

# 停止單個服務實例
stop_instance() {
    local port=$1
    local pid_file
    local pid

    pid_file=$(get_pid_file "$port")

    # 如果是遠端模式，停止遠端服務
    if [[ "$ENABLE_REMOTE" == "true" ]]; then
        # 檢查遠端是否有服務在運行
        if ! ssh -o ConnectTimeout=5 "$REMOTE_USER@$REMOTE_HOST" "lsof -i :$port" >/dev/null 2>&1; then
            print_warning "端口 $port 的遠端服務未在運行"
            return 0
        fi

        # 獲取遠端進程 PID
        local remote_pid
        remote_pid=$(ssh "$REMOTE_USER@$REMOTE_HOST" "lsof -i :$port -t" 2>/dev/null | head -1)

        if [[ -n "$remote_pid" ]]; then
            print_info "停止遠端端口 $port 的服務 (遠端 PID: $remote_pid)..."

            # 嘗試優雅停止遠端進程
            ssh "$REMOTE_USER@$REMOTE_HOST" "kill -TERM $remote_pid" 2>/dev/null || true

            # 等待遠端進程停止
            local max_wait=10
            local count=0
            while [[ $count -lt $max_wait ]]; do
                if ! ssh "$REMOTE_USER@$REMOTE_HOST" "kill -0 $remote_pid" >/dev/null 2>&1; then
                    print_success "遠端服務已優雅停止"
                    rm -f "$pid_file"
                    return 0
                fi
                sleep 1
                ((count++))
            done

            # 強制停止
            print_warning "優雅停止超時，強制終止遠端進程..."
            ssh "$REMOTE_USER@$REMOTE_HOST" "kill -9 $remote_pid" 2>/dev/null || true
            sleep 2

            if ! ssh "$REMOTE_USER@$REMOTE_HOST" "kill -0 $remote_pid" >/dev/null 2>&1; then
                print_success "遠端服務已強制停止"
                rm -f "$pid_file"
                return 0
            else
                print_error "無法停止遠端服務"
                return 1
            fi
        else
            print_warning "無法獲取遠端進程 PID"
            return 1
        fi
    else
        # 本地模式停止
        if ! pid=$(get_pid_from_file "$pid_file"); then
            print_warning "端口 $port 的服務未在運行"
            return 0
        fi

        print_info "停止端口 $port 的服務 (PID: $pid)..."

        # 嘗試優雅停止
        kill -TERM "$pid" 2>/dev/null || true

        if wait_for_process_stop "$pid" 10; then
            print_success "服務已優雅停止"
        else
            print_warning "優雅停止超時，強制終止..."
            force_kill_process "$pid"

            if wait_for_process_stop "$pid" 5; then
                print_success "服務已強制停止"
            else
                print_error "無法停止服務"
                return 1
            fi
        fi

        # 清理文件
        rm -f "$pid_file"
        return 0
    fi
}

# 檢查服務狀態
check_instance_status() {
    local port=$1
    local pid_file
    local pid

    pid_file=$(get_pid_file "$port")

    # 如果是遠端模式，檢查遠端端口狀態
    if [[ "$ENABLE_REMOTE" == "true" ]]; then
        if ssh -o ConnectTimeout=5 "$REMOTE_USER@$REMOTE_HOST" "lsof -i :$port" >/dev/null 2>&1; then
            # 獲取遠端進程信息
            local remote_pid
            remote_pid=$(ssh "$REMOTE_USER@$REMOTE_HOST" "lsof -i :$port -t" 2>/dev/null | head -1)

            print_success "端口 $port: 遠端運行中 (遠端 PID: $remote_pid)"
            echo "  遠端主機: $REMOTE_HOST"

            # 獲取遠端進程詳細信息
            if [[ -n "$remote_pid" ]]; then
                local cpu_usage mem_usage start_time
                cpu_usage=$(ssh "$REMOTE_USER@$REMOTE_HOST" "ps -p $remote_pid -o %cpu --no-headers 2>/dev/null | tr -d ' '" || echo "N/A")
                mem_usage=$(ssh "$REMOTE_USER@$REMOTE_HOST" "ps -p $remote_pid -o %mem --no-headers 2>/dev/null | tr -d ' '" || echo "N/A")
                start_time=$(ssh "$REMOTE_USER@$REMOTE_HOST" "ps -p $remote_pid -o lstart --no-headers 2>/dev/null" || echo "N/A")

                [[ "$cpu_usage" != "N/A" ]] && echo "  CPU: ${cpu_usage}%"
                [[ "$mem_usage" != "N/A" ]] && echo "  記憶體: ${mem_usage}%"
                [[ "$start_time" != "N/A" ]] && echo "  啟動時間: $start_time"
            fi

            echo "  端口狀態: 監聽中"
            return 0
        else
            print_warning "端口 $port: 遠端未運行"
            return 1
        fi
    else
        # 本地模式檢查
        if pid=$(get_pid_from_file "$pid_file"); then
            local cpu_usage
            local mem_usage
            local start_time

            # 獲取進程信息
            if command -v ps >/dev/null 2>&1; then
                cpu_usage=$(ps -p "$pid" -o %cpu --no-headers 2>/dev/null | tr -d ' ' || echo "N/A")
                mem_usage=$(ps -p "$pid" -o %mem --no-headers 2>/dev/null | tr -d ' ' || echo "N/A")
                start_time=$(ps -p "$pid" -o lstart --no-headers 2>/dev/null || echo "N/A")
            fi

            print_success "端口 $port: 運行中 (PID: $pid)"
            [[ "$cpu_usage" != "N/A" ]] && echo "  CPU: ${cpu_usage}%"
            [[ "$mem_usage" != "N/A" ]] && echo "  記憶體: ${mem_usage}%"
            [[ "$start_time" != "N/A" ]] && echo "  啟動時間: $start_time"

            # 檢查端口狀態
            if is_port_in_use "$port"; then
                echo "  端口狀態: 監聽中"
            else
                echo "  端口狀態: 未監聽"
            fi

            return 0
        else
            print_warning "端口 $port: 未運行"
            return 1
        fi
    fi
}
# =============================================================================
# Main Command Functions
# =============================================================================

# 啟動所有服務
cmd_start() {
    print_info "啟動 FramePack 服務..."

    # 載入用戶配置
    load_user_config

    create_directories
    setup_platform_env
    check_dependencies

    # 如果啟用遠端模式，跳過本地 GPU 檢測
    if [[ "$ENABLE_REMOTE" != "true" ]]; then
        detect_gpus
    else
        print_info "遠端模式已啟用，跳過本地 GPU 檢測"
        GPU_DEVICES=(0)  # 遠端模式使用默認 GPU 設備
        ENABLE_SECOND_GPU=false
    fi

    check_network

    local success=true

    # 確保至少有一個 GPU 設備
    if [[ ${#GPU_DEVICES[@]} -eq 0 ]]; then
        print_warning "未檢測到 GPU 設備，使用默認設備 0"
        GPU_DEVICES=(0)
    fi

    # 啟動主要服務
    if ! start_instance "${GPU_DEVICES[0]}" "$DEFAULT_PORT" "$USERNAME" "$PASSWORD"; then
        success=false
    fi

    # 啟動第二個 GPU 服務（如果啟用且有第二個 GPU）
    if [[ "$ENABLE_SECOND_GPU" == "true" ]] && [[ ${#GPU_DEVICES[@]} -gt 1 ]]; then
        print_info "啟動第二個 GPU 服務..."
        if ! start_instance "${GPU_DEVICES[1]}" "$SECOND_PORT" "$USERNAME" "$PASSWORD"; then
            success=false
        fi
    fi

    if [[ "$success" == "true" ]]; then
        print_success "所有服務啟動完成"
        echo ""
        print_info "訪問地址:"
        if [[ "$HOST" == "0.0.0.0" ]]; then
            # 獲取本機 IP 地址 (跨平台兼容)
            if [[ "$IS_MACOS" == true ]]; then
                local_ip=$(ifconfig | grep "inet " | grep -v 127.0.0.1 | awk '{print $2}' | head -1)
            else
                local_ip=$(hostname -I | awk '{print $1}' 2>/dev/null)
            fi
            [[ -z "$local_ip" ]] && local_ip="YOUR_IP"

            if [[ "$ENABLE_REMOTE" == "true" ]]; then
                echo "  遠端服務 (GPU ${GPU_DEVICES[0]}): http://localhost:$DEFAULT_PORT (本機)"
                echo "  遠端服務 (GPU ${GPU_DEVICES[0]}): http://$REMOTE_HOST:$DEFAULT_PORT (遠端訪問)"
                if [[ "$ENABLE_SECOND_GPU" == "true" ]] && [[ ${#GPU_DEVICES[@]} -gt 1 ]]; then
                    echo "  第二遠端服務 (GPU ${GPU_DEVICES[1]}): http://localhost:$SECOND_PORT (本機)"
                    echo "  第二遠端服務 (GPU ${GPU_DEVICES[1]}): http://$REMOTE_HOST:$SECOND_PORT (遠端訪問)"
                fi
            else
                echo "  主服務 (GPU ${GPU_DEVICES[0]}): http://localhost:$DEFAULT_PORT (本機)"
                echo "  主服務 (GPU ${GPU_DEVICES[0]}): http://$local_ip:$DEFAULT_PORT (外部訪問)"
                if [[ "$ENABLE_SECOND_GPU" == "true" ]] && [[ ${#GPU_DEVICES[@]} -gt 1 ]]; then
                    echo "  第二服務 (GPU ${GPU_DEVICES[1]}): http://localhost:$SECOND_PORT (本機)"
                    echo "  第二服務 (GPU ${GPU_DEVICES[1]}): http://$local_ip:$SECOND_PORT (外部訪問)"
                fi
            fi
        else
            echo "  主服務 (GPU ${GPU_DEVICES[0]}): http://$HOST:$DEFAULT_PORT"
            if [[ "$ENABLE_SECOND_GPU" == "true" ]] && [[ ${#GPU_DEVICES[@]} -gt 1 ]]; then
                echo "  第二服務 (GPU ${GPU_DEVICES[1]}): http://$HOST:$SECOND_PORT"
            fi
        fi
        echo ""
        print_info "默認登錄信息:"
        echo "  用戶名: $USERNAME"
        echo "  密碼: $PASSWORD"
    else
        print_error "部分服務啟動失敗，請檢查日誌"
        return 1
    fi
}

# 停止所有服務
cmd_stop() {
    # 載入用戶配置
    load_user_config

    print_info "停止 FramePack 服務..."

    local success=true

    # 停止主要服務
    if ! stop_instance "$DEFAULT_PORT"; then
        success=false
    fi

    # 停止第二個服務
    if ! stop_instance "$SECOND_PORT"; then
        success=false
    fi

    if [[ "$success" == "true" ]]; then
        print_success "所有服務已停止"
    else
        print_error "部分服務停止失敗"
        return 1
    fi
}

# 重啟所有服務
cmd_restart() {
    print_info "重啟 FramePack 服務..."
    cmd_stop
    sleep 2
    cmd_start
}

# 檢查服務狀態
cmd_status() {
    # 載入用戶配置
    load_user_config

    print_info "FramePack 服務狀態:"
    echo ""

    local any_running=false

    # 檢查主要服務
    if check_instance_status "$DEFAULT_PORT"; then
        any_running=true
    fi

    echo ""

    # 檢查第二個服務
    if check_instance_status "$SECOND_PORT"; then
        any_running=true
    fi

    echo ""

    if [[ "$any_running" == "true" ]]; then
        print_info "系統資源使用情況:"
        if [[ "$ENABLE_REMOTE" == "true" ]]; then
            print_info "遠端模式 - 檢查遠端主機資源: $REMOTE_HOST"
            if ssh -o ConnectTimeout=5 "$REMOTE_USER@$REMOTE_HOST" "command -v free" >/dev/null 2>&1; then
                echo "遠端記憶體使用:"
                ssh "$REMOTE_USER@$REMOTE_HOST" "free -h | head -2"
            fi

            if ssh -o ConnectTimeout=5 "$REMOTE_USER@$REMOTE_HOST" "command -v nvidia-smi" >/dev/null 2>&1; then
                echo ""
                echo "遠端 GPU 使用情況:"
                ssh "$REMOTE_USER@$REMOTE_HOST" "nvidia-smi --query-gpu=index,name,utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits"
            fi
        else
            if command -v free >/dev/null 2>&1; then
                echo "記憶體使用:"
                free -h | head -2
            fi

            if command -v nvidia-smi >/dev/null 2>&1; then
                echo ""
                echo "GPU 使用情況:"
                nvidia-smi --query-gpu=index,name,utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits
            fi
        fi
    else
        print_warning "沒有服務在運行"
    fi
}

# 開發模式 (類似原來的 start_framepack.sh)
cmd_dev() {
    print_info "🚀 FramePack 開發模式"
    print_info "操作系統: $OS"
    echo ""

    # 設定環境變數
    setup_platform_env

    # 顯示環境信息
    if [[ "$IS_MACOS" == true ]]; then
        print_info "✅ macOS 環境變數已設置:"
        print_info "   PYTORCH_ENABLE_MPS_FALLBACK=1"
        print_info "   TOKENIZERS_PARALLELISM=false"
    else
        print_info "✅ Ubuntu 環境變數已設置:"
        print_info "   TOKENIZERS_PARALLELISM=false"
        if command -v nvidia-smi >/dev/null 2>&1; then
            print_info "   CUDA_VISIBLE_DEVICES=$CUDA_VISIBLE_DEVICES"
        fi
    fi

    # 檢查虛擬環境
    if [[ -f "$PYTHON_BIN" ]]; then
        print_success "✅ 發現虛擬環境: $VENV_PATH"
    else
        print_warning "⚠️ 未發現虛擬環境，請先創建: python3 -m venv .venv"
        exit 1
    fi

    # 檢查 Python 版本
    python_version=$("$PYTHON_BIN" --version 2>&1)
    print_info "🐍 Python 版本: $python_version"

    # 顯示選項
    echo ""
    print_info "請選擇要啟動的版本:"
    echo "1) FramePack 基礎版本 (demo_gradio_refactored.py)"
    echo "2) FramePack F1 版本 (demo_gradio_f1_refactored.py) - 包含認證和高級功能"
    echo "3) 退出"

    read -p "請輸入選項 (1-3): " choice

    case $choice in
        1)
            print_info "🎬 啟動 FramePack 基礎版本..."
            if [[ -f "$WORK_DIR/demo_gradio_refactored.py" ]]; then
                "$PYTHON_BIN" "$WORK_DIR/demo_gradio_refactored.py"
            else
                print_error "找不到 demo_gradio_refactored.py"
                exit 1
            fi
            ;;
        2)
            print_info "🎬 啟動 FramePack F1 版本..."
            print_info "💡 提示: 默認用戶名/密碼為 admin/123456"
            print_info "💡 可以使用 --no-auth 參數禁用認證"
            if [[ -f "$SCRIPT_PATH" ]]; then
                "$PYTHON_BIN" "$SCRIPT_PATH"
            else
                print_error "找不到 $SCRIPT_NAME"
                exit 1
            fi
            ;;
        3)
            print_info "👋 再見！"
            exit 0
            ;;
        *)
            print_error "❌ 無效選項"
            exit 1
            ;;
    esac
}

# 顯示 GPU 信息
cmd_gpu_info() {
    print_info "GPU 信息檢查..."
    detect_gpus
    echo ""

    if command -v nvidia-smi >/dev/null 2>&1; then
        print_info "詳細 GPU 信息:"
        nvidia-smi
    else
        print_warning "nvidia-smi 不可用，無法顯示詳細 GPU 信息"
    fi
}

# 配置管理
cmd_config() {
    print_info "FramePack 配置管理"
    echo ""

    if [[ -f "$CONFIG_FILE" ]]; then
        print_success "發現現有配置文件: $CONFIG_FILE"
        echo ""
        print_info "當前配置內容:"
        cat "$CONFIG_FILE"
        echo ""

        print_info "請選擇操作:"
        echo "1) 編輯現有配置"
        echo "2) 重新創建配置"
        echo "3) 刪除配置文件"
        echo "4) 返回"

        read -p "請輸入選項 (1-4): " choice

        case $choice in
            1)
                if command -v nano >/dev/null 2>&1; then
                    nano "$CONFIG_FILE"
                elif command -v vi >/dev/null 2>&1; then
                    vi "$CONFIG_FILE"
                else
                    print_error "未找到文本編輯器 (nano/vi)"
                    return 1
                fi
                ;;
            2)
                create_config_file
                ;;
            3)
                read -p "確定要刪除配置文件嗎？(y/N): " -n 1 -r
                echo
                if [[ $REPLY =~ ^[Yy]$ ]]; then
                    rm -f "$CONFIG_FILE"
                    print_success "配置文件已刪除"
                else
                    print_info "已取消"
                fi
                ;;
            4)
                return 0
                ;;
            *)
                print_error "無效選項"
                return 1
                ;;
        esac
    else
        print_info "未找到配置文件，將創建新的配置文件"
        create_config_file
    fi
}

# 創建配置文件
create_config_file() {
    print_info "創建新的配置文件..."

    # 詢問用戶配置選項
    echo ""
    print_info "請輸入配置信息 (直接按 Enter 使用默認值):"

    read -p "認證用戶名 [admin]: " input_username
    USERNAME=${input_username:-admin}

    read -p "認證密碼 [123456]: " input_password
    PASSWORD=${input_password:-123456}

    read -p "主端口 [7860]: " input_port
    DEFAULT_PORT=${input_port:-7860}

    read -p "第二端口 [7861]: " input_second_port
    SECOND_PORT=${input_second_port:-7861}

    read -p "監聽地址 [0.0.0.0]: " input_host
    HOST=${input_host:-0.0.0.0}

    echo ""
    print_info "是否啟用遠端開發模式？"
    read -p "啟用遠端模式 (y/N): " -n 1 -r
    echo

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        ENABLE_REMOTE=true

        read -p "遠端主機 IP [192.168.1.104]: " input_remote_host
        REMOTE_HOST=${input_remote_host:-192.168.1.104}

        read -p "遠端用戶名 [jake]: " input_remote_user
        REMOTE_USER=${input_remote_user:-jake}

        read -p "遠端 Python 路徑 [/home/jake/.virtualenvs/FramePackB/bin/python]: " input_remote_python
        REMOTE_PYTHON=${input_remote_python:-/home/jake/.virtualenvs/FramePackB/bin/python}

        read -p "遠端項目目錄 [/tmp/pycharm_project_662]: " input_remote_dir
        REMOTE_PROJECT_DIR=${input_remote_dir:-/tmp/pycharm_project_662}
    else
        ENABLE_REMOTE=false
    fi

    # 創建配置文件
    cat > "$CONFIG_FILE" << EOF
# FramePack 用戶配置文件
# 由配置管理工具自動生成

# =============================================================================
# 服務配置
# =============================================================================

# 認證設定
USERNAME=$USERNAME
PASSWORD=$PASSWORD

# 端口設定
DEFAULT_PORT=$DEFAULT_PORT
SECOND_PORT=$SECOND_PORT

# 服務器監聽地址
HOST=$HOST

# =============================================================================
# 遠端開發配置
# =============================================================================

# 是否啟用遠端模式
ENABLE_REMOTE=$ENABLE_REMOTE
EOF

    if [[ "$ENABLE_REMOTE" == "true" ]]; then
        cat >> "$CONFIG_FILE" << EOF

# 遠端服務器設定
REMOTE_HOST=$REMOTE_HOST
REMOTE_USER=$REMOTE_USER

# 遠端 Python 環境路徑
REMOTE_PYTHON=$REMOTE_PYTHON

# 遠端項目目錄
REMOTE_PROJECT_DIR=$REMOTE_PROJECT_DIR
EOF
    fi

    print_success "配置文件已創建: $CONFIG_FILE"
    echo ""
    print_info "配置內容:"
    cat "$CONFIG_FILE"
}

# 清理系統文件
cmd_clean() {
    print_info "清理 FramePack 系統文件..."

    # 停止所有服務
    print_info "首先停止所有運行中的服務..."
    cmd_stop

    # 清理鎖文件
    cleanup_lock_files

    # 清理孤立的 PID 文件
    if [[ -d "$PID_DIR" ]]; then
        local pid_files
        pid_files=$(find "$PID_DIR" -name "framepack_*.pid" 2>/dev/null || true)
        if [[ -n "$pid_files" ]]; then
            print_info "清理 PID 文件..."
            for pid_file in $pid_files; do
                if [[ -f "$pid_file" ]]; then
                    local pid
                    if pid=$(cat "$pid_file" 2>/dev/null) && [[ -n "$pid" ]]; then
                        if ! is_process_running "$pid"; then
                            print_info "清理孤立的 PID 文件: $(basename "$pid_file")"
                            rm -f "$pid_file"
                        else
                            print_warning "跳過運行中的進程 PID 文件: $(basename "$pid_file") (PID: $pid)"
                        fi
                    else
                        print_info "清理無效的 PID 文件: $(basename "$pid_file")"
                        rm -f "$pid_file"
                    fi
                fi
            done
        fi
    fi

    print_success "清理完成"
}

# 顯示幫助信息
cmd_help() {
    echo "FramePack Service Manager - 跨平台版本"
    echo "支援 macOS (開發環境) 和 Ubuntu (部署環境)"
    echo ""
    echo "用法: $0 [COMMAND]"
    echo ""
    echo "命令:"
    echo "  start     啟動服務 (生產模式)"
    echo "  stop      停止服務"
    echo "  restart   重啟服務"
    echo "  status    檢查服務狀態"
    echo "  dev       開發模式 (互動式選擇)"
    echo "  gpu       顯示 GPU 信息"
    echo "  config    配置管理 (創建/編輯配置文件)"
    echo "  clean     清理系統文件 (PID 文件、鎖文件等)"
    echo "  help      顯示此幫助信息"
    echo ""
    echo "系統信息:"
    echo "  操作系統: $OS"
    echo "  工作目錄: $WORK_DIR"
    echo "  Python: $PYTHON_BIN"
    echo "  腳本: $SCRIPT_NAME"
    echo ""
    echo "服務配置:"
    echo "  監聽地址: $HOST"
    echo "  主端口: $DEFAULT_PORT"
    echo "  第二端口: $SECOND_PORT"
    echo "  認證用戶名: $USERNAME"
    echo "  認證密碼: $PASSWORD"
    echo ""
    echo "運行模式:"
    if [[ "$ENABLE_REMOTE" == "true" ]]; then
        echo "  模式: 遠端開發模式"
        echo "  遠端主機: $REMOTE_USER@$REMOTE_HOST"
        echo "  遠端 Python: $REMOTE_PYTHON"
        echo "  遠端項目目錄: $REMOTE_PROJECT_DIR"
    else
        echo "  模式: 本地模式"
        echo "  GPU 自動偵測: 啟用"
        if [[ ${#GPU_DEVICES[@]} -gt 0 ]]; then
            echo "  檢測到的 GPU: ${GPU_DEVICES[*]}"
            echo "  第二個 GPU 服務: $([ "$ENABLE_SECOND_GPU" = true ] && echo "自動啟用" || echo "未啟用")"
        else
            echo "  GPU 狀態: 將在啟動時自動偵測"
        fi
    fi
    echo ""
    echo "配置文件:"
    echo "  用戶配置: $CONFIG_FILE $([ -f "$CONFIG_FILE" ] && echo "(已載入)" || echo "(未找到)")"
    echo "  示例配置: ${CONFIG_FILE}.example"
    echo ""
    echo "環境變數:"
    if [[ "$IS_MACOS" == true ]]; then
        echo "  PYTORCH_ENABLE_MPS_FALLBACK: ${PYTORCH_ENABLE_MPS_FALLBACK:-未設置}"
        echo "  TOKENIZERS_PARALLELISM: ${TOKENIZERS_PARALLELISM:-未設置}"
    else
        echo "  TOKENIZERS_PARALLELISM: ${TOKENIZERS_PARALLELISM:-未設置}"
        echo "  CUDA_VISIBLE_DEVICES: ${CUDA_VISIBLE_DEVICES:-未設置}"
    fi
    echo ""
    echo "文件位置:"
    echo "  PID 文件: $PID_DIR"
    echo "  日誌文件: $LOG_DIR"
    echo "  鎖文件: $LOCK_DIR"
}
# =============================================================================
# Main Execution
# =============================================================================

# 信號處理和清理函數
cleanup() {
    print_info "接收到終止信號，正在清理..."
    cmd_stop
    cleanup_lock_files
    exit 0
}

# 清理所有鎖文件
cleanup_lock_files() {
    if [[ -d "$LOCK_DIR" ]]; then
        local lock_files
        lock_files=$(find "$LOCK_DIR" -name "framepack_*.lock" 2>/dev/null || true)
        if [[ -n "$lock_files" ]]; then
            print_info "清理鎖文件..."
            rm -f "$LOCK_DIR"/framepack_*.lock 2>/dev/null || true
        fi
    fi
}

# 設置信號處理
trap cleanup SIGINT SIGTERM

# 主函數
main() {
    local command="${1:-start}"

    case "$command" in
        start)
            cmd_start
            ;;
        stop)
            cmd_stop
            ;;
        restart)
            cmd_restart
            ;;
        status)
            cmd_status
            ;;
        dev)
            cmd_dev
            ;;
        gpu)
            cmd_gpu_info
            ;;
        config)
            cmd_config
            ;;
        clean)
            cmd_clean
            ;;
        help|--help|-h)
            cmd_help
            ;;
        *)
            print_error "未知命令: $command"
            echo ""
            cmd_help
            exit 1
            ;;
    esac
}

# 檢查是否以 root 身份運行（不建議）
if [[ $EUID -eq 0 ]]; then
    print_warning "不建議以 root 身份運行此腳本"
    read -p "是否繼續？(y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "已取消執行"
        exit 1
    fi
fi

# 執行主函數
main "$@"