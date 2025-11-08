# 网络连接问题解决方案

## 问题描述

你的币安合约异动检测系统遇到了 **WinError 10048** 错误：

```
OSError: [WinError 10048] 通常每个套接字地址(协议/网络地址/端口)只允许使用一次。
```

### 问题原因

1. **端口耗尽**: Windows系统的动态端口范围有限，频繁的HTTP请求导致端口被耗尽
2. **TIME_WAIT状态积累**: 大量连接处于TIME_WAIT状态，占用端口资源
3. **连接池配置不当**: 没有合理配置HTTP连接池和重试策略
4. **请求频率过高**: 系统每3分钟向币安API发送多个请求

### 错误影响

- 持仓量排行更新失败
- 无法连接币安API (`fapi.binance.com:443`)
- 系统功能受限

## 解决方案

### 🚀 快速修复（推荐）

1. **以管理员身份运行PowerShell**
2. **执行一键修复脚本**:
   ```powershell
   cd d:\ai\heyue
   python fix_network_issues.py
   ```

### 🔧 手动修复步骤

#### 步骤1: 优化Windows网络设置

**以管理员身份运行PowerShell，执行以下命令:**

```powershell
# 增加动态端口范围
netsh int ipv4 set dynamicport tcp start=1024 num=64511

# 减少TIME_WAIT状态时间
netsh int ipv4 set global tcptimedwaitdelay=30

# 启用TCP窗口缩放
netsh int tcp set global autotuninglevel=normal

# 优化TCP连接
netsh int tcp set global chimney=enabled
netsh int tcp set global rss=enabled

# 重置网络配置
netsh winsock reset
ipconfig /flushdns
```

#### 步骤2: 重启系统
```powershell
shutdown /r /t 0
```

#### 步骤3: 使用优化的启动脚本
```powershell
# 使用新的启动脚本
start_optimized.bat
```

### 🔍 问题诊断

**运行网络诊断工具:**
```powershell
python network_troubleshoot.py check
```

**查看详细诊断:**
```powershell
python network_troubleshoot.py optimize
```

## 代码改进

### 主要改进点

1. **连接池管理**: 
   - 统一的HTTP会话管理
   - 连接池大小优化
   - 自动重试策略

2. **错误处理增强**:
   - 更好的异常捕获
   - 重试机制
   - 优雅的降级处理

3. **资源清理**:
   - 会话连接自动关闭
   - 内存泄漏防护

### 修改的文件

- `data_updater.py`: 添加连接池和重试机制
- `anomaly_detector.py`: 优化网络请求
- `config.py`: 添加网络配置参数
- `network_config.py`: 新增统一网络管理
- `network_troubleshoot.py`: 网络诊断工具
- `fix_network_issues.py`: 一键修复脚本

## 使用建议

### 启动方式

**方式1: 使用优化的启动脚本**
```powershell
.\start_optimized.bat
```

**方式2: 直接启动（确保已优化网络）**
```powershell
python main.py
```

### 监控建议

1. **定期检查网络状态**:
   ```powershell
   python network_troubleshoot.py check
   ```

2. **监控日志文件**:
   - 查看 `logs/heyue.log` 中的网络错误
   - 观察连接失败频率

3. **系统资源监控**:
   - 使用任务管理器监控网络连接数
   - 观察内存使用情况

### 预防措施

1. **定期重启系统**: 清理网络状态
2. **监控连接数**: 避免过多TIME_WAIT连接
3. **合理设置更新频率**: 可以将更新间隔适当延长

## 常见问题

### Q: 修复后仍然出现网络错误？
**A**: 
1. 确认已以管理员权限执行修复
2. 重启系统后再试
3. 检查防火墙设置
4. 运行网络诊断工具

### Q: 币安API访问被限制？
**A**: 
1. 检查网络连接
2. 可能需要VPN
3. 确认API限制情况

### Q: 系统运行一段时间后又出现问题？
**A**: 
1. 定期重启应用
2. 监控系统资源
3. 考虑增加更新间隔

## 技术细节

### WinError 10048 详细说明

这个错误通常发生在:
- 端口资源耗尽
- TIME_WAIT状态连接过多
- 应用程序创建连接过快
- 没有正确复用连接

### 优化原理

1. **连接池**: 复用HTTP连接，减少新连接创建
2. **重试策略**: 智能重试，避免立即失败
3. **超时设置**: 合理的超时时间，避免连接挂起
4. **资源清理**: 及时释放网络资源

## 更新日志

- **2025-11-08**: 
  - 添加统一网络管理
  - 修复WinError 10048问题
  - 增加诊断和修复工具
  - 优化连接池配置

---

如果问题仍然存在，请运行诊断工具并查看详细日志。