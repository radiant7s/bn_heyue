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