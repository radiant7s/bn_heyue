#!/usr/bin/env python3
"""
data_updater.py - 独立数据更新器

每3分钟更新AI选币和持仓量排行数据，独立于异动检测系统
"""

import time
import threading
import requests
import numpy as np
from typing import List, Dict
from datetime import datetime

from database import db

class DataUpdater:
    def __init__(self):
        self.running = False
        self.update_interval = 180  # 3分钟
        self.top_n_symbols = 20  # 每个表最多20个币种
        
    def get_active_symbols(self) -> List[str]:
        """获取活跃合约列表"""
        try:
            # 获取24h ticker数据
            url = "https://fapi.binance.com/fapi/v1/ticker/24hr"
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            tickers = r.json()
            
            # 过滤USDT永续合约并按成交量排序
            usdt_tickers = [
                t for t in tickers 
                if t['symbol'].endswith('USDT') and float(t.get('quoteVolume', 0)) > 5000
            ]
            
            # 按成交量排序
            usdt_tickers.sort(key=lambda x: float(x.get('quoteVolume', 0)), reverse=True)
            
            return [t['symbol'] for t in usdt_tickers[:50]]  # 取前50个活跃合约
            
        except Exception as e:
            print(f"获取活跃合约失败: {e}")
            return []
    
    def calculate_coin_score(self, symbol: str, ticker_data: Dict, klines: List[Dict]) -> float:
        """计算币种评分"""
        try:
            if len(klines) < 10:
                return 0.0
            
            # 价格相关指标
            prices = [k['close_price'] for k in klines]
            volumes = [k['quote_volume'] for k in klines]
            
            # 计算收益率波动
            returns = [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]
            volatility = np.std(returns) if len(returns) > 1 else 0
            
            # 计算趋势强度
            price_change_24h = float(ticker_data.get('priceChangePercent', 0))
            volume_24h = float(ticker_data.get('quoteVolume', 0))
            
            # 计算成交量增长
            recent_avg_volume = np.mean(volumes[-5:]) if len(volumes) >= 5 else 0
            older_avg_volume = np.mean(volumes[:5]) if len(volumes) >= 10 else recent_avg_volume
            volume_growth = (recent_avg_volume - older_avg_volume) / older_avg_volume if older_avg_volume > 0 else 0
            
            # 综合评分
            score = 0.0
            
            # 价格变化权重 (30%)
            score += abs(price_change_24h) * 0.3
            
            # 成交量权重 (25%)
            score += min(volume_24h / 1000000, 100) * 0.25  # 归一化成交量
            
            # 波动率权重 (25%)
            score += min(volatility * 1000, 50) * 0.25  # 归一化波动率
            
            # 成交量增长权重 (20%)
            score += min(abs(volume_growth) * 100, 20) * 0.2
            
            return min(score, 100)  # 限制最高100分
            
        except Exception as e:
            print(f"计算 {symbol} 评分失败: {e}")
            return 0.0
    
    def update_ai_coins(self):
        """更新AI选币数据"""
        try:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 开始更新AI选币数据...")
            
            # 获取活跃合约
            symbols = self.get_active_symbols()
            if not symbols:
                print("未获取到活跃合约数据")
                return
            
            # 获取24h ticker数据
            url = "https://fapi.binance.com/fapi/v1/ticker/24hr"
            r = requests.get(url, timeout=10)
            ticker_data = {t['symbol']: t for t in r.json()}
            
            coin_scores = []
            
            for symbol in symbols[:30]:  # 处理前30个合约
                try:
                    # 获取K线数据
                    klines = db.get_recent_klines(symbol, 16)
                    if not klines:
                        continue
                    
                    ticker = ticker_data.get(symbol, {})
                    score = self.calculate_coin_score(symbol, ticker, klines)
                    
                    if score > 0:
                        start_price = klines[0]['close_price']
                        current_price = klines[-1]['close_price']
                        max_price = max([k['high_price'] for k in klines])
                        
                        increase_percent = ((current_price - start_price) / start_price) * 100
                        volume_24h = float(ticker.get('quoteVolume', 0))
                        price_change_24h = float(ticker.get('priceChangePercent', 0))
                        
                        coin_scores.append({
                            'symbol': symbol,
                            'score': score,
                            'start_time': klines[0]['open_time'] // 1000,
                            'start_price': start_price,
                            'current_price': current_price,
                            'max_price': max_price,
                            'increase_percent': increase_percent,
                            'volume_24h': volume_24h,
                            'price_change_24h': price_change_24h
                        })
                    
                    time.sleep(0.05)  # 限速
                    
                except Exception as e:
                    print(f"处理 {symbol} 失败: {e}")
                    continue
            
            # 按评分排序并取前20个
            coin_scores.sort(key=lambda x: x['score'], reverse=True)
            top_coins = coin_scores[:self.top_n_symbols]
            
            # 清空旧数据并插入新数据
            db.clear_ai_coins()
            for coin in top_coins:
                db.upsert_ai_coin(coin)
            
            print(f"AI选币数据更新完成: {len(top_coins)}个币种")
            
        except Exception as e:
            print(f"更新AI选币数据失败: {e}")
    
    def update_oi_rankings(self):
        """更新持仓量排行数据"""
        try:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 开始更新持仓量排行...")
            
            # 获取活跃合约
            symbols = self.get_active_symbols()
            if not symbols:
                print("未获取到活跃合约数据")
                return
            
            # 获取24h ticker数据
            url = "https://fapi.binance.com/fapi/v1/ticker/24hr"
            r = requests.get(url, timeout=10)
            ticker_data = {t['symbol']: t for t in r.json()}
            
            oi_data = []
            
            for symbol in symbols[:30]:  # 处理前30个合约
                try:
                    ticker = ticker_data.get(symbol, {})
                    volume_24h = float(ticker.get('quoteVolume', 0))
                    price_change_24h = float(ticker.get('priceChangePercent', 0))
                    
                    if volume_24h > 0:
                        # 基于成交量模拟持仓量数据
                        base_oi = volume_24h * 0.15  # 模拟持仓量为成交量的15%
                        oi_delta = base_oi * 0.03  # 模拟3%变化
                        oi_delta_percent = abs(price_change_24h) * 0.5 + 2.0  # 基于价格变化模拟
                        
                        oi_data.append({
                            'symbol': symbol,
                            'current_oi': base_oi,
                            'oi_delta': oi_delta,
                            'oi_delta_percent': oi_delta_percent,
                            'oi_delta_value': oi_delta * 50,  # 模拟价值
                            'price_delta_percent': price_change_24h,
                            'net_long': base_oi * 0.6,  # 60%多头
                            'net_short': base_oi * 0.4,  # 40%空头
                            'volume_24h': volume_24h
                        })
                    
                    time.sleep(0.05)  # 限速
                    
                except Exception as e:
                    print(f"处理 {symbol} 持仓量失败: {e}")
                    continue
            
            # 按持仓量排序并分配排名
            oi_data.sort(key=lambda x: x['current_oi'], reverse=True)
            top_oi = oi_data[:self.top_n_symbols]
            
            # 分配排名
            for rank, oi in enumerate(top_oi, 1):
                oi['rank'] = rank
            
            # 清空旧数据并插入新数据
            db.clear_oi_rankings()
            for oi in top_oi:
                db.upsert_oi_ranking(oi)
            
            print(f"持仓量排行更新完成: {len(top_oi)}个币种")
            
        except Exception as e:
            print(f"更新持仓量排行失败: {e}")
    
    def update_cycle(self):
        """执行一次完整的更新周期"""
        print(f"\n=== 开始数据更新周期 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
        
        # 更新AI选币数据
        self.update_ai_coins()
        
        time.sleep(10)  # 间隔10秒
        
        # 更新持仓量排行
        self.update_oi_rankings()
        
        print("=== 数据更新周期完成 ===\n")
    
    def start(self):
        """启动数据更新器"""
        self.running = True
        print(f"数据更新器启动，更新间隔: {self.update_interval}秒")
        
        # 首次立即更新
        self.update_cycle()
        
        # 定期更新
        while self.running:
            try:
                time.sleep(self.update_interval)
                if self.running:
                    self.update_cycle()
            except Exception as e:
                print(f"数据更新器异常: {e}")
                time.sleep(60)  # 出错后等待1分钟再继续
    
    def stop(self):
        """停止数据更新器"""
        self.running = False
        print("数据更新器已停止")

def start_updater_background():
    """在后台启动数据更新器"""
    updater = DataUpdater()
    
    def run_updater():
        updater.start()
    
    thread = threading.Thread(target=run_updater, daemon=True)
    thread.start()
    return updater

if __name__ == "__main__":
    print("=== 独立数据更新器 ===")
    updater = DataUpdater()
    
    try:
        updater.start()
    except KeyboardInterrupt:
        print("\n收到中断信号，正在停止...")
        updater.stop()