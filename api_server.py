#!/usr/bin/env python3
"""
api_server.py - API服务器

提供REST API接口，从数据库快速返回异动数据
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import time
from datetime import datetime
from typing import Dict, List

from database import db

app = Flask(__name__)
CORS(app)  # 允许跨域请求
try:
    # 设置日志（幂等）
    from log_config import setup_logging
    setup_logging()
except Exception:
    pass
import logging
logger = logging.getLogger(__name__)


def format_update_time(val) -> str:
    """把数据库或时间戳的 last_update 解析为中文格式字符串 'YYYY-MM-DD HH:MM:SS'.

    支持输入形式：
    - 整数或浮点（秒或毫秒）
    - 数字字符串（秒或毫秒）
    - ISO 格式字符串（如 '2025-11-08T08:51:37' 或 '2025-11-08 08:51:37')
    否则返回原始字符串表示。
    """
    try:
        # 直接处理数值（秒或毫秒）
        if isinstance(val, (int, float)):
            ts = int(val)
            if ts > 1_000_000_000_000:  # 毫秒
                ts = ts // 1000
            return datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')

        # 字符串处理
        if isinstance(val, str):
            s = val.strip()
            if s.isdigit():
                ts = int(s)
                if ts > 1_000_000_000_000:
                    ts = ts // 1000
                return datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
            # 尝试解析 ISO 格式
            try:
                dt = datetime.fromisoformat(s)
                return dt.strftime('%Y-%m-%d %H:%M:%S')
            except Exception:
                # 回退：尝试常见带空格的时间格式
                try:
                    dt = datetime.strptime(s, '%Y-%m-%d %H:%M:%S')
                    return dt.strftime('%Y-%m-%d %H:%M:%S')
                except Exception:
                    return s

    except Exception:
        pass
    # 最后回退为原始表示
    return str(val)


def get_update_time() -> str:
    """返回中文格式的当前时间，供接口顶层 `update` 字段使用。"""
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def get_aster_symbols() -> set:
    """获取aster交易所支持的交易对集合"""
    try:
        aster_symbols = db.get_aster_symbols()
        return {symbol['symbol'] for symbol in aster_symbols}
    except Exception as e:
        logger.error(f"获取aster交易对失败: {e}")
        return set()

def filter_symbols_by_exchange(symbols: List[str], exchange: str) -> List[str]:
    """根据交易所过滤交易对"""
    if exchange.lower() == 'aster':
        aster_symbols = get_aster_symbols()
        return [symbol for symbol in symbols if symbol in aster_symbols]
    else:
        # 其他交易所或binance，不过滤
        return symbols

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    try:
        stats = db.get_symbol_stats()
        
        # 获取数据库详细信息
        size_info = db.get_data_size_info()
        
        return jsonify({
            "status": "healthy",
            "update": get_update_time(),
            "timestamp": int(time.time()),
            "server_time": datetime.now().isoformat(),
            "database": {
                "file_size_mb": stats["file_size_mb"],
                "max_age_hours": stats["max_age_hours"],
                "symbol_count": stats["symbol_count"],
                "kline_count": stats["kline_count"],
                "anomaly_count_24h": stats["anomaly_count_24h"],
                "auto_cleanup": db.auto_cleanup,
                "cleanup_interval_hours": db.cleanup_interval // 3600,
                "records": size_info["records"],
                "oldest_data": size_info["oldest_data"]
            }
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "update": get_update_time(),
            "message": str(e),
            "timestamp": int(time.time())
        }), 500

@app.route('/api/anomalies', methods=['GET'])
def get_anomalies():
    """获取异动数据接口"""
    try:
        # 解析查询参数
        interval_type = request.args.get('interval', '15m')
        hours = int(request.args.get('hours', 24))
        limit = int(request.args.get('limit', 100))
        min_score = float(request.args.get('min_score', 0.0))
        anomaly_only = request.args.get('anomaly_only', 'false').lower() == 'true'
        exchange = request.args.get('exchange', 'binance').lower()
        
        # 从数据库获取数据
        anomalies = db.get_recent_anomalies(interval_type, hours, limit * 2)  # 获取更多以便过滤
        
        # 如果是aster交易所，获取支持的交易对
        aster_symbols = set()
        if exchange == 'aster':
            aster_symbols = get_aster_symbols()
        
        # 应用过滤器
        filtered_anomalies = []
        for anomaly in anomalies:
            # 交易所过滤
            if exchange == 'aster' and anomaly['symbol'] not in aster_symbols:
                continue
            
            # 分数过滤
            if anomaly['anomaly_score'] < min_score:
                continue
            
            # 仅异动过滤
            if anomaly_only and anomaly['anomaly_reasons'] == '正常':
                continue
                
            filtered_anomalies.append({
                "symbol": anomaly['symbol'],
                "timestamp": anomaly['timestamp'],
                "datetime": datetime.fromtimestamp(anomaly['timestamp']).isoformat(),
                "interval_type": anomaly['interval_type'],
                
                # 价格数据
                "current_return_pct": round(anomaly['cur_return'] * 100, 3),
                "close_price": anomaly['close_price'],
                
                # 成交量数据
                "current_volume": anomaly['cur_volume'],
                "current_volatility": anomaly['cur_volatility'],
                
                # 异动指标
                "price_zscore": round(anomaly['price_zscore'], 2),
                "price_percentile": round(anomaly['price_percentile'], 1),
                "volume_zscore": round(anomaly['volume_zscore'], 2),
                "volatility_zscore": round(anomaly['volatility_zscore'], 2),
                
                # 评分
                "anomaly_score": round(anomaly['anomaly_score'], 3),
                "price_score": round(anomaly['price_score'], 3),
                "volume_score": round(anomaly['volume_score'], 3),
                "volatility_score": round(anomaly['volatility_score'], 3),
                
                # 异动类型和成交额
                "anomaly_reasons": anomaly['anomaly_reasons'],
                "quote_volume_24h": anomaly['quote_volume_24h'],
                
                "created_at": anomaly['created_at']
            })
        
        # 限制结果数量
        filtered_anomalies = filtered_anomalies[:limit]
        
        return jsonify({
            "status": "success",
            "update": get_update_time(),
            "count": len(filtered_anomalies),
            "data": filtered_anomalies,
            "filters": {
                "interval_type": interval_type,
                "hours": hours,
                "min_score": min_score,
                "anomaly_only": anomaly_only,
                "exchange": exchange
            },
            "timestamp": int(time.time())
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "update": get_update_time(),
            "message": str(e),
            "timestamp": int(time.time())
        }), 500

@app.route('/api/anomalies/top', methods=['GET'])
def get_top_anomalies():
    """获取评分最高的异动数据"""
    try:
        limit = int(request.args.get('limit', 20))
        hours = int(request.args.get('hours', 24))
        exchange = request.args.get('exchange', 'binance').lower()
        
        # 获取数据并按评分排序
        anomalies = db.get_recent_anomalies("15m", hours, limit * 3)
        
        # 如果是aster交易所，获取支持的交易对
        aster_symbols = set()
        if exchange == 'aster':
            aster_symbols = get_aster_symbols()
        
        # 过滤掉正常数据，只返回异动，并应用交易所过滤
        top_anomalies = []
        for a in anomalies:
            if a['anomaly_reasons'] == '正常' or a['anomaly_score'] <= 0.5:
                continue
            if exchange == 'aster' and a['symbol'] not in aster_symbols:
                continue
            top_anomalies.append(a)
        
        top_anomalies = top_anomalies[:limit]
        
        result = []
        for anomaly in top_anomalies:
            result.append({
                "rank": len(result) + 1,
                "symbol": anomaly['symbol'],
                "current_return_pct": round(anomaly['cur_return'] * 100, 2),
                "anomaly_score": round(anomaly['anomaly_score'], 2),
                "price_zscore": round(anomaly['price_zscore'], 2),
                "volume_zscore": round(anomaly['volume_zscore'], 2),
                "volatility_zscore": round(anomaly['volatility_zscore'], 2),
                "quote_volume_24h": int(anomaly['quote_volume_24h']),
                "anomaly_reasons": anomaly['anomaly_reasons'],
                "datetime": datetime.fromtimestamp(anomaly['timestamp']).strftime('%H:%M:%S')
            })
        
        return jsonify({
            "status": "success",
            "update": get_update_time(),
            "count": len(result),
            "data": result,
            "exchange": exchange,
            "timestamp": int(time.time())
        })
        
    except Exception as e:
        return jsonify({
            "status": "error", 
            "update": get_update_time(),
            "message": str(e)
        }), 500

@app.route('/api/symbols/<symbol>/klines', methods=['GET'])
def get_symbol_klines(symbol):
    """获取指定合约的K线数据"""
    try:
        limit = int(request.args.get('limit', 100))
        
        klines = db.get_recent_klines(symbol, limit)
        
        result = []
        for kline in klines:
            result.append({
                "timestamp": kline['open_time'],
                "datetime": datetime.fromtimestamp(kline['open_time'] // 1000).isoformat(),
                "open": kline['open_price'],
                "high": kline['high_price'],
                "low": kline['low_price'],
                "close": kline['close_price'],
                "volume": kline['volume'],
                "quote_volume": kline['quote_volume']
            })
        
        return jsonify({
            "status": "success",
            "update": get_update_time(),
            "symbol": symbol,
            "count": len(result),
            "data": result
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "update": get_update_time(),
            "message": str(e)
        }), 500

@app.route('/api/coins', methods=['GET'])
def get_coins():
    """获取高评分币种接口 - 用于AI选币决策（基于独立数据表）"""
    try:
        limit = int(request.args.get('limit',10))
        exchange = request.args.get('exchange', 'binance').lower()
        
        # 从独立的ai_coins表获取数据
        coins_data = db.get_ai_coins(limit * 2)  # 获取更多数据以便过滤
        
        # 如果是aster交易所，获取支持的交易对
        aster_symbols = set()
        if exchange == 'aster':
            aster_symbols = get_aster_symbols()
        
        # 转换格式并过滤交易所
        coins = []
        for coin in coins_data:
            # 交易所过滤
            if exchange == 'aster' and coin['symbol'] not in aster_symbols:
                continue
                
            coin_result = {
                "pair": coin['symbol'],
                "score": round(coin['score'], 1),
                "start_time": coin['start_time'],
                "start_price": round(coin['start_price'], 4),
                "last_score": round(coin['score'], 1),  # 当前就是最新评分
                "max_score": round(coin['score'], 1),   # 简化为当前评分
                "max_price": round(coin['max_price'], 4),
                "increase_percent": round(coin['increase_percent'], 2)
            }
            coins.append(coin_result)
            
            # 限制数量
            if len(coins) >= limit:
                break
        
        return jsonify({
            "success": True,
            "update": get_update_time(),
            "data": {
                "coins": coins,
                "count": len(coins),
                "exchange": exchange,
                "last_update": format_update_time(coins_data[0]['updated_at'] if coins_data else int(time.time())),
                "update_interval": "3分钟"
            }
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "update": get_update_time(),
            "error": str(e)
        }), 500

@app.route('/api/oitop', methods=['GET'])
def get_oi_top():
    """获取持仓量Top20接口 - 基于独立数据表快速响应"""
    try:
        limit = int(request.args.get('limit', 20))
        exchange = request.args.get('exchange', 'binance').lower()
        
        # 从独立的oi_rankings表获取数据
        oi_data = db.get_oi_rankings(limit * 2)  # 获取更多数据以便过滤
        
        # 如果是aster交易所，获取支持的交易对
        aster_symbols = set()
        if exchange == 'aster':
            aster_symbols = get_aster_symbols()
        
        # 转换格式并过滤交易所
        positions = []
        for oi in oi_data:
            # 交易所过滤
            if exchange == 'aster' and oi['symbol'] not in aster_symbols:
                continue
                
            position = {
                "symbol": oi['symbol'],
                "rank": len(positions) + 1,  # 重新排序
                "current_oi": round(oi['current_oi'], 2),
                "oi_delta": round(oi['oi_delta'], 2),
                "oi_delta_percent": round(oi['oi_delta_percent'], 2),
                "oi_delta_value": round(oi['oi_delta_value'], 2),
                "price_delta_percent": round(oi['price_delta_percent'], 2),
                "net_long": round(oi['net_long'], 2),
                "net_short": round(oi['net_short'], 2)
            }
            positions.append(position)
            
            # 限制数量
            if len(positions) >= limit:
                break
        
        return jsonify({
            "success": True,
            "update": get_update_time(),
            "data": {
                "positions": positions,
                "count": len(positions),
                "exchange": exchange,
                "time_range": "24h",
                "last_update": format_update_time(oi_data[0]['updated_at'] if oi_data else int(time.time())),
                "update_interval": "3分钟",
                "note": f"基于独立数据表，每3分钟更新，当前交易所：{exchange}"
            }
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "update": get_update_time(),
            "error": str(e)
        }), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """获取统计信息"""
    try:
        stats = db.get_symbol_stats()
        
        # 获取最近1小时的异动数量
        recent_anomalies = db.get_recent_anomalies("15m", 1, 1000)
        anomaly_count_1h = len([a for a in recent_anomalies if a['anomaly_reasons'] != '正常'])
        
        return jsonify({
            "status": "success",
            "update": get_update_time(),
            "data": {
                "monitored_symbols": stats["symbol_count"],
                "total_klines": stats["kline_count"],
                "anomalies_24h": stats["anomaly_count_24h"],
                "anomalies_1h": anomaly_count_1h,
                "last_update": format_update_time(int(time.time()))
            }
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "update": get_update_time(),
            "message": str(e)
        }), 500

@app.route('/', methods=['GET'])
def index():
    """首页 - API文档"""
    return """
    <h1>币安合约异动检测 API</h1>
    <h2>可用接口：</h2>
    <ul>
        <li><code>GET /api/health</code> - 健康检查</li>
        <li><code>GET /api/anomalies</code> - 获取异动数据
            <ul>
                <li>参数: interval=15m, hours=24, limit=100, min_score=0.0, anomaly_only=false, exchange=binance</li>
                <li>exchange: binance(默认) | aster（当选择aster时，只返回aster交易所支持的交易对）</li>
            </ul>
        </li>
        <li><code>GET /api/anomalies/top</code> - 获取评分最高的异动
            <ul>
                <li>参数: limit=20, hours=24, exchange=binance</li>
                <li>exchange: binance(默认) | aster</li>
            </ul>
        </li>
        <li><code>GET /api/coins</code> - 获取高评分币种（AI选币决策）
            <ul>
                <li>参数: limit=10, exchange=binance</li>
                <li>exchange: binance(默认) | aster</li>
                <li>返回评分、价格、涨幅等数据</li>
            </ul>
        </li>
        <li><code>GET /api/oitop</code> - 获取持仓量Top20（市场热度分析）
            <ul>
                <li>参数: limit=20, exchange=binance</li>
                <li>exchange: binance(默认) | aster</li>
                <li>返回持仓量、增长率、多空比等数据</li>
            </ul>
        </li>
        <li><code>GET /api/symbols/{symbol}/klines</code> - 获取指定合约K线数据
            <ul>
                <li>参数: limit=100</li>
            </ul>
        </li>
        <li><code>GET /api/stats</code> - 获取统计信息</li>
    </ul>
    
    <h2>示例：</h2>
    <ul>
        <li><a href="/api/health">/api/health</a></li>
        <li><a href="/api/coins">/api/coins</a> - AI选币接口（币安）</li>
        <li><a href="/api/coins?exchange=aster">/api/coins?exchange=aster</a> - AI选币接口（Aster）</li>
        <li><a href="/api/oitop?limit=10">/api/oitop?limit=10</a> - 持仓量Top10（币安）</li>
        <li><a href="/api/oitop?limit=10&exchange=aster">/api/oitop?limit=10&exchange=aster</a> - 持仓量Top10（Aster）</li>
        <li><a href="/api/anomalies/top?limit=10">/api/anomalies/top?limit=10</a> - 异动Top10（币安）</li>
        <li><a href="/api/anomalies/top?limit=10&exchange=aster">/api/anomalies/top?limit=10&exchange=aster</a> - 异动Top10（Aster）</li>
        <li><a href="/api/anomalies?anomaly_only=true&min_score=1.0">/api/anomalies?anomaly_only=true&min_score=1.0</a></li>
        <li><a href="/api/anomalies?anomaly_only=true&min_score=1.0&exchange=aster">/api/anomalies?anomaly_only=true&min_score=1.0&exchange=aster</a> - 异动数据（Aster）</li>
    </ul>
    
    <h2>交易所支持：</h2>
    <ul>
        <li><strong>binance</strong>: 币安交易所（默认），返回所有数据</li>
        <li><strong>aster</strong>: Aster交易所，只返回aster数据库中存在的交易对</li>
    </ul>
    """

if __name__ == '__main__':
    logger.info("=== 币安异动检测 API 服务器 ===")
    logger.info("启动API服务器...")
    logger.info("访问 http://localhost:5000 查看API文档")
    logger.info("访问 http://localhost:5000/api/health 进行健康检查")
    
    app.run(host='0.0.0.0', port=5000, debug=False)