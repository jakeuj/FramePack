#!/bin/bash
# 端口占用檢查和進程終止腳本
# 使用方法: ./kill_port.sh <端口號> [選項]

set -e

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 顯示使用說明
show_usage() {
    echo "使用方法: $0 <端口號> [選項]"
    echo ""
    echo "選項:"
    echo "  -f, --force     強制終止進程 (不詢問確認)"
    echo "  -h, --help      顯示此幫助信息"
    echo ""
    echo "範例:"
    echo "  $0 7860         檢查並終止占用端口 7860 的進程"
    echo "  $0 7860 -f     強制終止占用端口 7860 的進程"
}

# 檢查端口占用
check_port() {
    local port=$1
    local pids=()
    
    echo -e "${BLUE}🔍 檢查端口 $port 的占用情況...${NC}"
    
    # 方法1: 使用 lsof
    if command -v lsof >/dev/null 2>&1; then
        while IFS= read -r pid; do
            [[ -n "$pid" ]] && pids+=("$pid")
        done < <(lsof -ti :$port 2>/dev/null || true)
    fi
    
    # 方法2: 使用 netstat (如果 lsof 沒找到結果)
    if [[ ${#pids[@]} -eq 0 ]] && command -v netstat >/dev/null 2>&1; then
        while IFS= read -r line; do
            if [[ "$line" == *":$port "* ]]; then
                pid=$(echo "$line" | grep -oE '[0-9]+/' | cut -d'/' -f1)
                [[ -n "$pid" ]] && pids+=("$pid")
            fi
        done < <(netstat -tlnp 2>/dev/null || true)
    fi
    
    # 方法3: 使用 ss (如果前面都沒找到)
    if [[ ${#pids[@]} -eq 0 ]] && command -v ss >/dev/null 2>&1; then
        while IFS= read -r line; do
            pid=$(echo "$line" | grep -oE 'pid=[0-9]+' | cut -d'=' -f2)
            [[ -n "$pid" ]] && pids+=("$pid")
        done < <(ss -tlnp "sport = :$port" 2>/dev/null || true)
    fi
    
    echo "${pids[@]}"
}

# 獲取進程信息
get_process_info() {
    local pid=$1
    if ps -p "$pid" >/dev/null 2>&1; then
        ps -p "$pid" -o pid,ppid,cmd --no-headers 2>/dev/null || echo "PID $pid (無法獲取詳細信息)"
    else
        echo "PID $pid (進程不存在)"
    fi
}

# 終止進程
kill_process() {
    local pid=$1
    local force=$2
    
    if [[ "$force" == "true" ]]; then
        kill -9 "$pid" 2>/dev/null
    else
        kill -15 "$pid" 2>/dev/null
    fi
}

# 主函數
main() {
    local port=""
    local force_kill=false
    
    # 解析參數
    while [[ $# -gt 0 ]]; do
        case $1 in
            -f|--force)
                force_kill=true
                shift
                ;;
            -h|--help)
                show_usage
                exit 0
                ;;
            -*)
                echo -e "${RED}❌ 未知選項: $1${NC}"
                show_usage
                exit 1
                ;;
            *)
                if [[ -z "$port" ]]; then
                    port=$1
                else
                    echo -e "${RED}❌ 太多參數${NC}"
                    show_usage
                    exit 1
                fi
                shift
                ;;
        esac
    done
    
    # 檢查端口號
    if [[ -z "$port" ]]; then
        echo -e "${RED}❌ 請指定端口號${NC}"
        show_usage
        exit 1
    fi
    
    if ! [[ "$port" =~ ^[0-9]+$ ]] || [[ "$port" -lt 1 ]] || [[ "$port" -gt 65535 ]]; then
        echo -e "${RED}❌ 端口號必須在 1-65535 範圍內${NC}"
        exit 1
    fi
    
    echo -e "${BLUE}🚀 端口占用檢查工具 - 端口 $port${NC}"
    echo "=================================================="
    
    # 檢查端口占用
    pids=($(check_port "$port"))
    
    if [[ ${#pids[@]} -eq 0 ]]; then
        echo -e "${GREEN}✅ 端口 $port 未被占用${NC}"
        exit 0
    fi
    
    echo -e "${YELLOW}⚠️  端口 $port 被以下進程占用:${NC}"
    for pid in "${pids[@]}"; do
        info=$(get_process_info "$pid")
        echo "   PID $pid: $info"
    done
    
    # 詢問是否終止進程
    if [[ "$force_kill" != "true" ]]; then
        echo ""
        read -p "是否要終止這些進程? (y/N): " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy是]$ ]]; then
            echo -e "${RED}❌ 用戶取消操作${NC}"
            exit 1
        fi
    fi
    
    # 終止進程
    success_count=0
    for pid in "${pids[@]}"; do
        echo -e "${BLUE}🔄 正在終止進程 $pid...${NC}"
        
        if kill_process "$pid" false; then
            sleep 1
            if ! ps -p "$pid" >/dev/null 2>&1; then
                echo -e "${GREEN}✅ 成功終止進程 $pid${NC}"
                ((success_count++))
            else
                echo -e "${YELLOW}🔄 嘗試強制終止進程 $pid...${NC}"
                if kill_process "$pid" true; then
                    sleep 1
                    if ! ps -p "$pid" >/dev/null 2>&1; then
                        echo -e "${GREEN}✅ 強制終止進程 $pid 成功${NC}"
                        ((success_count++))
                    else
                        echo -e "${RED}❌ 強制終止進程 $pid 失敗${NC}"
                    fi
                else
                    echo -e "${RED}❌ 無法終止進程 $pid${NC}"
                fi
            fi
        else
            echo -e "${RED}❌ 無法終止進程 $pid${NC}"
        fi
    done
    
    echo ""
    if [[ $success_count -eq ${#pids[@]} ]]; then
        echo -e "${GREEN}🎉 所有占用端口 $port 的進程已成功終止${NC}"
        echo -e "${GREEN}✅ 端口 $port 現在可用${NC}"
        exit 0
    else
        echo -e "${YELLOW}⚠️  部分進程終止失敗 ($success_count/${#pids[@]})${NC}"
        exit 1
    fi
}

# 執行主函數
main "$@"
