#!/usr/bin/env python3
"""
oi_collector.py - 持仓量数据收集器

收集币安期货的持仓量数据，用于分析市场热度
"""

import requests
import time
from typing import List, Dict
from database import db

class OICollector:
    def __init__(self):
        self.base_url = "https://fapi.binance.com/fapi/v1"
        
    def get_symbol_oi(self, symbol: str) -> Dict:
        """获取单个合约的持仓量数据"""
        try:
            # 获取当前持仓量
            oi_url = f"{self.base_url}/openInterest"
            r = requests.get(oi_url, params={"symbol": symbol}, timeout=10)
            r.raise_for_status()
            oi_data = r.json()
            
            # 获取24h价格变化
            ticker_url = f"{self.base_url}/ticker/24hr"
            r = requests.get(ticker_url, params={"symbol": symbol}, timeout=10)
            r.raise_for_status()
            ticker_data = r.json()
            
            return {
                "symbol": symbol,
                "current_oi": float(oi_data["openInterest"]),
                "price_change_percent": float(ticker_data["priceChangePercent"]),
                "quote_volume": float(ticker_data["quoteVolume"]),
                "timestamp": int(time.time())
            }
            
        except Exception as e:
            print(f"获取 {symbol} 持仓量数据失败: {e}")
            return None
    
    def get_top_symbols_oi(self, symbols: List[str]) -> List[Dict]:
        """获取多个合约的持仓量数据"""
        oi_data = []
        
        for symbol in symbols:
            data = self.get_symbol_oi(symbol)
            if data:
                oi_data.append(data)
            time.sleep(0.1)  # 限速
        
        return oi_data
    
    def calculate_oi_top(self, symbols: List[str], limit: int = 20) -> List[Dict]:
        """计算持仓量排行榜"""
        oi_data = self.get_top_symbols_oi(symbols)
        
        # 按持仓量排序
        oi_data.sort(key=lambda x: x["current_oi"], reverse=True)
        
        # 生成排行榜
        top_list = []
        for rank, data in enumerate(oi_data[:limit], 1):
            # 模拟一些数据（在实际应用中，这些需要从历史数据计算）
            current_oi = data["current_oi"]
            
            top_list.append({
                "symbol": data["symbol"],
                "rank": rank,
                "current_oi": current_oi,
                "oi_delta": current_oi * 0.02,  # 模拟2%增长
                "oi_delta_percent": 2.0 + (rank * 0.1),  # 模拟变化百分比
                "oi_delta_value": current_oi * 0.02 * 50000,  # 模拟价值变化
                "price_delta_percent": data["price_change_percent"],
                "net_long": current_oi * 0.55,  # 模拟多头占55%
                "net_short": current_oi * 0.45   # 模拟空头占45%
            })
        
        return top_list

# 全局实例
oi_collector = OICollector()