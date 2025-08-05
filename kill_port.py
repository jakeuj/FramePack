#!/usr/bin/env python3
"""
端口占用檢查和進程終止工具
用於解決 FramePack 啟動時的端口衝突問題
"""

import subprocess
import sys
import argparse
import re


def find_process_by_port(port):
    """根據端口號查找占用的進程"""
    try:
        # Linux/Unix 系統使用 lsof
        result = subprocess.run(
            ['lsof', '-ti', f':{port}'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            return [int(pid) for pid in pids if pid.strip()]
            
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        pass
    
    try:
        # 嘗試使用 netstat (適用於大多數系統)
        result = subprocess.run(
            ['netstat', '-tlnp'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            pids = []
            for line in result.stdout.split('\n'):
                if f':{port} ' in line:
                    # 提取 PID
                    match = re.search(r'(\d+)/', line)
                    if match:
                        pids.append(int(match.group(1)))
            return pids
            
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        pass
    
    try:
        # 嘗試使用 ss (現代 Linux 系統)
        result = subprocess.run(
            ['ss', '-tlnp', f'sport = :{port}'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            pids = []
            for line in result.stdout.split('\n'):
                match = re.search(r'pid=(\d+)', line)
                if match:
                    pids.append(int(match.group(1)))
            return pids
            
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        pass
    
    return []


def get_process_info(pid):
    """獲取進程詳細信息"""
    try:
        # 獲取進程命令行
        result = subprocess.run(
            ['ps', '-p', str(pid), '-o', 'pid,ppid,cmd', '--no-headers'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            return result.stdout.strip()
    except:
        pass
    
    return f"PID {pid} (無法獲取詳細信息)"


def kill_process(pid, force=False):
    """終止進程"""
    try:
        signal = 'SIGKILL' if force else 'SIGTERM'
        result = subprocess.run(
            ['kill', '-9' if force else '-15', str(pid)],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        return result.returncode == 0
    except:
        return False


def check_and_kill_port(port, force=False, auto_confirm=False):
    """檢查端口並終止占用的進程"""
    print(f"🔍 檢查端口 {port} 的占用情況...")
    
    pids = find_process_by_port(port)
    
    if not pids:
        print(f"✅ 端口 {port} 未被占用")
        return True
    
    print(f"⚠️  端口 {port} 被以下進程占用:")
    for pid in pids:
        info = get_process_info(pid)
        print(f"   PID {pid}: {info}")
    
    if not auto_confirm:
        response = input(f"\n是否要終止這些進程? (y/N): ").lower().strip()
        if response not in ['y', 'yes', '是']:
            print("❌ 用戶取消操作")
            return False
    
    success_count = 0
    for pid in pids:
        print(f"🔄 正在終止進程 {pid}...")
        if kill_process(pid, force):
            print(f"✅ 成功終止進程 {pid}")
            success_count += 1
        else:
            print(f"❌ 無法終止進程 {pid}")
            if not force:
                print(f"🔄 嘗試強制終止進程 {pid}...")
                if kill_process(pid, True):
                    print(f"✅ 強制終止進程 {pid} 成功")
                    success_count += 1
                else:
                    print(f"❌ 強制終止進程 {pid} 失敗")
    
    if success_count == len(pids):
        print(f"🎉 所有占用端口 {port} 的進程已成功終止")
        return True
    else:
        print(f"⚠️  部分進程終止失敗 ({success_count}/{len(pids)})")
        return False


def main():
    parser = argparse.ArgumentParser(description='檢查並終止占用指定端口的進程')
    parser.add_argument('port', type=int, help='要檢查的端口號')
    parser.add_argument('-f', '--force', action='store_true', help='強制終止進程 (使用 SIGKILL)')
    parser.add_argument('-y', '--yes', action='store_true', help='自動確認，不詢問用戶')
    
    args = parser.parse_args()
    
    if args.port < 1 or args.port > 65535:
        print("❌ 端口號必須在 1-65535 範圍內")
        sys.exit(1)
    
    print(f"🚀 端口占用檢查工具 - 端口 {args.port}")
    print("=" * 50)
    
    success = check_and_kill_port(args.port, args.force, args.yes)
    
    if success:
        print(f"\n✅ 端口 {args.port} 現在可用")
        sys.exit(0)
    else:
        print(f"\n❌ 無法釋放端口 {args.port}")
        sys.exit(1)


if __name__ == "__main__":
    main()
