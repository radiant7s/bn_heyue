# 币安合约异动检测系统

一个基于WebSocket实时数据收集和多维度异动检测的完整系统，用于监控币安USDT永续合约的价格异动。

## 🚀 系统特性

### 实时数据收集
- **WebSocket连接**：实时收集150个活跃USDT永续合约的15分钟K线数据
- **智能历史数据初始化**：启动时仅对K线不足16条的合约获取历史数据，避免重复下载
- **自动去重**：数据库UNIQUE约束自动处理重复数据，WebSocket实时更新无重复问题
- **智能筛选**：按24小时成交额筛选最活跃的合约，减少噪声
- **本地存储**：所有数据存储在SQLite数据库，支持快速查询

### 多维度异动检测
- **价格异动**：基于历史15分钟收益率的z-score和百分位数分析
- **成交量异动**：检测当前成交量相对历史平均的异常情况
- **波动率异动**：分析真实波动率（高低价差）的异常变化
- **综合评分**：多维度加权评分，智能识别综合异动

### 数据更新服务
- **AI选币决策**：基于多维度指标的智能选币排行
- **持仓量排行**：实时持仓量变化监控
- **自动更新**：每3分钟自动更新排行数据

### 数据存储管理
- **自动清理**：超过24小时的数据自动删除
- **存储上限**：数据库大小和记录数智能限制
- **配置化管理**：可自定义数据保留策略

### API服务
- **RESTful接口**：提供HTTP API快速查询异动数据
- **实时响应**：无需等待实时计算，毫秒级响应
- **多种查询**：支持按时间、评分、类型等多种筛选条件

## 📁 文件结构

```
├── main.py                 # 主启动脚本（集成所有服务）
├── database.py             # 数据库管理模块（含存储上限管理）
├── config.py               # 配置文件（数据库、清理等设置）
├── ws_collector.py         # WebSocket数据收集器
├── anomaly_detector.py     # 异动检测引擎
├── data_updater.py         # 数据更新器（AI选币、持仓量排行）
├── oi_collector.py         # 持仓量数据收集器
├── api_server.py           # API服务器
├── cleanup.py              # 数据库清理工具
├── requirements.txt        # Python依赖
├── .gitignore             # Git忽略规则
├── data.db                # SQLite数据库（自动创建）
├── DATABASE_MANAGEMENT.md # 数据库管理详细文档
└── README.md              # 本文档
```

## 🔧 快速开始

### 1. 安装依赖
```powershell
pip install -r requirements.txt
```

### 2. 启动完整系统
```powershell
python main.py
```

系统启动后会显示：
- 数据库配置信息（数据保留时间、大小限制等）
- 各服务状态（WebSocket收集器、异动检测器、数据更新器、API服务器）
- API接口地址和端口

### 3. 数据库管理
```powershell
# 查看数据库状态
python cleanup.py --info

# 手动清理数据
python cleanup.py --hours 12

# 强制清理（不询问确认）
python cleanup.py --hours 6 --force
```

## 🖥️ 使用方式

### 完整实时系统（推荐）
启动后包含四个组件：
- **WebSocket数据收集器**：实时收集150个合约的K线数据
- **异动检测引擎**：每分钟检测异动并存储结果
- **数据更新器**：每3分钟更新AI选币排行和持仓量排行
- **API服务器**：提供HTTP接口（http://localhost:5000）

```powershell
python main.py
```

启动完成后系统会持续运行，并每30秒显示状态信息。

### 数据库管理工具
```powershell
# 查看详细数据库信息
python cleanup.py --info

# 清理超过指定时间的数据
python cleanup.py --hours 24

# 配置自动清理（编辑 config.py）
# max_age_hours: 数据保留时间
# cleanup_interval: 清理检查间隔
# max_db_size_mb: 文件大小限制
```

## 📊 API接口

系统启动后可通过以下接口查询数据：

### 主要接口
- **健康检查**：`GET /api/health` - 系统状态和数据库信息
- **AI选币排行**：`GET /api/coins` - 基于多维度评分的选币建议
- **持仓量排行**：`GET /api/oitop` - 持仓量变化排行榜
- **异动数据**：`GET /api/anomalies/top` - 最新异动检测结果
- **异动筛选**：`GET /api/anomalies?anomaly_only=true&min_score=1.0` - 按条件筛选异动

### API示例
```bash
# 获取AI选币建议（前20个）
curl "http://localhost:5000/api/coins"

# 获取持仓量排行
curl "http://localhost:5000/api/oitop"

# 获取评分最高的异动
curl "http://localhost:5000/api/anomalies/top?limit=10"

# 获取显著异动（评分>2.0）
curl "http://localhost:5000/api/anomalies?anomaly_only=true&min_score=2.0"

# 查看系统健康状态
curl "http://localhost:5000/api/health"
```

### 响应格式
所有API返回JSON格式数据，包含：
- `data`: 主要数据内容
- `count`: 结果数量
- `timestamp`: 数据时间戳
- `status`: 请求状态

## ⚙️ 配置参数

### 数据库配置 (config.py)
```python
DATABASE_CONFIG = {
    "max_age_hours": 24,        # 数据保留时间（小时）
    "cleanup_interval": 3600,   # 清理检查间隔（秒）
    "auto_cleanup": True,       # 自动清理开关
    "max_db_size_mb": 100,      # 数据库大小限制（MB）
    "max_klines_per_symbol": 10000,  # 单合约K线数量限制
}
```

### WebSocket收集器 (ws_collector.py)
```python
"MIN_VOL_24H": 5000.0,      # 最小24h成交量筛选
"TOP_N_SYMBOLS": 150,       # 监控的合约数量
"HISTORY_KLINES": 16,       # 初始化历史K线数量（仅不足时获取）
```

### 异动检测器 (anomaly_detector.py)
```python
"PRICE_Z_THRESHOLD": 2.5,    # 价格异动z-score阈值
"VOLUME_Z_THRESHOLD": 2.0,   # 成交量异动z-score阈值
"VOLATILITY_Z_THRESHOLD": 2.0, # 波动率异动z-score阈值
"MIN_ABS_RETURN": 0.01,      # 最小绝对收益率1%
```

### 数据更新器 (data_updater.py)
```python
"UPDATE_INTERVAL": 180,      # 更新间隔（秒）
"TOP_COINS_LIMIT": 20,       # AI选币数量限制
"OI_RANKINGS_LIMIT": 20,     # 持仓量排行数量限制
```

## 🗃️ 数据库结构

### 核心数据表

#### klines表（K线数据）
- `symbol, open_time, close_time`：合约标识和时间
- `open_price, high_price, low_price, close_price`：OHLC价格
- `volume, quote_volume, trades_count`：成交量和交易数
- `created_at`：数据创建时间

#### anomalies表（异动数据）
- `symbol, timestamp, interval_type`：合约、时间、间隔类型
- `cur_return, price_zscore, volume_zscore, volatility_zscore`：收益率和异动指标
- `anomaly_score, anomaly_reasons`：综合评分和异动原因
- `quote_volume_24h`：24小时成交额

#### ai_coins表（AI选币数据）
- `symbol, score`：合约和评分
- `start_time, start_price, current_price, max_price`：价格跟踪
- `increase_percent, volume_24h, price_change_24h`：涨幅和成交量
- `updated_at`：更新时间

#### oi_rankings表（持仓量排行）
- `symbol, rank, current_oi`：合约、排名、当前持仓量
- `oi_delta, oi_delta_percent, oi_delta_value`：持仓量变化
- `price_delta_percent, net_long, net_short`：价格变化和多空比
- `volume_24h, updated_at`：成交量和更新时间

### 数据管理
- **自动清理**：超过24小时的数据自动删除
- **存储上限**：文件大小和记录数智能限制
- **索引优化**：关键字段建立索引提升查询性能
- **去重机制**：UNIQUE约束防止重复数据

## 🔍 系统优势

### 技术特点
1. **实时性能**：WebSocket实时数据 + 本地数据库，毫秒级响应
2. **智能管理**：自动数据清理、存储上限控制、去重机制
3. **多维分析**：价格、成交量、波动率、持仓量综合评估
4. **模块化设计**：独立的数据收集、检测、更新、API服务模块
5. **配置化管理**：灵活的参数配置，适应不同使用场景

### 数据优势
- **150个活跃合约**：覆盖主要USDT永续合约
- **多时间维度**：支持15分钟、5分钟、1分钟检测
- **历史数据积累**：本地存储便于历史分析
- **智能筛选**：按成交额预筛选，减少噪声

### 算法优势
- **统计学方法**：基于z-score和百分位数的科学异动判断
- **综合评分**：多维度加权评分，避免单一指标误判
- **动态阈值**：基于历史分布的自适应阈值
- **实时更新**：AI选币和持仓量排行实时更新

### 使用优势
- **即开即用**：一键启动，自动初始化
- **零配置**：默认参数适合大多数使用场景
- **多接口支持**：RESTful API + 命令行工具
- **故障恢复**：自动重连、重试机制

## 🚨 注意事项

1. **网络依赖**：需要稳定的网络连接到币安WebSocket和API服务器
2. **API限制**：系统自动控制请求频率，避免触发币安API限制
3. **数据延迟**：WebSocket数据有轻微延迟（通常<1秒）
4. **存储管理**：系统自动管理数据库大小，可通过config.py调整
5. **资源占用**：监控150个合约需要一定的CPU和内存资源

## 🔧 故障排除

### 常见问题

#### 启动相关
- **WebSocket连接失败**：检查网络连接，系统会自动重连
- **历史数据获取慢**：首次启动需要下载历史数据，请耐心等待
- **端口被占用**：修改api_server.py中的端口号

#### 运行相关
- **数据库锁定**：多个进程同时访问，停止其他进程或重启
- **API超时**：网络问题导致，系统有自动重试机制
- **无异动检测**：市场平稳时正常，可在配置中降低检测阈值

#### 性能相关
- **内存占用高**：正常现象，可通过减少监控合约数量优化
- **数据库过大**：调整config.py中的清理参数
- **响应速度慢**：检查数据库索引，考虑清理旧数据

### 系统监控
```powershell
# 检查数据库状态和大小
python cleanup.py --info

# 查看系统健康状态
curl http://localhost:5000/api/health

# 观察实时运行日志
python main.py  # 查看终端输出
```

### 配置优化
```python
# 调整监控合约数量（减少资源占用）
TOP_N_SYMBOLS = 100  # 默认150

# 调整数据保留时间（减少存储占用）
max_age_hours = 12   # 默认24

# 调整清理频率（提高清理效率）
cleanup_interval = 1800  # 默认3600（1小时）
```

## 📈 未来扩展

### 功能扩展
- **多时间框架**：支持5分钟、1分钟、1小时K线分析
- **技术指标集成**：RSI、MACD、布林带等技术指标异动检测
- **现货市场支持**：扩展到Binance Spot现货市场
- **跨交易所监控**：支持其他主流交易所（OKX、Bybit等）

### 智能化改进
- **机器学习模型**：基于历史数据训练异动预测模型
- **市场情绪分析**：结合社交媒体、新闻情绪分析
- **自适应阈值**：根据市场波动自动调整检测阈值
- **异动分类**：突破、放量、震荡等异动类型分类

### 用户体验
- **Web界面**：开发Web前端界面，实时图表展示
- **移动端支持**：微信小程序、APP推送
- **报警系统**：邮件、短信、钉钉等多渠道报警
- **自定义策略**：用户可配置个性化筛选策略

### 性能优化
- **分布式部署**：支持多节点部署，提高处理能力
- **缓存优化**：Redis缓存热点数据，提升响应速度
- **数据压缩**：历史数据压缩存储，减少磁盘占用
- **负载均衡**：API服务负载均衡，支持高并发

---

**提示**：
- 首次启动需要2-5分钟下载历史数据
- 启动完成后即可享受毫秒级异动查询
- 建议在稳定网络环境下运行
- 详细的数据库管理说明请查看 `DATABASE_MANAGEMENT.md`