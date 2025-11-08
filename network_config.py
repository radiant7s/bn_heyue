#!/usr/bin/env python3
"""
network_config.py - 网络配置和优化

为了解决 Windows 系统下的 WinError 10048 错误，
统一配置所有HTTP请求的连接池和重试策略
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import logging

logger = logging.getLogger(__name__)

class NetworkSession:
    """统一的网络会话管理器"""
    
    @staticmethod
    def create_session(
        max_retries: int = 3,
        backoff_factor: float = 1.0,
        pool_connections: int = 10,
        pool_maxsize: int = 20,
        timeout: float = 15.0
    ) -> requests.Session:
        """
        创建优化的HTTP会话
        
        Args:
            max_retries: 最大重试次数
            backoff_factor: 重试间隔因子
            pool_connections: 连接池数量
            pool_maxsize: 连接池最大大小
            timeout: 默认超时时间
            
        Returns:
            配置好的requests.Session对象
        """
        session = requests.Session()
        
        # 配置重试策略
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST"],
            raise_on_status=False
        )
        
        # 配置HTTP适配器
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=pool_connections,
            pool_maxsize=pool_maxsize,
            pool_block=False
        )
        
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # 设置默认头部
        session.headers.update({
            'User-Agent': 'BinanceHeyue/1.0',
            'Connection': 'keep-alive',
            'Accept': 'application/json',
            'Accept-Encoding': 'gzip, deflate'
        })
        
        return session

class BinanceSession:
    """币安API专用会话管理器"""
    
    def __init__(self):
        self.session = NetworkSession.create_session(
            max_retries=3,
            backoff_factor=0.5,
            pool_connections=5,
            pool_maxsize=10
        )
        
        # 币安API特殊配置
        self.session.headers.update({
            'X-MBX-APIKEY': '',  # 如果需要API KEY
        })
        
    def get(self, url: str, **kwargs) -> requests.Response:
        """发送GET请求"""
        try:
            kwargs.setdefault('timeout', 15)
            response = self.session.get(url, **kwargs)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            logger.warning(f"请求失败: {url}, 错误: {e}")
            raise
            
    def close(self):
        """关闭会话"""
        if self.session:
            self.session.close()

# 全局币安会话实例
_binance_session = None

def get_binance_session() -> BinanceSession:
    """获取全局币安会话实例"""
    global _binance_session
    if _binance_session is None:
        _binance_session = BinanceSession()
    return _binance_session

def close_all_sessions():
    """关闭所有会话连接"""
    global _binance_session
    if _binance_session:
        _binance_session.close()
        _binance_session = None

# Windows网络优化建议
WINDOWS_NETWORK_TIPS = """
Windows网络连接优化建议:

1. 增加端口数量:
   netsh int ipv4 set dynamicport tcp start=1024 num=64511

2. 减少TIME_WAIT状态时间:
   netsh int ipv4 set global tcptimedwaitdelay=30

3. 启用TCP窗口缩放:
   netsh int tcp set global autotuninglevel=normal

4. 优化TCP连接:
   netsh int tcp set global chimney=enabled
   netsh int tcp set global rss=enabled
   netsh int tcp set global netdma=enabled

注意: 需要管理员权限执行这些命令
"""

def print_network_optimization_tips():
    """打印网络优化建议"""
    print(WINDOWS_NETWORK_TIPS)