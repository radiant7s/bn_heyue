#!/usr/bin/env python3
"""
check_aster_data.py - 检查aster数据库中的数据

查看aster表中是否有交易对数据
"""

from database import db

def main():
    """检查aster数据库数据"""
    print("=== 检查Aster数据库 ===")
    
    try:
        # 获取aster交易对
        aster_symbols = db.get_aster_symbols()
        
        print(f"Aster交易对总数: {len(aster_symbols)}")
        
        if aster_symbols:
            print("\n前10个Aster交易对:")
            for i, symbol_info in enumerate(aster_symbols[:10]):
                print(f"{i+1:2}. {symbol_info['symbol']} (状态: {symbol_info.get('status', 'N/A')})")
            
            if len(aster_symbols) > 10:
                print(f"... 还有 {len(aster_symbols) - 10} 个交易对")
                
            # 显示一些示例交易对名称
            symbol_names = [s['symbol'] for s in aster_symbols[:20]]
            print(f"\n示例交易对: {', '.join(symbol_names)}")
        else:
            print("❌ Aster数据库中没有交易对数据")
            print("请确保已经运行了相关脚本来导入aster交易对数据")
            
    except Exception as e:
        print(f"❌ 读取Aster数据失败: {e}")

if __name__ == "__main__":
    main()