#!/usr/bin/env python3
"""
測試 MPS 修復是否有效
"""

import os
import sys

# 確保在導入 PyTorch 之前設置環境變數
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
os.environ['TOKENIZERS_PARALLELISM'] = 'false'

def test_app_import():
    """測試應用導入"""
    print("🧪 測試應用導入...")
    
    try:
        from apps import FramePackF1App
        app = FramePackF1App()
        print("✅ FramePackF1App 導入和實例化成功")
        return True
    except Exception as e:
        print(f"❌ 應用導入失敗: {e}")
        return False

def test_model_manager():
    """測試模型管理器"""
    print("🤖 測試模型管理器...")
    
    try:
        from core.model_manager import ModelManager
        
        # 使用測試路徑，不實際載入模型
        manager = ModelManager('test_path')
        print("✅ ModelManager 實例化成功")
        print(f"   High VRAM Mode: {manager.high_vram}")
        return True
    except Exception as e:
        print(f"❌ 模型管理器測試失敗: {e}")
        return False

def test_video_processor():
    """測試視頻處理器"""
    print("🎬 測試視頻處理器...")
    
    try:
        from core.video_processor import FramePackF1VideoProcessor
        from core.model_manager import ModelManager
        
        # 創建測試實例
        model_manager = ModelManager('test_path')
        processor = FramePackF1VideoProcessor(model_manager, './test_output')
        
        print("✅ FramePackF1VideoProcessor 實例化成功")
        return True
    except Exception as e:
        print(f"❌ 視頻處理器測試失敗: {e}")
        return False

def test_pytorch_mps():
    """測試 PyTorch MPS 功能"""
    print("🔥 測試 PyTorch MPS 功能...")
    
    try:
        import torch
        
        print(f"   PyTorch 版本: {torch.__version__}")
        
        if torch.backends.mps.is_available():
            print("   ✅ MPS 後端可用")
            
            # 測試基本張量操作
            device = torch.device("mps")
            x = torch.randn(2, 3, 4, device=device)
            y = x * 2
            print("   ✅ 基本 MPS 張量操作成功")
            
            # 測試有問題的 avg_pool3d 操作
            x_3d = torch.randn(1, 16, 4, 8, 8, device=device)
            try:
                result = torch.nn.functional.avg_pool3d(x_3d, kernel_size=(2, 2, 2))
                print("   ✅ avg_pool3d 操作成功（可能有回退警告）")
            except Exception as e:
                print(f"   ❌ avg_pool3d 操作失敗: {e}")
                return False
                
        else:
            print("   ⚠️ MPS 後端不可用，將使用 CPU")
            
        return True
    except Exception as e:
        print(f"❌ PyTorch MPS 測試失敗: {e}")
        return False

def main():
    """主測試函數"""
    print("🍎 MPS 修復驗證測試")
    print("=" * 40)
    
    # 檢查環境變數
    mps_fallback = os.environ.get("PYTORCH_ENABLE_MPS_FALLBACK")
    tokenizers_parallel = os.environ.get("TOKENIZERS_PARALLELISM")
    
    print(f"🔧 環境變數檢查:")
    print(f"   PYTORCH_ENABLE_MPS_FALLBACK: {mps_fallback}")
    print(f"   TOKENIZERS_PARALLELISM: {tokenizers_parallel}")
    
    if mps_fallback != "1":
        print("⚠️ MPS 回退未啟用")
    if tokenizers_parallel != "false":
        print("⚠️ Tokenizers 並行未禁用")
    
    print("\n" + "-" * 40)
    
    # 運行測試
    tests = [
        ("PyTorch MPS 功能", test_pytorch_mps),
        ("模型管理器", test_model_manager),
        ("視頻處理器", test_video_processor),
        ("應用導入", test_app_import),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}:")
        if test_func():
            passed += 1
        print()
    
    print("=" * 40)
    print(f"📊 測試結果: {passed}/{total} 通過")
    
    if passed == total:
        print("🎉 所有測試通過！MPS 修復有效！")
        print("\n🚀 現在可以安全地運行:")
        print("   python demo_gradio_f1_refactored.py")
        print("   或使用啟動腳本: ./start_framepack.sh")
        return True
    else:
        print("⚠️ 部分測試失敗，請檢查配置")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
