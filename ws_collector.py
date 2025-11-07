#!/usr/bin/env python3
"""
ws_collector.py - WebSocket数据收集器

通过币安WebSocket实时收集15分钟K线数据并存储到数据库
"""

import json
import time
import threading
import requests
from typing import List, Dict
import websocket

from database import db

class BinanceWSCollector:
    def __init__(self):
        self.ws = None
        self.symbols = []
        self.running = False
        self.reconnect_count = 0
        self.max_reconnects = 10
        
        # 配置
        self.config = {
            "MIN_VOL_24H": 5000.0,  # 最小24h成交量筛选
            "TOP_N_SYMBOLS": 150,   # 监控的合约数量
            "HISTORY_KLINES": 16,   # 初始化时获取的历史K线数量
        }
    
    def fetch_initial_klines(self, symbols: List[str]):
        """获取所有合约的初始历史K线数据（仅当不足时才获取）"""
        print(f"检查 {len(symbols)} 个合约的历史K线数据...")
        
        # 先检查哪些合约需要补充历史数据
        symbols_to_fetch = []
        for symbol in symbols:
            current_count = db.get_symbol_kline_count(symbol)
            if current_count < self.config["HISTORY_KLINES"]:
                symbols_to_fetch.append(symbol)
                print(f"  {symbol}: 当前{current_count}条，需要补充")
            else:
                print(f"  {symbol}: 已有{current_count}条，跳过")
        
        if not symbols_to_fetch:
            print("所有合约都有足够的历史数据，跳过初始化步骤")
            return
        
        print(f"需要获取历史数据的合约: {len(symbols_to_fetch)}个")
        
        total = len(symbols_to_fetch)
        for idx, symbol in enumerate(symbols_to_fetch, 1):
            try:
                print(f"[{idx}/{total}] 获取 {symbol} 历史K线...", end="")
                
                # 获取历史K线数据
                url = "https://fapi.binance.com/fapi/v1/klines"
                params = {
                    "symbol": symbol,
                    "interval": "15m",
                    "limit": self.config["HISTORY_KLINES"]
                }
                
                r = requests.get(url, params=params, timeout=10)
                r.raise_for_status()
                klines_data = r.json()
                
                # 保存到数据库（去重由数据库UNIQUE约束处理）
                saved_count = 0
                for kline_raw in klines_data:
                    kline_record = {
                        "open_time": int(kline_raw[0]),
                        "close_time": int(kline_raw[6]),
                        "open_price": float(kline_raw[1]),
                        "high_price": float(kline_raw[2]),
                        "low_price": float(kline_raw[3]),
                        "close_price": float(kline_raw[4]),
                        "volume": float(kline_raw[5]),
                        "quote_volume": float(kline_raw[7]),
                        "trades_count": int(kline_raw[8])
                    }
                    
                    # INSERT OR REPLACE 自动处理重复数据
                    db.insert_kline(symbol, kline_record)
                    saved_count += 1
                
                print(f" ✓ {saved_count}条")
                
                # 简单限速避免请求过快
                time.sleep(0.05)
                
            except Exception as e:
                print(f" ✗ 失败: {e}")
                continue
        
        print("历史K线数据初始化完成!")
        
        # 显示统计信息
        stats = db.get_symbol_stats()
        print(f"数据库统计: {stats['symbol_count']}个合约, {stats['kline_count']}条K线数据")
    
    def get_active_symbols(self) -> List[str]:
        """获取活跃的USDT永续合约列表"""
        print("获取活跃合约列表...")
        
        # 获取合约信息
        exchange_url = "https://fapi.binance.com/fapi/v1/exchangeInfo"
        r = requests.get(exchange_url, timeout=10)
        r.raise_for_status()
        exchange_data = r.json()
        
        perpetual_symbols = [
            s["symbol"] for s in exchange_data.get("symbols", [])
            if (s.get("contractType") == "PERPETUAL" and 
                s.get("quoteAsset") == "USDT" and 
                s.get("status") == "TRADING")
        ]
        
        # 获取24h成交额数据
        ticker_url = "https://fapi.binance.com/fapi/v1/ticker/24hr"
        r = requests.get(ticker_url, timeout=10)
        r.raise_for_status()
        ticker_data = r.json()
        
        # 过滤并排序
        symbol_volumes = {}
        for ticker in ticker_data:
            symbol = ticker["symbol"]
            if symbol in perpetual_symbols:
                quote_volume = float(ticker.get("quoteVolume", 0) or 0)
                if quote_volume >= self.config["MIN_VOL_24H"]:
                    symbol_volumes[symbol] = quote_volume
        
        # 按成交额排序，取前N个
        sorted_symbols = sorted(symbol_volumes.items(), key=lambda x: x[1], reverse=True)
        top_symbols = [symbol for symbol, _ in sorted_symbols[:self.config["TOP_N_SYMBOLS"]]]
        
        print(f"筛选出 {len(top_symbols)} 个活跃合约（24h成交额 >= {self.config['MIN_VOL_24H']} USDT）")
        return top_symbols
    
    def create_stream_url(self, symbols: List[str]) -> str:
        """创建WebSocket流URL"""
        # 构建15分钟K线流
        streams = [f"{symbol.lower()}@kline_15m" for symbol in symbols]
        base_url = "wss://fstream.binance.com/stream?streams="
        return base_url + "/".join(streams)
    
    def on_message(self, ws, message):
        """处理WebSocket消息"""
        try:
            data = json.loads(message)
            stream = data.get("stream", "")
            kline_data = data.get("data", {}).get("k", {})
            
            if not kline_data:
                return
            
            symbol = kline_data["s"]
            is_closed = kline_data.get("x", False)  # x表示该K线是否闭合
            
            # 构建K线数据
            kline_record = {
                "open_time": int(kline_data["t"]),
                "close_time": int(kline_data["T"]),
                "open_price": float(kline_data["o"]),
                "high_price": float(kline_data["h"]),
                "low_price": float(kline_data["l"]),
                "close_price": float(kline_data["c"]),
                "volume": float(kline_data["v"]),
                "quote_volume": float(kline_data["q"]),
                "trades_count": int(kline_data["n"])
            }
            
            # 存储到数据库（INSERT OR REPLACE自动处理重复数据）
            # 数据库UNIQUE(symbol, open_time)约束确保去重
            db.insert_kline(symbol, kline_record)
            
            current_time = time.strftime("%H:%M:%S")
            status = "闭合" if is_closed else "更新"
            print(f"[{current_time}] {symbol} 15m K线{status}: {kline_record['close_price']:.4f}, 成交额: {kline_record['quote_volume']:.0f}")
            
        except Exception as e:
            print(f"处理消息错误: {e}")
    
    def on_error(self, ws, error):
        """处理WebSocket错误"""
        print(f"WebSocket错误: {error}")
    
    def on_close(self, ws, close_status_code, close_msg):
        """WebSocket连接关闭"""
        print(f"WebSocket连接关闭: {close_status_code}, {close_msg}")
        if self.running and self.reconnect_count < self.max_reconnects:
            print(f"准备重连... (第{self.reconnect_count + 1}次)")
            time.sleep(5)
            self.reconnect_count += 1
            self.start()
    
    def on_open(self, ws):
        """WebSocket连接打开"""
        print("WebSocket连接已建立")
        self.reconnect_count = 0
    
    def start(self):
        """启动WebSocket收集器"""
        if self.running:
            return
            
        self.running = True
        
        try:
            # 获取要监控的合约
            self.symbols = self.get_active_symbols()
            
            if not self.symbols:
                print("没有找到符合条件的合约")
                return
            
            # 首先获取历史K线数据填充数据库
            self.fetch_initial_klines(self.symbols)
            
            # 创建WebSocket连接
            url = self.create_stream_url(self.symbols)
            print(f"连接到: {url[:100]}...")
            
            self.ws = websocket.WebSocketApp(
                url,
                on_message=self.on_message,
                on_error=self.on_error,
                on_close=self.on_close,
                on_open=self.on_open
            )
            
            # 启动WebSocket（这会阻塞当前线程）
            self.ws.run_forever()
            
        except Exception as e:
            print(f"启动WebSocket收集器失败: {e}")
            self.running = False
    
    def stop(self):
        """停止WebSocket收集器"""
        self.running = False
        if self.ws:
            self.ws.close()
        print("WebSocket收集器已停止")

def start_collector_background():
    """在后台线程启动收集器"""
    collector = BinanceWSCollector()
    
    def run_collector():
        while True:
            try:
                collector.start()
            except Exception as e:
                print(f"收集器异常: {e}")
                time.sleep(10)  # 等待10秒后重试
    
    thread = threading.Thread(target=run_collector, daemon=True)
    thread.start()
    return collector

if __name__ == "__main__":
    print("=== 币安WebSocket数据收集器 ===")
    
    collector = BinanceWSCollector()
    
    try:
        collector.start()
    except KeyboardInterrupt:
        print("\n收到中断信号，正在停止...")
        collector.stop()