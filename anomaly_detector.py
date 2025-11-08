#!/usr/bin/env python3
"""
anomaly_detector.py - 异动检测后台任务

每分钟从数据库读取K线数据，计算异动并更新异动汇总表
"""

import time
import threading
import schedule
import numpy as np
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import List, Dict, Optional
from datetime import datetime

from database import db
from log_config import setup_logging

# 初始化日志（幂等）
setup_logging()
import logging
logger = logging.getLogger(__name__)

class AnomalyDetector:
    def __init__(self):
        self.config = {
            # 多维度异动判断阈值（与原脚本保持一致）
            "PRICE_Z_THRESHOLD": 2.5,
            "PRICE_PERCENTILE": 92.0,
            "VOLUME_Z_THRESHOLD": 2.0,
            "VOLATILITY_Z_THRESHOLD": 2.0,
            "MIN_ABS_RETURN": 0.005,
            
            # 综合评分权重
            "WEIGHT_PRICE": 0.4,
            "WEIGHT_VOLUME": 0.3,
            "WEIGHT_VOLATILITY": 0.3,
            "ANOMALY_SCORE_THRESHOLD": 0.5,  # 降低阈值，让更多数据被记录
            
            # 数据要求
            "MIN_KLINES_REQUIRED": 16,  # 最少需要的K线数量（调整为与收集器初始化数量一致）
        }
        
        self.running = False
        
        # 配置HTTP会话和重试策略
        self.session = requests.Session()
        
        # 配置重试策略
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        
        # 配置HTTP适配器
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=5,
            pool_maxsize=10,
            pool_block=False
        )
        
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # 设置默认头部
        self.session.headers.update({
            'User-Agent': 'python-requests/2.31.0',
            'Connection': 'keep-alive',
            'Accept': 'application/json'
        })
    
    def get_24h_volumes(self) -> Dict[str, float]:
        """获取24小时成交额数据（用于排序）"""
        try:
            url = "https://fapi.binance.com/fapi/v1/ticker/24hr"
            r = self.session.get(url, timeout=15)
            r.raise_for_status()
            
            volumes = {}
            for ticker in r.json():
                volumes[ticker["symbol"]] = float(ticker.get("quoteVolume", 0) or 0)
            return volumes
        except Exception:
            logger.exception("获取24h成交额失败")
            return {}
    
    def analyze_symbol_anomaly(self, symbol: str, klines: List[Dict], quote_volume_24h: float = 0) -> Optional[Dict]:
        """分析单个合约的异动情况"""
        if len(klines) < self.config["MIN_KLINES_REQUIRED"]:
            return None
        
        try:
            # 提取数据
            closes = np.array([k["close_price"] for k in klines])
            volumes = np.array([k["quote_volume"] for k in klines])
            highs = np.array([k["high_price"] for k in klines])
            lows = np.array([k["low_price"] for k in klines])
            
            # 1. 价格收益率分析
            returns = np.diff(closes) / closes[:-1]
            if len(returns) < 5:
                return None
            
            hist_returns = returns[:-1]
            cur_ret = returns[-1]
            cur_abs_ret = abs(cur_ret)
            
            # 检查最小收益率要求
            if cur_abs_ret < self.config["MIN_ABS_RETURN"]:
                return None
            
            # 价格异动指标
            price_mean = float(np.mean(np.abs(hist_returns)))
            price_std = float(np.std(np.abs(hist_returns), ddof=0))
            price_zscore = float((cur_abs_ret - price_mean) / price_std) if price_std > 0 else 0
            price_percentile = float((np.abs(hist_returns) < cur_abs_ret).sum()) / len(hist_returns) * 100
            
            # 2. 成交量异动分析
            hist_volumes = volumes[:-1]
            cur_volume = volumes[-1]
            
            volume_mean = float(np.mean(hist_volumes))
            volume_std = float(np.std(hist_volumes, ddof=0))
            volume_zscore = float((cur_volume - volume_mean) / volume_std) if volume_std > 0 else 0
            
            # 3. 波动率异动分析
            true_ranges = (highs - lows) / closes * 100
            hist_volatility = true_ranges[:-1]
            cur_volatility = true_ranges[-1]
            
            vol_mean = float(np.mean(hist_volatility))
            vol_std = float(np.std(hist_volatility, ddof=0))
            volatility_zscore = float((cur_volatility - vol_mean) / vol_std) if vol_std > 0 else 0
            
            # 4. 综合异动评分
            price_score = max(price_zscore - self.config["PRICE_Z_THRESHOLD"], 0) + \
                         max(price_percentile - self.config["PRICE_PERCENTILE"], 0) / 10
            volume_score = max(abs(volume_zscore) - self.config["VOLUME_Z_THRESHOLD"], 0)
            volatility_score = max(volatility_zscore - self.config["VOLATILITY_Z_THRESHOLD"], 0)
            
            anomaly_score = (self.config["WEIGHT_PRICE"] * price_score + 
                           self.config["WEIGHT_VOLUME"] * volume_score + 
                           self.config["WEIGHT_VOLATILITY"] * volatility_score)
            
            # 5. 判断异动类型
            reasons = []
            is_anomaly = False
            
            if (price_zscore >= self.config["PRICE_Z_THRESHOLD"] or 
                price_percentile >= self.config["PRICE_PERCENTILE"]):
                reasons.append("价格")
                is_anomaly = True
            
            if abs(volume_zscore) >= self.config["VOLUME_Z_THRESHOLD"]:
                reasons.append("成交量")
                is_anomaly = True
            
            if volatility_zscore >= self.config["VOLATILITY_Z_THRESHOLD"]:
                reasons.append("波动率")
                is_anomaly = True
            
            if anomaly_score >= self.config["ANOMALY_SCORE_THRESHOLD"]:
                if not reasons:
                    reasons.append("综合")
                is_anomaly = True
            
            # 即使不是异动也记录（方便API查询全部数据）
            if not reasons:
                reasons = ["正常"]
            
            # 获取最新K线的时间戳
            latest_kline = klines[-1]
            
            return {
                "symbol": symbol,
                "timestamp": latest_kline["open_time"] // 1000,  # 转换为秒
                "interval_type": "15m",
                "cur_return": cur_ret,
                "cur_abs_return": cur_abs_ret,
                "close_price": closes[-1],
                "cur_volume": cur_volume,
                "cur_volatility": cur_volatility,
                "price_zscore": price_zscore,
                "price_percentile": price_percentile,
                "volume_zscore": volume_zscore,
                "volatility_zscore": volatility_zscore,
                "anomaly_score": anomaly_score,
                "price_score": price_score,
                "volume_score": volume_score,
                "volatility_score": volatility_score,
                "anomaly_reasons": "+".join(reasons),
                "quote_volume_24h": quote_volume_24h,
                "is_anomaly": is_anomaly
            }
            
        except Exception:
            logger.exception(f"分析 {symbol} 异动时出错")
            return None
    
    def detect_anomalies(self):
        """检测所有合约的异动"""
        logger.info(f"[{datetime.now().strftime('%H:%M:%S')}] 开始异动检测...")

        try:
            # 获取24h成交额数据
            volumes_24h = self.get_24h_volumes()
            
            # 获取数据库中所有有数据的合约
            conn = db.get_connection()
            cursor = conn.execute("SELECT DISTINCT symbol FROM klines")
            symbols = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            anomaly_count = 0
            total_processed = 0
            
            for symbol in symbols:
                try:
                    # 获取最近的K线数据
                    klines = db.get_recent_klines(symbol, limit=150)
                    
                    if len(klines) < self.config["MIN_KLINES_REQUIRED"]:
                        continue
                    
                    # 分析异动
                    volume_24h = volumes_24h.get(symbol, 0)
                    result = self.analyze_symbol_anomaly(symbol, klines, volume_24h)
                    
                    if result:
                        # 存储结果到数据库
                        db.insert_anomaly(result)
                        total_processed += 1
                        
                        if result["is_anomaly"]:
                            anomaly_count += 1
                            logger.info(f"  异动: {symbol} ({result['anomaly_reasons']}) 评分={result['anomaly_score']:.2f}")
                
                except Exception:
                    logger.exception(f"处理 {symbol} 时出错")
            
            logger.info(f"[{datetime.now().strftime('%H:%M:%S')}] 异动检测完成: {total_processed}个合约, {anomaly_count}个异动")
            
        except Exception:
            logger.exception("异动检测出错")
    
    def start(self):
        """启动异动检测任务"""
        if self.running:
            return
        self.running = True
        logger.info("异动检测器已启动")

        # 立即执行一次
        self.detect_anomalies()

        # 安排定时任务 - 每分钟执行一次
        schedule.every().minute.do(self.detect_anomalies)

        # 运行调度器
        while self.running:
            schedule.run_pending()
            time.sleep(1)
    
    def stop(self):
        """停止异动检测任务"""
        self.running = False
        schedule.clear()
        # 关闭session连接
        if hasattr(self, 'session'):
            self.session.close()
        logger.info("异动检测器已停止")

def start_detector_background():
    """在后台线程启动异动检测器"""
    detector = AnomalyDetector()
    
    def run_detector():
        try:
            detector.start()
        except Exception as e:
            logger.exception("异动检测器异常")
    
    thread = threading.Thread(target=run_detector, daemon=True)
    thread.start()
    return detector

if __name__ == "__main__":
    logger = logging.getLogger(__name__)
    logger.info("=== 异动检测器 ===")

    detector = AnomalyDetector()

    try:
        detector.start()
    except KeyboardInterrupt:
        logger.info("\n收到中断信号，正在停止...")
        detector.stop()