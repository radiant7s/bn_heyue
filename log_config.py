#!/usr/bin/env python3
"""
log_config.py - 统一日志配置

将日志输出到控制台和文件（带滚动），供各模块调用 setup_logging()。
"""
import logging
import os
from logging.handlers import RotatingFileHandler

LOG_DIR = os.path.join(os.path.dirname(__file__), 'logs')
LOG_FILE = os.path.join(LOG_DIR, 'heyue.log')


def setup_logging(level: int = logging.INFO):
    """配置根日志记录器：
    - 控制台 (StreamHandler)
    - 文件 (RotatingFileHandler)
    如果已经配置过处理器，则不会重复添加（幂等）。
    """
    os.makedirs(LOG_DIR, exist_ok=True)

    logger = logging.getLogger()
    logger.setLevel(level)

    # 如果已经添加了 handler，跳过（避免重复）
    if logger.handlers:
        return

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 控制台输出
    sh = logging.StreamHandler()
    sh.setLevel(level)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    # 日志文件（滚动）
    fh = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5, encoding='utf-8')
    fh.setLevel(level)
    fh.setFormatter(fmt)
    logger.addHandler(fh)


if __name__ == '__main__':
    setup_logging()
    logging.getLogger(__name__).info('日志配置已初始化，日志文件: %s', LOG_FILE)
