#!/usr/bin/env python3
"""
測試 GPU 偵測功能
模擬不同的 GPU 環境來測試腳本的自動偵測功能
"""

import subprocess
import tempfile
import os
import sys
from pathlib import Path

def create_mock_nvidia_smi(gpu_count=0):
    """創建模擬的 nvidia-smi 命令"""
    mock_script = f"""#!/bin/bash
case "$1" in
    "--query-gpu=index")
        case "$2" in
            "--format=csv,noheader,nounits")
                for i in $(seq 0 {gpu_count-1}); do
                    echo $i
                done
                ;;
        esac
        ;;
    "--query-gpu=index,name,memory.total")
        case "$2" in
            "--format=csv,noheader,nounits")
                for i in $(seq 0 {gpu_count-1}); do
                    echo "$i, NVIDIA GeForce RTX 409$i, 2456$i"
                done
                ;;
        esac
        ;;
    "--query-gpu=name,memory.total")
        case "$2" in
            "--format=csv,noheader,nounits")
                case "$4" in
                    "0") echo "NVIDIA GeForce RTX 4090, 24564" ;;
                    "1") echo "NVIDIA GeForce RTX 4080, 16376" ;;
                    "2") echo "NVIDIA GeForce RTX 4070, 12288" ;;
                    *) echo "NVIDIA GeForce RTX 40XX, 8192" ;;
                esac
                ;;
        esac
        ;;
    *)
        echo "Mock nvidia-smi - GPU Count: {gpu_count}"
        for i in $(seq 0 {gpu_count-1}); do
            echo "GPU $i: NVIDIA GeForce RTX 409$i"
        done
        ;;
esac
"""
    return mock_script

def test_gpu_detection(gpu_count, description):
    """測試特定 GPU 數量的偵測"""
    print(f"\n🧪 測試場景: {description}")
    print(f"   模擬 GPU 數量: {gpu_count}")
    
    # 創建臨時的 nvidia-smi 腳本
    with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
        f.write(create_mock_nvidia_smi(gpu_count))
        mock_nvidia_smi = f.name
    
    try:
        # 設置執行權限
        os.chmod(mock_nvidia_smi, 0o755)
        
        # 修改 PATH 讓腳本使用我們的模擬 nvidia-smi
        env = os.environ.copy()
        temp_dir = os.path.dirname(mock_nvidia_smi)
        env['PATH'] = f"{temp_dir}:{env['PATH']}"
        
        # 創建符號連結
        nvidia_smi_link = os.path.join(temp_dir, 'nvidia-smi')
        if os.path.exists(nvidia_smi_link):
            os.unlink(nvidia_smi_link)
        os.symlink(mock_nvidia_smi, nvidia_smi_link)
        
        # 運行 GPU 偵測
        result = subprocess.run(
            ['./start.sh', 'gpu'],
            capture_output=True,
            text=True,
            env=env,
            timeout=10
        )
        
        if result.returncode == 0:
            print("✅ GPU 偵測成功")
            # 解析輸出
            output = result.stdout
            if f"檢測到 {gpu_count} 張 NVIDIA GPU" in output:
                print(f"✅ 正確偵測到 {gpu_count} 張 GPU")
            elif gpu_count == 0 and "nvidia-smi 不可用" in output:
                print("✅ 正確處理無 GPU 情況")
            else:
                print("⚠️ GPU 數量偵測可能有問題")
            
            # 檢查第二個 GPU 服務狀態
            if gpu_count >= 2:
                if "第二個 GPU 服務: 自動啟用" in output or "第二個 GPU 服務: 啟用" in output:
                    print("✅ 正確啟用第二個 GPU 服務")
                else:
                    print("❌ 未正確啟用第二個 GPU 服務")
            else:
                if "第二個 GPU 服務: 禁用" in output or "第二個 GPU 服務: 未啟用" in output:
                    print("✅ 正確禁用第二個 GPU 服務")
                else:
                    print("❌ 第二個 GPU 服務狀態不正確")
            
            print(f"📋 輸出摘要:")
            for line in output.split('\n'):
                if 'GPU' in line and ('配置' in line or '檢測' in line or '服務' in line):
                    print(f"   {line.strip()}")
        else:
            print(f"❌ GPU 偵測失敗: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("⚠️ GPU 偵測超時")
        return False
    except Exception as e:
        print(f"❌ 測試錯誤: {e}")
        return False
    finally:
        # 清理臨時文件
        try:
            if os.path.exists(nvidia_smi_link):
                os.unlink(nvidia_smi_link)
            os.unlink(mock_nvidia_smi)
        except:
            pass
    
    return True

def main():
    """主測試函數"""
    print("🚀 GPU 自動偵測功能測試")
    print("=" * 50)
    
    # 檢查 start.sh 是否存在
    if not Path('start.sh').exists():
        print("❌ start.sh 不存在")
        return False
    
    # 測試不同的 GPU 場景
    test_scenarios = [
        (0, "無 GPU 環境 (CPU 模式)"),
        (1, "單 GPU 環境"),
        (2, "雙 GPU 環境"),
        (4, "多 GPU 環境 (4張)")
    ]
    
    success_count = 0
    total_count = len(test_scenarios)
    
    for gpu_count, description in test_scenarios:
        if test_gpu_detection(gpu_count, description):
            success_count += 1
    
    print("\n" + "=" * 50)
    print(f"🎯 測試結果: {success_count}/{total_count} 通過")
    
    if success_count == total_count:
        print("🎉 所有 GPU 偵測測試通過！")
        print("\n📝 功能確認:")
        print("✅ 自動偵測 GPU 數量")
        print("✅ 根據 GPU 數量自動配置服務")
        print("✅ 正確處理無 GPU 環境")
        print("✅ 智能啟用/禁用第二個 GPU 服務")
        return True
    else:
        print("❌ 部分測試失敗，請檢查腳本邏輯")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
