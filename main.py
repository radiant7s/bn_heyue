#!/usr/bin/env python3
"""
main.py - 主启动脚本

集成启动WebSocket数据收集器、异动检测器和API服务器
"""

import time
import signal
import sys
import threading
from datetime import datetime

from ws_collector import start_collector_background
from anomaly_detector import start_detector_background
from data_updater import start_updater_background, download_and_store_aster
from api_server import app
from log_config import setup_logging
import logging

# 初始化日志
setup_logging()
logger = logging.getLogger(__name__)

class SystemManager:
    def __init__(self):
        self.running = True
        self.collector = None
        self.detector = None
        self.updater = None
        self.api_thread = None
        
        # 注册信号处理器
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        """处理停止信号"""
        logger.info(f"\n收到停止信号 {signum}，正在优雅关闭...")
        self.stop()
        sys.exit(0)
    
    def start_api_server(self):
        """启动API服务器"""
        def run_api():
            try:
                app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
            except Exception as e:
                logger.exception(f"API服务器启动失败: {e}")
        
        self.api_thread = threading.Thread(target=run_api, daemon=True)
        self.api_thread.start()
    
    def start(self):
        """启动所有服务"""
        logger.info("=== 币安合约异动检测系统 ===")
        logger.info(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 显示数据库配置信息
        from database import db
        logger.info(f"\n数据库配置:")
        logger.info(f"- 数据保留时间: {db.max_age_hours} 小时")
        logger.info(f"- 清理检查间隔: {db.cleanup_interval//60} 分钟")
        stats = db.get_symbol_stats()
        logger.info(f"- 当前数据库大小: {stats['file_size_mb']} MB")
        logger.info(f"- 监控合约数量: {stats['symbol_count']}")
        logger.info(f"- K线数据条数: {stats['kline_count']}")
        logger.info(f"- 自动清理: {'启用' if db.auto_cleanup else '禁用'}")
        logger.info(f"- 大小限制: {db.max_db_size_mb} MB")
        logger.info("")
        
        try:
            # 启动时先下载并更新 Aster exchangeInfo
            try:
                ok = download_and_store_aster()
                if ok:
                    logger.info("Aster exchangeInfo 下载并写入数据库完成")
                else:
                    logger.warning("Aster exchangeInfo 下载或写入数据库失败（见日志）")
            except Exception:
                logger.exception("启动时执行 Aster exchangeInfo 更新出错")

            # 1. 启动WebSocket数据收集器
            logger.info("1. 启动WebSocket数据收集器...")
            self.collector = start_collector_background()
            time.sleep(3)  # 等待连接建立
            
            # 2. 启动异动检测器
            logger.info("2. 启动异动检测器...")
            self.detector = start_detector_background() 
            time.sleep(2)
            
            # 3. 启动数据更新器（新增）
            logger.info("3. 启动数据更新器...")
            self.updater = start_updater_background()
            time.sleep(2)
            
            # 4. 启动API服务器
            logger.info("4. 启动API服务器...")
            self.start_api_server()
            time.sleep(1)
            
            logger.info("")
            logger.info("=== 系统启动完成 ===")
            logger.info("WebSocket数据收集器: 运行中")
            logger.info("异动检测器: 运行中")
            logger.info("数据更新器: 运行中 (每3分钟更新)")
            logger.info("API服务器: http://localhost:5000")
            logger.info("")
            logger.info("🔗 主要API接口:")
            logger.info("- AI选币决策: http://localhost:5000/api/coins")
            logger.info("- 持仓量排行: http://localhost:5000/api/oitop")
            logger.info("- 异动数据: http://localhost:5000/api/anomalies/top")
            logger.info("- 健康检查: http://localhost:5000/api/health")
            logger.info("")
            logger.info("💡 数据更新频率:")
            logger.info("- K线数据: 实时（WebSocket）")
            logger.info("- 异动检测: 每1分钟")
            logger.info("- AI选币排行: 每3分钟")
            logger.info("- 持仓量排行: 每3分钟")
            logger.info("")
            logger.info("按 Ctrl+C 停止系统")
            
            # 主循环 - 保持程序运行并显示状态
            last_status_time = 0
            while self.running:
                current_time = time.time()
                
                # 每30秒显示一次状态
                if current_time - last_status_time >= 30:
                    from database import db
                    stats = db.get_symbol_stats()
                    logger.info(f"[{datetime.now().strftime('%H:%M:%S')}] "
                                f"监控合约: {stats['symbol_count']}, "
                                f"K线数据: {stats['kline_count']}, "
                                f"24h异动: {stats['anomaly_count_24h']}")
                    last_status_time = current_time
                
                time.sleep(1)
                
        except Exception:
            logger.exception("启动系统时出错")
            self.stop()
    
    def stop(self):
        """停止所有服务"""
        self.running = False
        logger.info("正在停止系统...")

        if self.collector:
            try:
                self.collector.stop()
            except:
                pass
        
        if self.detector:
            try:
                self.detector.stop()
            except:
                pass

        logger.info("系统已停止")

if __name__ == "__main__":
    manager = SystemManager()
    manager.start()