#!/usr/bin/env python3
"""
fix_network_issues.py - 网络问题修复脚本

一键修复 WinError 10048 等网络连接问题
"""

import os
import sys
import subprocess
import time
import logging
from datetime import datetime

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(f'logs/network_fix_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def check_admin_privileges():
    """检查是否有管理员权限"""
    try:
        return os.getuid() == 0
    except AttributeError:
        # Windows
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0

def apply_windows_network_fixes():
    """应用Windows网络修复"""
    logger.info("开始应用Windows网络优化...")
    
    # 需要管理员权限的命令
    commands = [
        # 增加动态端口范围
        "netsh int ipv4 set dynamicport tcp start=1024 num=64511",
        
        # 减少TIME_WAIT状态时间
        "netsh int ipv4 set global tcptimedwaitdelay=30",
        
        # 启用TCP窗口缩放
        "netsh int tcp set global autotuninglevel=normal",
        
        # 优化TCP连接
        "netsh int tcp set global chimney=enabled",
        "netsh int tcp set global rss=enabled",
        
        # 重置Winsock目录
        "netsh winsock reset",
        
        # 刷新DNS
        "ipconfig /flushdns",
    ]
    
    success_count = 0
    for cmd in commands:
        try:
            logger.info(f"执行: {cmd}")
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                logger.info(f"✓ 成功: {cmd}")
                success_count += 1
            else:
                logger.warning(f"✗ 失败: {cmd}")
                logger.warning(f"错误输出: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            logger.error(f"✗ 超时: {cmd}")
        except Exception as e:
            logger.error(f"✗ 异常: {cmd} - {e}")
    
    logger.info(f"网络优化完成: {success_count}/{len(commands)} 个命令成功执行")
    
    if success_count > 0:
        logger.info("建议重启系统以使所有更改生效")
        return True
    else:
        logger.error("没有成功执行任何优化命令，请检查权限")
        return False

def check_and_install_dependencies():
    """检查并安装必要的依赖"""
    logger.info("检查Python依赖...")
    
    required_packages = [
        'requests',
        'urllib3',
        'websocket-client',
        'schedule',
        'numpy'
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            logger.info(f"✓ {package} 已安装")
        except ImportError:
            missing_packages.append(package)
            logger.warning(f"✗ {package} 未安装")
    
    if missing_packages:
        logger.info(f"正在安装缺失的包: {', '.join(missing_packages)}")
        try:
            subprocess.run([
                sys.executable, '-m', 'pip', 'install', '--upgrade'
            ] + missing_packages, check=True)
            logger.info("✓ 依赖安装完成")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"✗ 依赖安装失败: {e}")
            return False
    else:
        logger.info("✓ 所有依赖都已安装")
        return True

def restart_services():
    """重启相关服务"""
    logger.info("正在停止现有进程...")
    
    try:
        # 查找并终止可能的Python进程
        if os.name == 'nt':  # Windows
            subprocess.run('taskkill /f /im python.exe', shell=True, capture_output=True)
            subprocess.run('taskkill /f /im pythonw.exe', shell=True, capture_output=True)
        else:  # Linux/Mac
            subprocess.run('pkill -f "python.*main.py"', shell=True, capture_output=True)
            
        logger.info("✓ 已尝试停止现有进程")
        time.sleep(2)
        
    except Exception as e:
        logger.warning(f"停止进程时出现问题: {e}")

def create_startup_script():
    """创建优化的启动脚本"""
    logger.info("创建优化的启动脚本...")
    
    if os.name == 'nt':  # Windows
        script_content = '''@echo off
echo 启动币安合约异动检测系统...
echo 应用网络优化设置...

REM 设置环境变量
set PYTHONIOENCODING=utf-8
set REQUESTS_CA_BUNDLE=""

REM 启动系统
cd /d "%~dp0"
python main.py

pause
'''
        script_name = 'start_optimized.bat'
    else:  # Linux/Mac
        script_content = '''#!/bin/bash
echo "启动币安合约异动检测系统..."
echo "应用网络优化设置..."

# 设置环境变量
export PYTHONIOENCODING=utf-8
export REQUESTS_CA_BUNDLE=""

# 启动系统
cd "$(dirname "$0")"
python3 main.py
'''
        script_name = 'start_optimized.sh'
    
    try:
        with open(script_name, 'w', encoding='utf-8') as f:
            f.write(script_content)
        
        if os.name != 'nt':
            os.chmod(script_name, 0o755)
            
        logger.info(f"✓ 创建启动脚本: {script_name}")
        return True
        
    except Exception as e:
        logger.error(f"✗ 创建启动脚本失败: {e}")
        return False

def verify_fixes():
    """验证修复效果"""
    logger.info("验证修复效果...")
    
    try:
        import requests
        from network_config import get_binance_session
        
        # 测试网络连接
        session = get_binance_session()
        response = session.get("https://fapi.binance.com/fapi/v1/ping")
        
        if response.status_code == 200:
            logger.info("✓ 币安API连接测试成功")
            return True
        else:
            logger.warning(f"✗ 币安API连接测试失败: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"✗ 连接测试异常: {e}")
        return False

def main():
    """主修复流程"""
    logger.info("=" * 60)
    logger.info("币安合约异动检测系统 - 网络问题修复工具")
    logger.info("=" * 60)
    logger.info(f"开始时间: {datetime.now()}")
    logger.info("")
    
    success_steps = 0
    total_steps = 4
    
    # 步骤1: 检查管理员权限
    logger.info("步骤 1/4: 检查权限...")
    if check_admin_privileges():
        logger.info("✓ 检测到管理员权限")
    else:
        logger.warning("⚠️  未检测到管理员权限，某些优化可能无法应用")
        logger.warning("建议以管理员身份运行此脚本")
    
    # 步骤2: 安装依赖
    logger.info("步骤 2/4: 检查依赖...")
    if check_and_install_dependencies():
        success_steps += 1
    
    # 步骤3: 应用网络优化
    logger.info("步骤 3/4: 应用网络优化...")
    if os.name == 'nt' and check_admin_privileges():
        if apply_windows_network_fixes():
            success_steps += 1
    else:
        logger.info("跳过Windows网络优化（非Windows系统或无管理员权限）")
        success_steps += 1
    
    # 步骤4: 重启服务
    logger.info("步骤 4/4: 准备重启...")
    restart_services()
    if create_startup_script():
        success_steps += 1
    
    # 最终报告
    logger.info("")
    logger.info("=" * 60)
    logger.info("修复完成报告")
    logger.info("=" * 60)
    logger.info(f"成功完成: {success_steps}/{total_steps} 个步骤")
    
    if success_steps >= 3:
        logger.info("✓ 修复基本成功！")
        logger.info("")
        logger.info("后续步骤:")
        logger.info("1. 重启系统（推荐）")
        logger.info("2. 使用 start_optimized.bat/sh 启动系统")
        logger.info("3. 如果仍有问题，运行: python network_troubleshoot.py check")
    else:
        logger.error("✗ 修复未完全成功，请检查错误信息")
        logger.info("")
        logger.info("故障排除:")
        logger.info("1. 确保以管理员身份运行")
        logger.info("2. 检查网络连接")
        logger.info("3. 运行: python network_troubleshoot.py check")
    
    logger.info(f"结束时间: {datetime.now()}")

if __name__ == "__main__":
    # 确保日志目录存在
    os.makedirs('logs', exist_ok=True)
    main()