#!/usr/bin/env python3
"""
MPS (Apple Silicon) 兼容性修復腳本
解決 avg_pool3d 操作不支持的問題
"""

import os
import sys

def setup_mps_fallback():
    """設置 MPS 回退環境變數"""
    print("🔧 設置 MPS 兼容性修復...")
    
    # 設置 MPS 回退
    os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
    os.environ['TOKENIZERS_PARALLELISM'] = 'false'
    
    print("✅ MPS 回退已啟用")
    print("✅ Tokenizers 並行已禁用")

def check_mps_support():
    """檢查 MPS 支持狀態"""
    try:
        import torch
        
        print(f"🔍 PyTorch 版本: {torch.__version__}")
        
        if torch.backends.mps.is_available():
            print("✅ MPS 後端可用")
            if torch.backends.mps.is_built():
                print("✅ MPS 後端已構建")
            else:
                print("⚠️ MPS 後端未構建")
        else:
            print("❌ MPS 後端不可用")
            
        # 檢查環境變數
        mps_fallback = os.environ.get("PYTORCH_ENABLE_MPS_FALLBACK")
        if mps_fallback == "1":
            print("✅ MPS 回退已啟用")
        else:
            print("⚠️ MPS 回退未啟用")
            
    except ImportError:
        print("❌ 無法導入 PyTorch")

def test_problematic_operation():
    """測試有問題的操作"""
    try:
        import torch
        
        print("🧪 測試 avg_pool3d 操作...")
        
        # 創建測試張量
        if torch.backends.mps.is_available():
            device = torch.device("mps")
        else:
            device = torch.device("cpu")
            
        # 測試 avg_pool3d
        x = torch.randn(1, 16, 4, 8, 8, device=device)
        
        try:
            result = torch.nn.functional.avg_pool3d(x, kernel_size=(2, 2, 2))
            print("✅ avg_pool3d 操作成功")
            return True
        except NotImplementedError as e:
            print(f"❌ avg_pool3d 操作失敗: {e}")
            return False
            
    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        return False

def apply_runtime_fix():
    """應用運行時修復"""
    print("🔧 應用運行時修復...")
    
    try:
        import torch
        import torch.nn.functional as F
        
        # 保存原始的 avg_pool3d 函數
        original_avg_pool3d = F.avg_pool3d
        
        def mps_compatible_avg_pool3d(input, kernel_size, stride=None, padding=0, 
                                     ceil_mode=False, count_include_pad=True, divisor_override=None):
            """MPS 兼容的 avg_pool3d 實現"""
            if input.device.type == 'mps':
                # 如果在 MPS 設備上，先移到 CPU 執行操作，然後移回 MPS
                cpu_input = input.cpu()
                result = original_avg_pool3d(
                    cpu_input, kernel_size, stride, padding, 
                    ceil_mode, count_include_pad, divisor_override
                )
                return result.to(input.device)
            else:
                # 其他設備正常執行
                return original_avg_pool3d(
                    input, kernel_size, stride, padding, 
                    ceil_mode, count_include_pad, divisor_override
                )
        
        # 替換函數
        F.avg_pool3d = mps_compatible_avg_pool3d
        torch.nn.functional.avg_pool3d = mps_compatible_avg_pool3d
        
        print("✅ 運行時修復已應用")
        return True
        
    except Exception as e:
        print(f"❌ 運行時修復失敗: {e}")
        return False

def main():
    """主函數"""
    print("🍎 MPS (Apple Silicon) 兼容性修復工具")
    print("=" * 50)
    
    # 設置環境變數
    setup_mps_fallback()
    
    print("\n" + "-" * 30)
    
    # 檢查 MPS 支持
    check_mps_support()
    
    print("\n" + "-" * 30)
    
    # 測試有問題的操作
    success = test_problematic_operation()
    
    if not success:
        print("\n" + "-" * 30)
        print("🔧 嘗試應用運行時修復...")
        
        if apply_runtime_fix():
            # 重新測試
            print("🧪 重新測試修復後的操作...")
            success = test_problematic_operation()
    
    print("\n" + "=" * 50)
    
    if success:
        print("🎉 MPS 兼容性問題已解決！")
        print("\n💡 建議:")
        print("1. 確保在啟動應用前設置環境變數")
        print("2. 使用修復後的入口文件啟動應用")
        print("3. 如果仍有問題，可以考慮使用 CPU 模式")
    else:
        print("⚠️ MPS 兼容性問題仍然存在")
        print("\n🔧 解決方案:")
        print("1. 確保 PYTORCH_ENABLE_MPS_FALLBACK=1 已設置")
        print("2. 考慮使用 CPU 模式: export CUDA_VISIBLE_DEVICES=''")
        print("3. 更新到最新版本的 PyTorch")
    
    print("\n🚀 現在可以嘗試運行:")
    print("python demo_gradio_f1_refactored.py")

if __name__ == "__main__":
    main()
