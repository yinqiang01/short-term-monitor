"""Web可视化Dashboard - Flask应用"""
import json
from pathlib import Path
from flask import Flask, render_template, jsonify
from ..config_loader import get_config
from ..logger import get_logger

logger = get_logger("WebApp")

app = Flask(__name__,
            template_folder=str(Path(__file__).parent / "templates"),
            static_folder=str(Path(__file__).parent / "static"))

_config = None
_data_dir = None


def init_app(config: dict):
    """初始化应用配置"""
    global _config, _data_dir
    _config = config
    _data_dir = Path(config.get("system", {}).get("data_dir", "./data"))


def _read_data(name: str):
    """读取数据文件"""
    try:
        file_path = _data_dir / f"{name}.json"
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.debug(f"读取数据失败 {name}: {e}")
    return {}


@app.route("/")
def index():
    """Dashboard主页"""
    return render_template("dashboard.html")


@app.route("/api/summary")
def api_summary():
    """市场概览数据"""
    risk = _read_data("risk")
    limit_up = _read_data("limit_up")
    capital = _read_data("capital_flow")
    return jsonify({
        "limit_up": limit_up.get("count", risk.get("limit_up", 0)),
        "limit_down": limit_up.get("limit_down", risk.get("limit_down", 0)),
        "max_height": limit_up.get("max_height", risk.get("max_height", 0)),
        "up_count": risk.get("up_count", 0),
        "down_count": risk.get("down_count", 0),
        "up_down_ratio": risk.get("up_down_ratio", 0),
        "north_flow": capital.get("north_flow", 0),
        "alert_count": risk.get("alert_count", 0),
        "update_time": risk.get("time", ""),
    })


@app.route("/api/limit_up")
def api_limit_up():
    """涨停板数据"""
    return jsonify(_read_data("limit_up"))


@app.route("/api/capital_flow")
def api_capital_flow():
    """资金流向数据"""
    return jsonify(_read_data("capital_flow"))


@app.route("/api/dragon2")
def api_dragon2():
    """龙二选股数据"""
    return jsonify(_read_data("dragon2"))


@app.route("/api/risk")
def api_risk():
    """风险预警数据"""
    return jsonify(_read_data("risk"))


@app.route("/api/news")
def api_news():
    """新闻热点数据"""
    return jsonify(_read_data("news"))


@app.route("/api/watchlist")
def api_watchlist():
    """自选股数据"""
    return jsonify(_read_data("watchlist"))


@app.route("/api/daily_summary")
def api_daily_summary():
    """每日总结"""
    return jsonify(_read_data("daily_summary"))


@app.route("/api/stock/<code>")
def api_stock_detail(code):
    """单只股票详情：实时行情 + 技术分析"""
    from ..data.data_fetcher import DataFetcher
    from ..monitor.chip_analysis import ChipAnalysis
    result = {"code": code, "name": "", "price": 0, "change_pct": 0,
              "volume": 0, "amount": 0, "turnover": 0, "volume_ratio": 0,
              "technical": {}, "chip": {}}
    try:
        data_fetcher = DataFetcher(_config.get("data", {}))
        quote = data_fetcher.get_realtime_quote(code)
        result.update(quote)
        kline = data_fetcher.get_daily_kline(code, days=120)
        if kline is not None and not kline.empty:
            from ..monitor.chip_analysis import ChipAnalysis
            result["technical"] = {}
        chip = ChipAnalysis(_config.get("monitor", {}).get("chip", {}), data_fetcher)
        result["chip"] = chip.analyze(code) or {}
    except Exception as e:
        result["error"] = str(e)
    return jsonify(result)


@app.route("/api/recommendations")
def api_recommendations():
    """综合推荐买入：汇总六大维度信号，给出买入建议和理由"""
    limit_up = _read_data("limit_up")
    capital = _read_data("capital_flow")
    dragon2 = _read_data("dragon2")
    risk = _read_data("risk")
    news = _read_data("news")

    candidates = {}  # code -> {score, reasons, data}

    # 1. 龙二选股结果直接作为高优先级候选
    for s in (dragon2 if isinstance(dragon2, list) else []):
        code = s.get("code", "")
        if not code:
            continue
        score = s.get("score", 50)
        reasons = []
        if s.get("leader"):
            reasons.append(f"跟随龙头【{s['leader']}】，龙二补涨逻辑")
        if s.get("volume_ratio", 0) > 2:
            reasons.append(f"量比{s['volume_ratio']:.1f}，资金关注度高")
        if s.get("turnover", 0) and 3 < s["turnover"] < 15:
            reasons.append(f"换手率{s['turnover']:.1f}%，筹码活跃")
        if s.get("market_cap", 0) < 200e8:
            reasons.append(f"市值{ s['market_cap']/1e8:.0f}亿，小盘弹性大")
        candidates[code] = {
            "code": code, "name": s.get("name", ""), "price": s.get("price", 0),
            "score": score + 15, "reasons": reasons,
            "change_pct": s.get("change_pct", 0), "source": "龙二选股",
        }

    # 2. 资金流向TOP个股加分
    for s in (capital.get("main_inflow_stocks") or [])[:10]:
        code = s.get("code", "")
        if not code:
            continue
        inflow = s.get("inflow", 0)
        if code in candidates:
            candidates[code]["score"] += 12
            if inflow > 5e8:
                candidates[code]["reasons"].append(f"主力净流入{inflow/1e8:.1f}亿，大资金进场")
            elif inflow > 1e8:
                candidates[code]["reasons"].append(f"主力净流入{inflow/1e8:.1f}亿")
        else:
            score = 55
            reasons = []
            if inflow > 3e8:
                score += 10
                reasons.append(f"主力净流入{inflow/1e8:.1f}亿，资金强势")
            if s.get("change_pct", 0) > 3:
                reasons.append(f"当日涨{s['change_pct']:.1f}%，趋势向上")
            candidates[code] = {
                "code": code, "name": s.get("name", ""), "price": 0,
                "score": score, "reasons": reasons,
                "change_pct": s.get("change_pct", 0), "source": "资金流入",
            }

    # 3. 涨停板首板/二板股加分
    for s in (limit_up.get("leaders") or [])[:10]:
        code = s.get("code", "")
        if not code:
            continue
        boards = s.get("boards", 1)
        if code in candidates:
            candidates[code]["score"] += 8
            if boards == 1:
                candidates[code]["reasons"].append("今日首板突破，启动信号")
            elif boards == 2:
                candidates[code]["reasons"].append("二板确认，强势连板")
            elif boards >= 3:
                candidates[code]["reasons"].append(f"{boards}板高标，市场情绪龙头")
        else:
            if boards <= 3:  # 太高的不推荐追
                score = 50 + boards * 5
                reasons = [f"{boards}板涨停"]
                if s.get("industry"):
                    reasons.append(f"所属板块：{s['industry']}")
                candidates[code] = {
                    "code": code, "name": s.get("name", ""), "price": 0,
                    "score": score, "reasons": reasons,
                    "change_pct": 10, "source": "涨停板",
                }

    # 4. 匹配新闻热点
    for n in (news if isinstance(news, list) else [])[:15]:
        stock = n.get("stock", "")
        if stock and stock in candidates:
            candidates[stock]["score"] += 5
            candidates[stock]["reasons"].append(f"题材催化：{n.get('title', '')[:20]}")

    # 排序取TOP5
    result = sorted(candidates.values(), key=lambda x: x["score"], reverse=True)[:5]

    # 过滤掉分数太低的
    result = [r for r in result if r["score"] >= 60]

    # 生成操作建议
    for r in result:
        price = r.get("price", 0)
        if price > 0:
            r["buy_price"] = round(price * 0.995, 2)  # 回踩买入
            r["stop_loss"] = round(price * 0.95, 2)    # -5%止损
            r["target_1"] = round(price * 1.05, 2)     # +5%目标
            r["target_2"] = round(price * 1.10, 2)     # +10%目标
        else:
            r["buy_price"] = "竞价观察"
            r["stop_loss"] = "破前低止损"
            r["target_1"] = "+5%"
            r["target_2"] = "+10%"

    return jsonify({
        "date": limit_up.get("date", ""),
        "count": len(result),
        "stocks": result,
        "market_temp": {
            "limit_up": limit_up.get("count", 0),
            "limit_down": limit_up.get("limit_down", 0),
            "north_flow": capital.get("north_flow", 0),
        }
    })


@app.route("/api/all")
def api_all():
    """全部数据（一次性加载）"""
    return jsonify({
        "summary": _read_data("risk"),
        "limit_up": _read_data("limit_up"),
        "capital_flow": _read_data("capital_flow"),
        "dragon2": _read_data("dragon2"),
        "risk": _read_data("risk"),
        "news": _read_data("news"),
        "watchlist": _read_data("watchlist"),
        "recommendations": None,
    })


def run_web(config: dict):
    """运行Web服务"""
    init_app(config)
    web_cfg = config.get("web", {})
    host = web_cfg.get("host", "0.0.0.0")
    port = web_cfg.get("port", 8080)
    debug = web_cfg.get("debug", False)
    logger.info(f"Web Dashboard 启动: http://{host}:{port}")
    app.run(host=host, port=port, debug=debug, use_reloader=False)
