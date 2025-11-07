#!/usr/bin/env python3
"""
cleanup.py - 手动清理数据库

使用方法:
python cleanup.py              # 清理超过24小时的数据
python cleanup.py --hours 12   # 清理超过12小时的数据
python cleanup.py --info       # 仅显示数据库信息，不清理
"""

import argparse
import time
from datetime import datetime, timedelta
from database import Database

def format_time(timestamp):
    """格式化时间戳为可读格式"""
    if timestamp:
        return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
    return "无数据"

def format_size(bytes_size):
    """格式化文件大小"""
    if bytes_size < 1024:
        return f"{bytes_size} B"
    elif bytes_size < 1024 * 1024:
        return f"{bytes_size/1024:.1f} KB"
    else:
        return f"{bytes_size/(1024*1024):.1f} MB"

def show_database_info(db):
    """显示数据库详细信息"""
    print("=== 数据库信息 ===")
    
    # 基础统计
    stats = db.get_symbol_stats()
    print(f"文件大小: {stats['file_size_mb']} MB")
    print(f"数据保留时间: {stats['max_age_hours']} 小时")
    print(f"监控合约数量: {stats['symbol_count']}")
    print(f"K线数据条数: {stats['kline_count']}")
    print(f"24小时异动数: {stats['anomaly_count_24h']}")
    
    # 详细信息
    size_info = db.get_data_size_info()
    print(f"\n=== 各表记录数 ===")
    print(f"K线数据: {size_info['records']['klines']}")
    print(f"异动数据: {size_info['records']['anomalies']}")
    print(f"AI选币: {size_info['records']['ai_coins']}")
    print(f"持仓量排行: {size_info['records']['oi_rankings']}")
    
    print(f"\n=== 最旧数据时间 ===")
    if size_info['oldest_data']['kline_time']:
        print(f"K线数据: {format_time(size_info['oldest_data']['kline_time'])}")
    if size_info['oldest_data']['anomaly_time']:
        print(f"异动数据: {format_time(size_info['oldest_data']['anomaly_time'])}")

def cleanup_database(hours):
    """清理数据库"""
    print(f"=== 清理超过 {hours} 小时的数据 ===")
    
    # 创建临时数据库实例
    temp_db = Database(max_age_hours=hours)
    
    # 显示清理前信息
    print("\n清理前状态:")
    show_database_info(temp_db)
    
    # 执行清理
    print(f"\n正在清理超过 {hours} 小时的数据...")
    temp_db.cleanup_old_data()
    
    # 显示清理后信息
    print("\n清理后状态:")
    show_database_info(temp_db)
    
    print("\n✅ 数据清理完成!")

def main():
    parser = argparse.ArgumentParser(description="数据库清理工具")
    parser.add_argument("--hours", type=float, default=24, 
                       help="清理超过指定小时数的数据 (默认: 24)")
    parser.add_argument("--info", action="store_true",
                       help="仅显示数据库信息，不执行清理")
    parser.add_argument("--force", action="store_true",
                       help="强制清理，不询问确认")
    
    args = parser.parse_args()
    
    if args.info:
        # 仅显示信息
        from database import db
        show_database_info(db)
        return
    
    # 确认清理操作
    if not args.force:
        print(f"将要清理超过 {args.hours} 小时的所有数据")
        confirm = input("确认执行清理? (y/N): ").lower()
        if confirm != 'y':
            print("取消清理操作")
            return
    
    # 执行清理
    cleanup_database(args.hours)

if __name__ == "__main__":
    main()