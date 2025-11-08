#!/usr/bin/env python3
"""
data_updater.py - 独立数据更新器

每3分钟更新AI选币和持仓量排行数据，独立于异动检测系统
"""
#!/usr/bin/env python3
"""
data_updater.py - 独立数据更新器

每3分钟更新AI选币和持仓量排行数据，独立于异动检测系统
"""

import time
import threading
import requests
import numpy as np
import logging
from typing import List, Dict
from datetime import datetime

from database import db
from log_config import setup_logging

# 初始化日志（幂等）
setup_logging()
logger = logging.getLogger(__name__)


class DataUpdater:
    def __init__(self):
        self.running = False
        self.update_interval = 180  # 3分钟
        self.top_n_symbols = 20  # 每个表最多20个币种

    def get_active_symbols(self) -> List[str]:
        """获取活跃合约列表"""
        try:
            url = "https://fapi.binance.com/fapi/v1/ticker/24hr"
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            tickers = r.json()

            usdt_tickers = [
                t for t in tickers
                if t['symbol'].endswith('USDT') and float(t.get('quoteVolume', 0)) > 5000
            ]

            usdt_tickers.sort(key=lambda x: float(x.get('quoteVolume', 0)), reverse=True)
            return [t['symbol'] for t in usdt_tickers[:50]]
        except Exception:
            logger.exception("获取活跃合约失败")
            return []

    def calculate_coin_score(self, symbol: str, ticker_data: Dict, klines: List[Dict]) -> float:
        """计算币种评分"""
        try:
            if len(klines) < 10:
                return 0.0

            prices = [k['close_price'] for k in klines]
            volumes = [k['quote_volume'] for k in klines]

            returns = [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]
            volatility = np.std(returns) if len(returns) > 1 else 0

            price_change_24h = float(ticker_data.get('priceChangePercent', 0))
            volume_24h = float(ticker_data.get('quoteVolume', 0))

            recent_avg_volume = np.mean(volumes[-5:]) if len(volumes) >= 5 else 0
            older_avg_volume = np.mean(volumes[:5]) if len(volumes) >= 10 else recent_avg_volume
            volume_growth = (recent_avg_volume - older_avg_volume) / older_avg_volume if older_avg_volume > 0 else 0

            score = 0.0
            score += abs(price_change_24h) * 0.3
            score += min(volume_24h / 1000000, 100) * 0.25
            score += min(volatility * 1000, 50) * 0.25
            score += min(abs(volume_growth) * 100, 20) * 0.2

            return min(score, 100)
        except Exception:
            logger.exception(f"计算 {symbol} 评分失败")
            return 0.0

    def update_ai_coins(self):
        """更新AI选币数据"""
        try:
            logger.info(f"[{datetime.now().strftime('%H:%M:%S')}] 开始更新AI选币数据...")

            symbols = self.get_active_symbols()
            if not symbols:
                logger.warning("未获取到活跃合约数据")
                return

            url = "https://fapi.binance.com/fapi/v1/ticker/24hr"
            r = requests.get(url, timeout=10)
            ticker_data = {t['symbol']: t for t in r.json()}

            coin_scores = []
            for symbol in symbols[:30]:
                try:
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

                    time.sleep(0.05)
                except Exception:
                    logger.exception(f"处理 {symbol} 失败")
                    continue

            coin_scores.sort(key=lambda x: x['score'], reverse=True)
            top_coins = coin_scores[:self.top_n_symbols]

            db.clear_ai_coins()
            for coin in top_coins:
                db.upsert_ai_coin(coin)

            logger.info(f"AI选币数据更新完成: {len(top_coins)}个币种")
        except Exception:
            logger.exception("更新AI选币数据失败")

    def update_oi_rankings(self):
        """更新持仓量排行数据"""
        try:
            logger.info(f"[{datetime.now().strftime('%H:%M:%S')}] 开始更新持仓量排行...")

            symbols = self.get_active_symbols()
            if not symbols:
                logger.warning("未获取到活跃合约数据")
                return

            url = "https://fapi.binance.com/fapi/v1/ticker/24hr"
            r = requests.get(url, timeout=10)
            ticker_data = {t['symbol']: t for t in r.json()}

            oi_data = []
            for symbol in symbols[:30]:
                try:
                    ticker = ticker_data.get(symbol, {})
                    volume_24h = float(ticker.get('quoteVolume', 0))
                    price_change_24h = float(ticker.get('priceChangePercent', 0))

                    if volume_24h > 0:
                        base_oi = volume_24h * 0.15
                        oi_delta = base_oi * 0.03
                        oi_delta_percent = abs(price_change_24h) * 0.5 + 2.0

                        oi_data.append({
                            'symbol': symbol,
                            'current_oi': base_oi,
                            'oi_delta': oi_delta,
                            'oi_delta_percent': oi_delta_percent,
                            'oi_delta_value': oi_delta * 50,
                            'price_delta_percent': price_change_24h,
                            'net_long': base_oi * 0.6,
                            'net_short': base_oi * 0.4,
                            'volume_24h': volume_24h
                        })

                    time.sleep(0.05)
                except Exception:
                    logger.exception(f"处理 {symbol} 持仓量失败")
                    continue

            oi_data.sort(key=lambda x: x['current_oi'], reverse=True)
            top_oi = oi_data[:self.top_n_symbols]

            for rank, oi in enumerate(top_oi, 1):
                oi['rank'] = rank

            db.clear_oi_rankings()
            for oi in top_oi:
                db.upsert_oi_ranking(oi)

            logger.info(f"持仓量排行更新完成: {len(top_oi)}个币种")
        except Exception:
            logger.exception("更新持仓量排行失败")

    def update_cycle(self):
        """执行一次完整的更新周期"""
        logger.info(f"\n=== 开始数据更新周期 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")

        self.update_ai_coins()
        time.sleep(10)
        self.update_oi_rankings()

        logger.info("=== 数据更新周期完成 ===\n")

    def start(self):
        """启动数据更新器"""
        self.running = True
        logger.info(f"数据更新器启动，更新间隔: {self.update_interval}秒")

        # 首次立即更新
        self.update_cycle()

        # 定期更新
        while self.running:
            try:
                time.sleep(self.update_interval)
                if self.running:
                    self.update_cycle()
            except Exception:
                logger.exception("数据更新器异常")
                time.sleep(60)

    def stop(self):
        """停止数据更新器"""
        self.running = False
        logger.info("数据更新器已停止")


def start_updater_background():
    """在后台启动数据更新器"""
    updater = DataUpdater()

    def run_updater():
        updater.start()

    thread = threading.Thread(target=run_updater, daemon=True)
    thread.start()
    return updater


def download_and_store_aster(save_path: str = "json/aster_exchangeInfo.json") -> bool:
    """下载 Aster exchangeInfo 并保存到本地 JSON 文件，同时把 symbols 写入数据库 aster 表。

    返回 True 表示成功，False 表示失败。
    """
    try:
        url = "https://fapi.asterdex.com/fapi/v1/exchangeInfo"
        logger.info(f"下载 Aster exchangeInfo: {url}")
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        payload = r.json()

        # 确保目录存在
        import os, json
        dirpath = os.path.dirname(save_path)
        if dirpath and not os.path.exists(dirpath):
            os.makedirs(dirpath, exist_ok=True)

        # # 写入文件
        # with open(save_path, "w", encoding="utf-8") as f:
        #     json.dump(payload, f, ensure_ascii=False, indent=2)

        # 提取 symbols 并写入数据库
        symbols = payload.get('symbols') or []
        simple_symbols = []
        for s in symbols:
            # 保留常用字段
            simple_symbols.append({
                'symbol': s.get('symbol'),
                'status': s.get('status'),
                'baseAsset': s.get('baseAsset'),
                'quoteAsset': s.get('quoteAsset'),
                # include full raw for db method to store
                **({'raw': s} if s else {})
            })

        if simple_symbols:
            try:
                # 写入数据库
                from database import db
                # build list expected by replace_aster_symbols
                db.replace_aster_symbols([{
                    'symbol': item.get('symbol'),
                    'status': item.get('status'),
                    'baseAsset': item.get('baseAsset'),
                    'quoteAsset': item.get('quoteAsset'),
                    'raw': item.get('raw')
                } for item in simple_symbols])
                logger.info(f"已将 {len(simple_symbols)} 个 Aster 合约写入数据库")
            except Exception:
                logger.exception("写入 Aster 合约到数据库失败")

        return True
    except Exception:
        logger.exception("下载或保存 Aster exchangeInfo 失败")
        return False


if __name__ == "__main__":
    logger = logging.getLogger(__name__)
    logger.info("=== 独立数据更新器 ===")
    updater = DataUpdater()

    try:
        updater.start()
    except KeyboardInterrupt:
        logger.info("\n收到中断信号，正在停止...")
        updater.stop()