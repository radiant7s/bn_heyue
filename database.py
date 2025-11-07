#!/usr/bin/env python3
"""
database.py - 数据库模块

管理SQLite数据库，包含：
1. 原始K线数据表 (klines)
2. 异动汇总表 (anomalies)
"""

import sqlite3
import time
from typing import List, Dict, Optional
import threading
import logging

# 导入配置
try:
    from config import DATABASE_CONFIG, LOGGING_CONFIG
except ImportError:
    # 默认配置
    DATABASE_CONFIG = {
        "db_path": "data.db",
        "max_age_hours": 24,
        "cleanup_interval": 3600,
        "auto_cleanup": True,
        "max_db_size_mb": 100,
        "max_klines_per_symbol": 10000,
    }
    LOGGING_CONFIG = {
        "level": "INFO",
        "cleanup_log": True,
    }

class Database:
    def __init__(self, db_path: str = None, max_age_hours: int = None):
        self.db_path = db_path or DATABASE_CONFIG["db_path"]
        self.max_age_hours = max_age_hours or DATABASE_CONFIG["max_age_hours"]
        self.max_age_seconds = self.max_age_hours * 3600
        self.cleanup_interval = DATABASE_CONFIG["cleanup_interval"]
        self.auto_cleanup = DATABASE_CONFIG["auto_cleanup"]
        self.max_db_size_mb = DATABASE_CONFIG["max_db_size_mb"]
        self.max_klines_per_symbol = DATABASE_CONFIG["max_klines_per_symbol"]
        
        self.lock = threading.Lock()
        self.last_cleanup_time = 0  # 上次清理时间
        
        self.init_tables()
        if self.auto_cleanup:
            self.cleanup_old_data()  # 初始化时清理一次旧数据
    
    def get_connection(self):
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row  # 使结果可以通过列名访问
        return conn
    
    def init_tables(self):
        """初始化数据库表"""
        with self.lock:
            conn = self.get_connection()
            try:
                # 原始K线数据表
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS klines (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT NOT NULL,
                        open_time INTEGER NOT NULL,
                        close_time INTEGER NOT NULL,
                        open_price REAL NOT NULL,
                        high_price REAL NOT NULL,
                        low_price REAL NOT NULL,
                        close_price REAL NOT NULL,
                        volume REAL NOT NULL,
                        quote_volume REAL NOT NULL,
                        trades_count INTEGER NOT NULL,
                        created_at INTEGER NOT NULL,
                        UNIQUE(symbol, open_time)
                    )
                """)
                
                # 异动汇总表
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS anomalies (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT NOT NULL,
                        timestamp INTEGER NOT NULL,
                        interval_type TEXT NOT NULL,  -- '15m', '5m', '1m'
                        
                        -- 价格数据
                        cur_return REAL NOT NULL,
                        cur_abs_return REAL NOT NULL,
                        close_price REAL NOT NULL,
                        
                        -- 成交量数据
                        cur_volume REAL NOT NULL,
                        cur_volatility REAL NOT NULL,
                        
                        -- 异动指标
                        price_zscore REAL NOT NULL,
                        price_percentile REAL NOT NULL,
                        volume_zscore REAL NOT NULL,
                        volatility_zscore REAL NOT NULL,
                        
                        -- 评分
                        anomaly_score REAL NOT NULL,
                        price_score REAL NOT NULL,
                        volume_score REAL NOT NULL,
                        volatility_score REAL NOT NULL,
                        
                        -- 异动类型
                        anomaly_reasons TEXT NOT NULL,
                        
                        -- 24h成交额（用于排序）
                        quote_volume_24h REAL NOT NULL,
                        
                        created_at INTEGER NOT NULL,
                        UNIQUE(symbol, timestamp, interval_type)
                    )
                """)
                
                # AI选币数据表（独立更新）
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS ai_coins (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT NOT NULL,
                        score REAL NOT NULL,
                        start_time INTEGER NOT NULL,
                        start_price REAL NOT NULL,
                        current_price REAL NOT NULL,
                        max_price REAL NOT NULL,
                        increase_percent REAL NOT NULL,
                        volume_24h REAL NOT NULL,
                        price_change_24h REAL NOT NULL,
                        updated_at INTEGER NOT NULL,
                        UNIQUE(symbol)
                    )
                """)
                
                # 持仓量排行数据表（独立更新）
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS oi_rankings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT NOT NULL,
                        rank INTEGER NOT NULL,
                        current_oi REAL NOT NULL,
                        oi_delta REAL NOT NULL,
                        oi_delta_percent REAL NOT NULL,
                        oi_delta_value REAL NOT NULL,
                        price_delta_percent REAL NOT NULL,
                        net_long REAL NOT NULL,
                        net_short REAL NOT NULL,
                        volume_24h REAL NOT NULL,
                        updated_at INTEGER NOT NULL,
                        UNIQUE(symbol)
                    )
                """)
                
                # 创建索引
                conn.execute("CREATE INDEX IF NOT EXISTS idx_klines_symbol_time ON klines(symbol, open_time)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_anomalies_timestamp ON anomalies(timestamp DESC)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_anomalies_score ON anomalies(anomaly_score DESC)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_coins_score ON ai_coins(score DESC)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_oi_rankings_rank ON oi_rankings(rank ASC)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_coins_updated ON ai_coins(updated_at DESC)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_oi_rankings_updated ON oi_rankings(updated_at DESC)")
                
                conn.commit()
            finally:
                conn.close()
    
    def cleanup_old_data(self):
        """清理超过时效的旧数据"""
        cutoff_time = int(time.time()) - self.max_age_seconds
        
        with self.lock:
            conn = self.get_connection()
            try:
                deleted_counts = {}
                
                # 清理旧的K线数据
                cursor = conn.execute("DELETE FROM klines WHERE created_at < ?", (cutoff_time,))
                deleted_counts['klines'] = cursor.rowcount
                
                # 如果有单个合约K线数量限制，额外清理超量数据
                if self.max_klines_per_symbol > 0:
                    cursor = conn.execute("""
                        DELETE FROM klines 
                        WHERE id IN (
                            SELECT id FROM (
                                SELECT id, ROW_NUMBER() OVER (
                                    PARTITION BY symbol 
                                    ORDER BY open_time DESC
                                ) as rn
                                FROM klines
                            )
                            WHERE rn > ?
                        )
                    """, (self.max_klines_per_symbol,))
                    deleted_counts['klines_excess'] = cursor.rowcount
                
                # 清理旧的异动数据
                cursor = conn.execute("DELETE FROM anomalies WHERE created_at < ?", (cutoff_time,))
                deleted_counts['anomalies'] = cursor.rowcount
                
                # 清理旧的AI选币数据
                cursor = conn.execute("DELETE FROM ai_coins WHERE updated_at < ?", (cutoff_time,))
                deleted_counts['ai_coins'] = cursor.rowcount
                
                # 清理旧的持仓量排行数据
                cursor = conn.execute("DELETE FROM oi_rankings WHERE updated_at < ?", (cutoff_time,))
                deleted_counts['oi_rankings'] = cursor.rowcount
                
                conn.commit()
                
                # 记录清理情况
                total_deleted = sum(deleted_counts.values())
                if total_deleted > 0 and LOGGING_CONFIG.get("cleanup_log", True):
                    cleanup_msg = f"数据清理完成: "
                    cleanup_msg += f"K线={deleted_counts.get('klines', 0)}"
                    if 'klines_excess' in deleted_counts:
                        cleanup_msg += f"(+{deleted_counts['klines_excess']}超量)"
                    cleanup_msg += f", 异动={deleted_counts.get('anomalies', 0)}"
                    cleanup_msg += f", AI选币={deleted_counts.get('ai_coins', 0)}"
                    cleanup_msg += f", 持仓量排行={deleted_counts.get('oi_rankings', 0)}"
                    logging.info(cleanup_msg)
                
                # 执行VACUUM来释放磁盘空间
                if total_deleted > 100:  # 只有删除较多数据时才VACUUM
                    conn.execute("VACUUM")
                    if LOGGING_CONFIG.get("cleanup_log", True):
                        logging.info("执行VACUUM优化数据库")
                
                return deleted_counts
                
            except Exception as e:
                logging.error(f"清理旧数据时出错: {e}")
                return {}
            finally:
                conn.close()
    
    def maybe_cleanup(self):
        """根据时间间隔决定是否需要清理数据"""
        if not self.auto_cleanup:
            return
            
        current_time = int(time.time())
        need_cleanup = False
        
        # 检查时间间隔
        if current_time - self.last_cleanup_time >= self.cleanup_interval:
            need_cleanup = True
        
        # 检查数据库大小限制
        if self.max_db_size_mb > 0:
            import os
            if os.path.exists(self.db_path):
                file_size_mb = os.path.getsize(self.db_path) / (1024 * 1024)
                if file_size_mb > self.max_db_size_mb:
                    need_cleanup = True
                    if LOGGING_CONFIG.get("cleanup_log", True):
                        logging.warning(f"数据库大小超限 {file_size_mb:.1f}MB > {self.max_db_size_mb}MB，触发清理")
        
        # 检查单个合约K线数量限制
        if self.max_klines_per_symbol > 0:
            conn = self.get_connection()
            try:
                cursor = conn.execute("""
                    SELECT symbol, COUNT(*) as count 
                    FROM klines 
                    GROUP BY symbol 
                    HAVING count > ?
                    LIMIT 1
                """, (self.max_klines_per_symbol,))
                row = cursor.fetchone()
                if row:
                    need_cleanup = True
                    if LOGGING_CONFIG.get("cleanup_log", True):
                        logging.warning(f"合约 {row['symbol']} K线数量超限 {row['count']} > {self.max_klines_per_symbol}，触发清理")
            finally:
                conn.close()
        
        if need_cleanup:
            self.cleanup_old_data()
            self.last_cleanup_time = current_time
    
    def get_data_size_info(self) -> Dict:
        """获取数据库大小和记录数信息"""
        import os
        
        conn = self.get_connection()
        try:
            # 获取文件大小
            file_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
            file_size_mb = file_size / (1024 * 1024)
            
            # 获取各表记录数
            cursor = conn.execute("SELECT COUNT(*) as count FROM klines")
            klines_count = cursor.fetchone()['count']
            
            cursor = conn.execute("SELECT COUNT(*) as count FROM anomalies")
            anomalies_count = cursor.fetchone()['count']
            
            cursor = conn.execute("SELECT COUNT(*) as count FROM ai_coins")
            ai_coins_count = cursor.fetchone()['count']
            
            cursor = conn.execute("SELECT COUNT(*) as count FROM oi_rankings")
            oi_rankings_count = cursor.fetchone()['count']
            
            # 获取最旧数据的时间
            cursor = conn.execute("SELECT MIN(created_at) as oldest FROM klines")
            oldest_kline = cursor.fetchone()['oldest']
            
            cursor = conn.execute("SELECT MIN(created_at) as oldest FROM anomalies")
            oldest_anomaly = cursor.fetchone()['oldest']
            
            return {
                "file_size_mb": round(file_size_mb, 2),
                "max_age_hours": self.max_age_hours,
                "records": {
                    "klines": klines_count,
                    "anomalies": anomalies_count,
                    "ai_coins": ai_coins_count,
                    "oi_rankings": oi_rankings_count
                },
                "oldest_data": {
                    "kline_time": oldest_kline,
                    "anomaly_time": oldest_anomaly
                }
            }
        finally:
            conn.close()
    
    def insert_kline(self, symbol: str, kline_data: Dict):
        """插入K线数据"""
        with self.lock:
            conn = self.get_connection()
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO klines 
                    (symbol, open_time, close_time, open_price, high_price, low_price, 
                     close_price, volume, quote_volume, trades_count, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    symbol,
                    kline_data['open_time'],
                    kline_data['close_time'],
                    kline_data['open_price'],
                    kline_data['high_price'],
                    kline_data['low_price'],
                    kline_data['close_price'],
                    kline_data['volume'],
                    kline_data['quote_volume'],
                    kline_data.get('trades_count', 0),
                    int(time.time())
                ))
                conn.commit()
            finally:
                conn.close()
        
        # 检查是否需要清理旧数据
        self.maybe_cleanup()
    
    def get_recent_klines(self, symbol: str, limit: int = 150) -> List[Dict]:
        """获取最近的K线数据"""
        conn = self.get_connection()
        try:
            cursor = conn.execute("""
                SELECT * FROM klines 
                WHERE symbol = ? 
                ORDER BY open_time DESC 
                LIMIT ?
            """, (symbol, limit))
            
            rows = cursor.fetchall()
            return [dict(row) for row in reversed(rows)]  # 按时间正序返回
        finally:
            conn.close()
    
    def insert_anomaly(self, anomaly_data: Dict):
        """插入异动数据"""
        with self.lock:
            conn = self.get_connection()
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO anomalies 
                    (symbol, timestamp, interval_type, cur_return, cur_abs_return, close_price,
                     cur_volume, cur_volatility, price_zscore, price_percentile, volume_zscore,
                     volatility_zscore, anomaly_score, price_score, volume_score, volatility_score,
                     anomaly_reasons, quote_volume_24h, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    anomaly_data['symbol'],
                    anomaly_data['timestamp'],
                    anomaly_data['interval_type'],
                    anomaly_data['cur_return'],
                    anomaly_data['cur_abs_return'],
                    anomaly_data['close_price'],
                    anomaly_data['cur_volume'],
                    anomaly_data['cur_volatility'],
                    anomaly_data['price_zscore'],
                    anomaly_data['price_percentile'],
                    anomaly_data['volume_zscore'],
                    anomaly_data['volatility_zscore'],
                    anomaly_data['anomaly_score'],
                    anomaly_data['price_score'],
                    anomaly_data['volume_score'],
                    anomaly_data['volatility_score'],
                    anomaly_data['anomaly_reasons'],
                    anomaly_data['quote_volume_24h'],
                    int(time.time())
                ))
                conn.commit()
            finally:
                conn.close()
        
        # 检查是否需要清理旧数据
        self.maybe_cleanup()
    
    def get_recent_anomalies(self, interval_type: str = "15m", hours: int = 24, limit: int = 100) -> List[Dict]:
        """获取最近的异动数据"""
        since_timestamp = int(time.time()) - (hours * 3600)
        
        conn = self.get_connection()
        try:
            cursor = conn.execute("""
                SELECT * FROM anomalies 
                WHERE interval_type = ? AND timestamp >= ?
                ORDER BY anomaly_score DESC, timestamp DESC
                LIMIT ?
            """, (interval_type, since_timestamp, limit))
            
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def get_symbol_kline_count(self, symbol: str) -> int:
        """获取指定合约的K线数量"""
        conn = self.get_connection()
        try:
            cursor = conn.execute("""
                SELECT COUNT(*) as count FROM klines 
                WHERE symbol = ?
            """, (symbol,))
            row = cursor.fetchone()
            return row['count'] if row else 0
        finally:
            conn.close()
    
    def get_symbols_kline_count(self) -> List[tuple]:
        """获取所有合约的K线数量"""
        conn = self.get_connection()
        try:
            cursor = conn.execute("""
                SELECT symbol, COUNT(*) as count 
                FROM klines 
                GROUP BY symbol 
                ORDER BY symbol
            """)
            rows = cursor.fetchall()
            return [(row['symbol'], row['count']) for row in rows]
        finally:
            conn.close()

    def get_symbol_stats(self) -> Dict:
        """获取数据库统计信息"""
        import os
        
        conn = self.get_connection()
        try:
            # 获取文件大小
            file_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
            file_size_mb = file_size / (1024 * 1024)
            
            cursor = conn.execute("SELECT COUNT(DISTINCT symbol) as symbol_count FROM klines")
            symbol_count = cursor.fetchone()['symbol_count']
            
            cursor = conn.execute("SELECT COUNT(*) as kline_count FROM klines")
            kline_count = cursor.fetchone()['kline_count']
            
            cursor = conn.execute("SELECT COUNT(*) as anomaly_count FROM anomalies WHERE timestamp >= ?", 
                                (int(time.time()) - 86400,))  # 最近24小时
            anomaly_count = cursor.fetchone()['anomaly_count']
            
            return {
                "symbol_count": symbol_count,
                "kline_count": kline_count,
                "anomaly_count_24h": anomaly_count,
                "file_size_mb": round(file_size_mb, 2),
                "max_age_hours": self.max_age_hours
            }
        finally:
            conn.close()
    
    # ===== AI选币数据表操作 =====
    
    def upsert_ai_coin(self, coin_data: Dict):
        """插入或更新AI选币数据"""
        with self.lock:
            conn = self.get_connection()
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO ai_coins
                    (symbol, score, start_time, start_price, current_price, max_price,
                     increase_percent, volume_24h, price_change_24h, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    coin_data['symbol'],
                    coin_data['score'],
                    coin_data['start_time'],
                    coin_data['start_price'],
                    coin_data['current_price'],
                    coin_data['max_price'],
                    coin_data['increase_percent'],
                    coin_data['volume_24h'],
                    coin_data['price_change_24h'],
                    int(time.time())
                ))
                conn.commit()
            finally:
                conn.close()
    
    def get_ai_coins(self, limit: int = 20) -> List[Dict]:
        """获取AI选币排行数据"""
        conn = self.get_connection()
        try:
            cursor = conn.execute("""
                SELECT * FROM ai_coins
                ORDER BY score DESC, volume_24h DESC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def clear_ai_coins(self):
        """清空AI选币数据"""
        with self.lock:
            conn = self.get_connection()
            try:
                conn.execute("DELETE FROM ai_coins")
                conn.commit()
            finally:
                conn.close()
    
    # ===== 持仓量排行数据表操作 =====
    
    def upsert_oi_ranking(self, oi_data: Dict):
        """插入或更新持仓量排行数据"""
        with self.lock:
            conn = self.get_connection()
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO oi_rankings
                    (symbol, rank, current_oi, oi_delta, oi_delta_percent, oi_delta_value,
                     price_delta_percent, net_long, net_short, volume_24h, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    oi_data['symbol'],
                    oi_data['rank'],
                    oi_data['current_oi'],
                    oi_data['oi_delta'],
                    oi_data['oi_delta_percent'],
                    oi_data['oi_delta_value'],
                    oi_data['price_delta_percent'],
                    oi_data['net_long'],
                    oi_data['net_short'],
                    oi_data['volume_24h'],
                    int(time.time())
                ))
                conn.commit()
            finally:
                conn.close()
    
    def get_oi_rankings(self, limit: int = 20) -> List[Dict]:
        """获取持仓量排行数据"""
        conn = self.get_connection()
        try:
            cursor = conn.execute("""
                SELECT * FROM oi_rankings
                ORDER BY rank ASC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def clear_oi_rankings(self):
        """清空持仓量排行数据"""
        with self.lock:
            conn = self.get_connection()
            try:
                conn.execute("DELETE FROM oi_rankings")
                conn.commit()
            finally:
                conn.close()

# 全局数据库实例 - 使用配置文件设置
db = Database()