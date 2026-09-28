"""实时监控调度器 - 整合所有监控模块"""
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from ..data.data_fetcher import DataFetcher
from ..logger import get_logger
from ..monitor import (NewsMonitor, LimitUpMonitor, Dragon2Selector,
                       CapitalFlowMonitor, ChipAnalysis, RiskMonitor)
from ..notification.feishu_bot import FeishuBot

logger = get_logger("MonitorScheduler")


class MonitorScheduler:
    def __init__(self, config: dict):
        self.config = config
        self.data = DataFetcher(config.get("data", {}))
        self.feishu = FeishuBot(config.get("feishu", {}))

        # 初始化各监控模块
        monitor_cfg = config.get("monitor", {})
        self.news_monitor = NewsMonitor(monitor_cfg.get("news", {}), self.data)
        self.limit_up_monitor = LimitUpMonitor(monitor_cfg.get("limit_up", {}), self.data)
        self.dragon2_selector = Dragon2Selector(monitor_cfg.get("dragon2", {}), self.data)
        self.capital_flow_monitor = CapitalFlowMonitor(monitor_cfg.get("capital_flow", {}), self.data)
        self.chip_analysis = ChipAnalysis(monitor_cfg.get("chip", {}), self.data)
        self.risk_monitor = RiskMonitor(monitor_cfg.get("risk", {}), self.data)

        # 自选股
        self.watchlist = config.get("watchlist", {}).get("stocks", [])

        # 调度器
        self.scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
        self._running = False

        # 数据存储（供Web页面读取）
        self._data_dir = Path(config.get("system", {}).get("data_dir", "./data"))
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._latest_data = {}

    def start(self):
        """启动监控调度器"""
        if self._running:
            return
        logger.info("=" * 60)
        logger.info("短线选股监控系统启动")
        logger.info(f"飞书通知: {'开启' if self.feishu.enabled else '关闭'}")
        logger.info(f"自选股: {self.watchlist if self.watchlist else '无'}")
        logger.info("=" * 60)

        self._register_jobs()
        self.scheduler.start()
        self._running = True

        # 立即执行一次全量检查
        self._full_check()

        logger.info("监控调度器已启动，按 Ctrl+C 停止")
        try:
            while self._running:
                time.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            logger.info("收到停止信号...")
            self.stop()

    def stop(self):
        """停止"""
        if not self._running:
            return
        self._running = False
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
        logger.info("监控调度器已停止")

    def _register_jobs(self):
        """注册定时任务"""
        # 新闻监控：每5分钟
        self.scheduler.add_job(
            self._check_news,
            trigger=IntervalTrigger(minutes=5),
            id="news_monitor", name="新闻热点监控",
            next_run_time=datetime.now()
        )

        # 资金流向：每10分钟（交易时段）
        self.scheduler.add_job(
            self._check_capital_flow,
            trigger=CronTrigger(day_of_week="mon-fri", hour="9-11,13-14", minute="*/10"),
            id="capital_flow", name="资金流向监控"
        )

        # 风险监控：每15分钟
        self.scheduler.add_job(
            self._check_risk,
            trigger=CronTrigger(day_of_week="mon-fri", hour="9-14", minute="*/15"),
            id="risk_monitor", name="风险监控"
        )

        # 自选股监控：每5分钟
        self.scheduler.add_job(
            self._check_watchlist,
            trigger=CronTrigger(day_of_week="mon-fri", hour="9-14", minute="*/5"),
            id="watchlist", name="自选股监控"
        )

        # 涨停板复盘：15:10
        self.scheduler.add_job(
            self._check_limit_up,
            trigger=CronTrigger(day_of_week="mon-fri", hour=15, minute=10),
            id="limit_up", name="涨停板复盘"
        )

        # 龙二选股：15:30
        self.scheduler.add_job(
            self._run_dragon2,
            trigger=CronTrigger(day_of_week="mon-fri", hour=15, minute=30),
            id="dragon2", name="龙二选股"
        )

        # 每日总结：16:00
        self.scheduler.add_job(
            self._daily_summary,
            trigger=CronTrigger(day_of_week="mon-fri", hour=16, minute=0),
            id="daily_summary", name="每日总结"
        )

        logger.info("定时任务注册完成")

    # ===== 任务执行 =====

    def _check_news(self):
        """新闻监控"""
        try:
            alerts = self.news_monitor.check()
            if alerts:
                self.feishu.alert_news(alerts)
                self._latest_data["news"] = alerts
                self._save_data("news", alerts)
        except Exception as e:
            logger.error(f"新闻监控任务异常: {e}")

    def _check_capital_flow(self):
        """资金流向监控"""
        try:
            data = self.capital_flow_monitor.check()
            self._latest_data["capital_flow"] = data
            self._save_data("capital_flow", data)
            if self.capital_flow_monitor.has_alert(data):
                self.feishu.alert_capital(data)
        except Exception as e:
            logger.error(f"资金流向监控任务异常: {e}")

    def _check_risk(self):
        """风险监控"""
        try:
            alerts = self.risk_monitor.check()
            summary = self.risk_monitor.get_risk_summary()
            self._latest_data["risk"] = summary
            self._save_data("risk", summary)
            for alert in alerts:
                self.feishu.alert_risk(alert)
        except Exception as e:
            logger.error(f"风险监控任务异常: {e}")

    def _check_watchlist(self):
        """自选股监控"""
        if not self.watchlist:
            return
        try:
            alerts = self.risk_monitor.check_watchlist(self.watchlist)
            for alert in alerts:
                self.feishu.alert_watchlist(alert)
            if alerts:
                self._latest_data["watchlist"] = alerts
                self._save_data("watchlist", alerts)
        except Exception as e:
            logger.error(f"自选股监控任务异常: {e}")

    def _check_limit_up(self):
        """涨停板复盘"""
        try:
            data = self.limit_up_monitor.analyze()
            self._latest_data["limit_up"] = data
            self._save_data("limit_up", data)
            self.feishu.alert_limit_up(data)
        except Exception as e:
            logger.error(f"涨停板复盘异常: {e}")

    def _run_dragon2(self):
        """龙二选股"""
        try:
            # 先获取龙头
            limit_up_data = self._latest_data.get("limit_up", {})
            leaders = limit_up_data.get("leaders", [])
            if not leaders:
                data = self.limit_up_monitor.analyze()
                leaders = data.get("leaders", [])

            candidates = self.dragon2_selector.select(leaders)
            self._latest_data["dragon2"] = candidates
            self._save_data("dragon2", candidates)
            if candidates:
                self.feishu.alert_dragon2(candidates)
        except Exception as e:
            logger.error(f"龙二选股异常: {e}")

    def _daily_summary(self):
        """每日总结"""
        try:
            summary = {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "limit_up": self._latest_data.get("limit_up", {}).get("count", 0),
                "limit_down": self._latest_data.get("limit_up", {}).get("limit_down", 0),
                "max_height": self._latest_data.get("limit_up", {}).get("max_height", 0),
                "up_down_ratio": self._latest_data.get("risk", {}).get("up_down_ratio", 0),
                "north_flow": self._latest_data.get("capital_flow", {}).get("north_flow", 0),
                "top_inflow_sector": "",
                "hot_topics": "",
                "dragon2_count": len(self._latest_data.get("dragon2", [])),
            }
            # 热门板块
            sectors = self._latest_data.get("capital_flow", {}).get("hot_sectors", [])
            if sectors:
                summary["top_inflow_sector"] = sectors[0].get("name", "")
                summary["hot_topics"] = "、".join([s["name"] for s in sectors[:3]])

            self._save_data("daily_summary", summary)
            self.feishu.daily_summary(summary)
            logger.info("每日总结已发送")
        except Exception as e:
            logger.error(f"每日总结异常: {e}")

    def _full_check(self):
        """全量检查（启动时执行）"""
        logger.info("执行启动全量检查...")
        self._check_risk()
        self._check_capital_flow()
        if self.watchlist:
            self._check_watchlist()

    def _save_data(self, name: str, data):
        """保存数据供Web读取"""
        try:
            file_path = self._data_dir / f"{name}.json"
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.debug(f"保存数据失败 {name}: {e}")

    def get_latest_data(self) -> Dict:
        """获取最新数据（供Web API）"""
        return self._latest_data
