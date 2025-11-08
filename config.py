# config.py - 数据库配置文件

# 数据库配置
DATABASE_CONFIG = {
    # 数据库文件路径
    "db_path": "data.db",
    
    # 数据保留时间（小时）
    "max_age_hours": 24,
    
    # 清理检查间隔（秒）
    "cleanup_interval": 3600,  # 1小时
    
    # 自动清理开关
    "auto_cleanup": True,
    
    # 数据库大小限制（MB，0表示无限制）
    "max_db_size_mb": 100,
    
    # 记录数限制（0表示无限制）
    "max_klines_per_symbol": 10000,
}

# 网络配置
NETWORK_CONFIG = {
    # HTTP请求超时时间（秒）
    "timeout": 15,
    
    # 最大重试次数
    "max_retries": 3,
    
    # 重试间隔因子
    "backoff_factor": 1.0,
    
    # 连接池配置
    "pool_connections": 10,
    "pool_maxsize": 20,
    
    # 数据更新间隔（秒）
    "update_interval": 180,  # 3分钟
    
    # 异动检测间隔（秒）
    "anomaly_check_interval": 60,  # 1分钟
}

# 日志配置
LOGGING_CONFIG = {
    "level": "INFO",
    "format": "%(asctime)s - %(levelname)s - %(message)s",
    "cleanup_log": True,  # 是否记录清理日志
}

# 性能优化配置
PERFORMANCE_CONFIG = {
    # 批量插入大小
    "batch_insert_size": 100,
    
    # 索引优化
    "enable_extra_indexes": True,
    
    # 定期VACUUM间隔（秒）
    "vacuum_interval": 86400,  # 24小时
}