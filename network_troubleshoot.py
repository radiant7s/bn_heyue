#!/usr/bin/env python3
"""
network_troubleshoot.py - 网络故障诊断和修复工具

用于诊断和修复 WinError 10048 等网络连接问题
"""

import subprocess
import platform
import time
import sys
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

class NetworkTroubleshooter:
    """网络故障诊断器"""
    
    def __init__(self):
        self.is_windows = platform.system().lower() == 'windows'
        
    def check_system_info(self) -> Dict:
        """检查系统信息"""
        info = {
            'system': platform.system(),
            'version': platform.version(),
            'architecture': platform.architecture()[0]
        }
        
        if self.is_windows:
            try:
                # 检查Windows版本
                result = subprocess.run(['ver'], shell=True, capture_output=True, text=True)
                info['windows_version'] = result.stdout.strip()
            except Exception as e:
                info['windows_version'] = f"无法获取: {e}"
                
        return info
    
    def check_network_status(self) -> Dict:
        """检查网络状态"""
        status = {}
        
        # 检查网络连通性
        try:
            import requests
            response = requests.get('https://www.baidu.com', timeout=5)
            status['internet'] = response.status_code == 200
        except Exception as e:
            status['internet'] = False
            status['internet_error'] = str(e)
            
        # 检查币安API连通性
        try:
            import requests
            response = requests.get('https://fapi.binance.com/fapi/v1/ping', timeout=10)
            status['binance_api'] = response.status_code == 200
        except Exception as e:
            status['binance_api'] = False
            status['binance_error'] = str(e)
            
        return status
    
    def check_port_usage(self) -> Dict:
        """检查端口使用情况"""
        port_info = {}
        
        if self.is_windows:
            try:
                # 检查TCP连接状态
                result = subprocess.run(['netstat', '-an'], capture_output=True, text=True)
                lines = result.stdout.split('\n')
                
                tcp_states = {}
                for line in lines:
                    if 'TCP' in line:
                        parts = line.split()
                        if len(parts) >= 4:
                            state = parts[3] if len(parts) > 3 else 'UNKNOWN'
                            tcp_states[state] = tcp_states.get(state, 0) + 1
                            
                port_info['tcp_states'] = tcp_states
                
                # 检查TIME_WAIT状态的连接数
                time_wait_count = tcp_states.get('TIME_WAIT', 0)
                port_info['time_wait_connections'] = time_wait_count
                port_info['time_wait_warning'] = time_wait_count > 1000
                
            except Exception as e:
                port_info['error'] = str(e)
                
        return port_info
    
    def get_windows_network_config(self) -> Dict:
        """获取Windows网络配置"""
        config = {}
        
        if not self.is_windows:
            return config
            
        try:
            # 检查动态端口范围
            result = subprocess.run(['netsh', 'int', 'ipv4', 'show', 'dynamicport', 'tcp'], 
                                  capture_output=True, text=True)
            config['dynamic_port_range'] = result.stdout.strip()
            
            # 检查TCP设置
            result = subprocess.run(['netsh', 'int', 'tcp', 'show', 'global'], 
                                  capture_output=True, text=True)
            config['tcp_global_settings'] = result.stdout.strip()
            
        except Exception as e:
            config['error'] = str(e)
            
        return config
    
    def apply_windows_network_optimization(self) -> List[str]:
        """应用Windows网络优化（需要管理员权限）"""
        if not self.is_windows:
            return ["此功能仅适用于Windows系统"]
            
        commands = [
            # 增加动态端口范围
            ['netsh', 'int', 'ipv4', 'set', 'dynamicport', 'tcp', 'start=1024', 'num=64511'],
            
            # 减少TIME_WAIT状态时间
            ['netsh', 'int', 'ipv4', 'set', 'global', 'tcptimedwaitdelay=30'],
            
            # 启用TCP优化
            ['netsh', 'int', 'tcp', 'set', 'global', 'autotuninglevel=normal'],
            ['netsh', 'int', 'tcp', 'set', 'global', 'chimney=enabled'],
            ['netsh', 'int', 'tcp', 'set', 'global', 'rss=enabled'],
        ]
        
        results = []
        for cmd in commands:
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                results.append(f"✓ {' '.join(cmd)}: 成功")
            except subprocess.CalledProcessError as e:
                results.append(f"✗ {' '.join(cmd)}: 失败 - {e}")
            except Exception as e:
                results.append(f"✗ {' '.join(cmd)}: 错误 - {e}")
                
        return results
    
    def generate_report(self) -> str:
        """生成诊断报告"""
        report = []
        report.append("=" * 60)
        report.append("币安合约异动检测系统 - 网络诊断报告")
        report.append("=" * 60)
        report.append(f"生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        # 系统信息
        sys_info = self.check_system_info()
        report.append("📋 系统信息:")
        for key, value in sys_info.items():
            report.append(f"  {key}: {value}")
        report.append("")
        
        # 网络状态
        net_status = self.check_network_status()
        report.append("🌐 网络连通性:")
        for key, value in net_status.items():
            status = "✓" if value is True else "✗" if value is False else "?"
            report.append(f"  {status} {key}: {value}")
        report.append("")
        
        # 端口使用情况
        port_info = self.check_port_usage()
        report.append("🔌 端口使用情况:")
        if 'tcp_states' in port_info:
            for state, count in port_info['tcp_states'].items():
                warning = " ⚠️" if state == 'TIME_WAIT' and count > 1000 else ""
                report.append(f"  {state}: {count}{warning}")
        if 'time_wait_warning' in port_info and port_info['time_wait_warning']:
            report.append("  ⚠️  TIME_WAIT连接过多，可能导致端口耗尽")
        report.append("")
        
        # Windows网络配置
        if self.is_windows:
            config = self.get_windows_network_config()
            report.append("⚙️  Windows网络配置:")
            for key, value in config.items():
                if 'error' not in key:
                    report.append(f"  {key}:")
                    for line in str(value).split('\n')[:5]:  # 只显示前5行
                        if line.strip():
                            report.append(f"    {line.strip()}")
            report.append("")
        
        # 建议
        report.append("💡 建议:")
        if not net_status.get('internet', False):
            report.append("  - 检查网络连接")
        if not net_status.get('binance_api', False):
            report.append("  - 检查币安API访问（可能需要VPN）")
        if port_info.get('time_wait_warning', False):
            report.append("  - 优化Windows网络设置以减少TIME_WAIT连接")
            report.append("  - 运行网络优化命令（需要管理员权限）")
        report.append("  - 重启应用程序")
        report.append("  - 如果问题持续，考虑重启系统")
        
        return "\n".join(report)

def main():
    """主函数"""
    troubleshooter = NetworkTroubleshooter()
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == 'optimize':
            print("正在应用Windows网络优化...")
            print("注意: 需要管理员权限!")
            print()
            
            results = troubleshooter.apply_windows_network_optimization()
            for result in results:
                print(result)
                
        elif command == 'check':
            print("正在进行网络诊断...")
            print()
            print(troubleshooter.generate_report())
            
        else:
            print("使用方法:")
            print("  python network_troubleshoot.py check     - 生成诊断报告")
            print("  python network_troubleshoot.py optimize  - 应用网络优化")
    else:
        # 默认生成报告
        print(troubleshooter.generate_report())

if __name__ == "__main__":
    main()