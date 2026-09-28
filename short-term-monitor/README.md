# 短线选股监控系统

基于六维短线选股体系的实时监控系统，集成**新闻热点、涨停板、龙二选股、资金流向、筹码分析、风险监控**六大模块，支持**飞书机器人异动告警**和**Web可视化Dashboard**，可部署在服务器 7×24 小时自动运行。

## 功能特性

| 模块 | 功能 | 监控频率 |
|---|---|---|
| 📰 新闻热点 | 政策/利好/重组/订单等关键词监控，关联异动个股 | 每5分钟 |
| 🚀 涨停板复盘 | 涨停家数、连板高度、龙头股识别、封板质量、连板分布 | 每日15:10 |
| 🐉 龙二选股 | 基于龙头股自动筛选同题材低位补涨标的，按评分排序 | 每日15:30 |
| 💰 资金流向 | 主力净流入TOP、热门板块、北向资金、龙虎榜 | 每10分钟 |
| 🎯 筹码分析 | 获利比例、平均成本、筹码集中度、筹码峰识别 | 按需 |
| ⚠️ 风险监控 | 市场过热/恐慌、涨跌停比、北向流出、高位板风险 | 每15分钟 |
| 👀 自选股监控 | 涨跌幅/量比异动实时告警 | 每5分钟 |
| 📱 飞书通知 | 8类异动自动推送飞书群，支持签名校验 | 实时 |
| 🖥️ Web Dashboard | 深色主题可视化面板，数据每30秒自动刷新 | 实时 |

## 系统架构

```
┌─────────────────────────────────────────────────────┐
│                   定时调度器 (APScheduler)             │
│  新闻5min | 资金10min | 风险15min | 自选股5min       │
│  涨停板15:10 | 龙二15:30 | 每日总结16:00             │
└──────────────┬──────────────────┬───────────────────┘
               │                  │
    ┌──────────▼─────────┐  ┌─────▼──────────┐
    │   六大监控模块       │  │  飞书机器人      │
    │  新闻/涨停/龙二      │  │  异动告警推送    │
    │  资金/筹码/风险      │  │  8类通知类型     │
    └──────────┬─────────┘  └────────────────┘
               │
    ┌──────────▼─────────┐
    │   数据层 (akshare)   │
    │  行情/资金/新闻/龙虎榜 │
    └────────────────────┘
               │
    ┌──────────▼─────────┐
    │  Web Dashboard       │
    │  Flask + 实时刷新     │
    │  http://IP:8080      │
    └────────────────────┘
```

## 快速开始

### 方式一：Docker 部署（推荐）

```bash
# 1. 克隆/上传项目到服务器
cd /opt
git clone <项目地址> short-term-monitor
cd short-term-monitor

# 2. 配置飞书机器人
cp .env.example .env
vi .env
# 填写 FEISHU_WEBHOOK_URL 和 FEISHU_SECRET

# 3. 启动
cd deploy
docker-compose up -d

# 4. 查看日志
docker-compose logs -f

# 5. 访问面板
# 浏览器打开 http://服务器IP:8080
```

### 方式二：Linux 一键安装脚本

```bash
# 上传项目后执行
cd short-term-monitor
sudo bash deploy/install.sh

# 安装完成后配置并启动
vi /opt/short-term-monitor/.env
sudo systemctl start short-term-monitor
sudo systemctl status short-term-monitor
```

### 方式三：手动部署

```bash
# 1. 安装 Python 3.10+
# 2. 安装依赖
cd short-term-monitor
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. 配置
cp .env.example .env
vi .env

# 4. 启动
python -m src.main

# 5. 访问 http://localhost:8080
```

### 方式四：Windows 部署

```bat
# 1. 安装 Python 3.10+
# 2. 安装依赖
cd short-term-monitor
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# 3. 配置 .env
# 4. 启动
python -m src.main

# 5. 访问 http://localhost:8080
# 6. 如需开机自启，使用任务计划程序
```

## 飞书机器人配置指南

### 第一步：创建飞书机器人

1. 打开飞书，进入目标群聊
2. 点击群设置 → 群机器人 → 添加机器人
3. 选择「自定义机器人」
4. 设置机器人名称（如「短线监控助手」）和头像
5. 点击「添加」，复制生成的 **Webhook 地址**

### 第二步：配置安全设置（推荐）

1. 在机器人设置页面，找到「安全设置」
2. 勾选「签名校验」
3. 复制生成的 **签名密钥**（Secret）

### 第三步：填写配置

编辑 `.env` 文件：

```env
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/你的hook_id
FEISHU_SECRET=你的签名密钥
ENABLE_FEISHU_NOTIFY=true
```

### 第四步：重启服务

```bash
# Docker
docker-compose restart

# systemd
sudo systemctl restart short-term-monitor
```

### 通知类型说明

| 通知类型 | 触发条件 | 卡片颜色 |
|---|---|---|
| 新闻异动 | 匹配关键词的新闻出现 | 默认 |
| 涨停板复盘 | 每日15:10自动推送 | 红色 |
| 龙二选股 | 每日15:30推送选股结果 | 橙色 |
| 资金异动 | 主力净流入超3只/北向超5亿/有龙虎榜 | 默认 |
| 风险预警 | 市场过热/恐慌/北向流出/高位板 | 红色/橙色 |
| 自选股异动 | 涨跌幅超5%或量比超2 | 默认 |
| 每日总结 | 每日16:00推送全市场复盘 | 蓝色 |

## 配置说明

### 核心配置（.env）

```env
# 飞书机器人
FEISHU_WEBHOOK_URL=你的webhook地址
FEISHU_SECRET=你的签名密钥
ENABLE_FEISHU_NOTIFY=true

# 自选股监控（逗号分隔）
WATCHLIST=600519,000001,300750
WATCHLIST_ALERT_CHANGE_PCT=5     # 涨跌幅告警阈值%

# Web服务
WEB_HOST=0.0.0.0
WEB_PORT=8080

# 日志
LOG_LEVEL=INFO
```

### 高级配置（config/config.yaml）

可调整各模块的监控阈值，如：
- 新闻监控关键词
- 龙二选股的市值/涨幅/量比阈值
- 资金流向的净流入阈值
- 风险监控的涨停/跌停阈值
- 止损比例等

## 项目结构

```
short-term-monitor/
├── config/
│   └── config.yaml              # 主配置
├── src/
│   ├── main.py                  # 主入口
│   ├── config_loader.py         # 配置加载
│   ├── logger.py                # 日志
│   ├── monitor/                 # 六大监控模块
│   │   ├── news_monitor.py      # 新闻热点
│   │   ├── limit_up_monitor.py  # 涨停板
│   │   ├── dragon2_selector.py  # 龙二选股
│   │   ├── capital_flow.py      # 资金流向
│   │   ├── chip_analysis.py     # 筹码分析
│   │   └── risk_monitor.py      # 风险监控
│   ├── notification/
│   │   └── feishu_bot.py        # 飞书机器人
│   ├── data/
│   │   └── data_fetcher.py      # 数据获取(akshare)
│   ├── scheduler/
│   │   └── monitor_scheduler.py  # 定时调度器
│   └── web/
│       ├── app.py               # Flask应用
│       └── templates/
│           └── dashboard.html    # Dashboard页面
├── deploy/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── install.sh               # Linux一键安装
│   └── monitor.service          # systemd服务
├── logs/                        # 日志
├── data/                        # 监控数据(JSON)
├── requirements.txt
├── .env.example
└── README.md
```

## 常用命令

```bash
# 查看服务状态
sudo systemctl status short-term-monitor

# 查看实时日志
sudo journalctl -u short-term-monitor -f
tail -f /opt/short-term-monitor/logs/*.log

# 重启服务
sudo systemctl restart short-term-monitor

# Docker 方式
docker-compose logs -f
docker-compose restart
docker-compose down

# 仅查看Web面板（不启动监控）
python -m src.main --web-only

# 仅启动监控（不开Web）
python -m src.main --monitor-only
```

## 常见问题

### Q: 飞书机器人收不到消息？
A: 检查：1) Webhook地址是否正确；2) 签名密钥是否匹配；3) `.env` 中 `ENABLE_FEISHU_NOTIFY=true`；4) 查看日志是否有发送失败错误。

### Q: Web面板打不开？
A: 检查：1) 服务是否启动 `systemctl status`；2) 端口8080是否放行 `ufw allow 8080`；3) 云服务器安全组是否开放8080端口。

### Q: 数据不更新？
A: 系统仅在A股交易时段（周一至周五 9:30-15:00）活跃更新。非交易时段数据为最近一次结果。akshare接口偶尔限流，可查看日志。

### Q: 如何添加自选股？
A: 编辑 `.env`，设置 `WATCHLIST=600519,000001,300750`（逗号分隔，6位代码），重启服务生效。

### Q: 如何调整监控阈值？
A: 编辑 `config/config.yaml`，找到对应模块的配置项修改，重启服务生效。

## 风险提示

1. 本系统仅供学习研究使用，**不构成任何投资建议**。
2. 所有数据来自公开接口（akshare），**不保证实时性和准确性**。
3. 选股结果和异动告警仅为参考，**投资决策请自行判断**。
4. 股市有风险，入市需谨慎。

## 技术栈

- **语言**: Python 3.10+
- **数据**: akshare（免费开源财经数据接口）
- **调度**: APScheduler
- **Web**: Flask + 原生HTML/CSS/JS
- **通知**: 飞书自定义机器人 Webhook
- **部署**: Docker / systemd / 一键脚本

---

**版本**: v1.0.0
**更新日期**: 2026-09-18
