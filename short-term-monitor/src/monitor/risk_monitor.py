"""风险监控模块"""
from datetime import datetime
from typing import Dict, List, Optional
from ..data.data_fetcher import DataFetcher
from ..logger import get_logger

logger = get_logger("RiskMonitor")


class RiskMonitor:
    def __init__(self, config: dict, data: DataFetcher):
        self.config = config
        self.data = data
        self.market_emotion_threshold = config.get("market_emotion_threshold", 80)
        self.limit_down_threshold = config.get("limit_down_threshold", 20)
        self.stop_loss_pct = config.get("stop_loss_pct", 0.07)
        self._alerts = []

    def check(self) -> List[Dict]:
        """全面风险检查，返回告警列表"""
        self._alerts = []
        try:
            # 1. 市场情绪风险
            self._check_market_emotion()
            # 2. 涨跌停风险
            self._check_limit_up_down()
            # 3. 北向资金风险
            self._check_north_flow()
            # 4. 连板高度风险
            self._check_board_height()
        except Exception as e:
            logger.error(f"风险监控异常: {e}")
        return self._alerts

    def _check_market_emotion(self):
        """市场情绪检查"""
        try:
            emotion = self.data.get_market_emotion()
            limit_up = emotion.get("limit_up_count", 0)
            limit_down = emotion.get("limit_down_count", 0)

            # 过热风险
            if limit_up > self.market_emotion_threshold:
                self._alerts.append({
                    "level": "warning",
                    "type": "market_overheat",
                    "title": "市场过热预警",
                    "message": f"涨停家数达 {limit_up} 家，超过阈值 {self.market_emotion_threshold} 家，市场情绪过热，注意追高风险。",
                })
            # 恐慌风险
            if limit_down > self.limit_down_threshold:
                self._alerts.append({
                    "level": "danger",
                    "type": "market_panic",
                    "title": "市场恐慌预警",
                    "message": f"跌停家数达 {limit_down} 家，超过阈值 {self.limit_down_threshold} 家，市场恐慌情绪蔓延，建议降低仓位。",
                })
        except Exception as e:
            logger.debug(f"市场情绪检查异常: {e}")

    def _check_limit_up_down(self):
        """涨跌停比检查"""
        try:
            emotion = self.data.get_market_emotion()
            up = emotion.get("limit_up_count", 0)
            down = emotion.get("limit_down_count", 0)
            if down > 0 and up / down < 1.5:
                self._alerts.append({
                    "level": "warning",
                    "type": "weak_market",
                    "title": "市场偏弱预警",
                    "message": f"涨跌停比 {up}:{down}，多头力量不足，市场偏弱，谨慎操作。",
                })
        except Exception as e:
            logger.debug(f"涨跌停比检查异常: {e}")

    def _check_north_flow(self):
        """北向资金检查"""
        try:
            north = self.data.get_north_flow()
            if north:
                flow = north.get("net_inflow", 0)
                if flow < -3000000000:  # 净流出超30亿
                    self._alerts.append({
                        "level": "warning",
                        "type": "north_outflow",
                        "title": "北向资金大幅流出",
                        "message": f"北向资金净流出 {flow/1e8:.2f} 亿，外资看空，注意风险。",
                    })
        except Exception as e:
            logger.debug(f"北向资金检查异常: {e}")

    def _check_board_height(self):
        """连板高度检查"""
        try:
            emotion = self.data.get_market_emotion()
            max_height = emotion.get("max_board_height", 0)
            if max_height >= 7:
                self._alerts.append({
                    "level": "warning",
                    "type": "high_board_risk",
                    "title": "高位板风险预警",
                    "message": f"最高连板达 {max_height} 板，处于高位，龙头股随时可能断板，避免追高。",
                })
        except Exception as e:
            logger.debug(f"连板高度检查异常: {e}")

    def check_watchlist(self, watchlist: List[str]) -> List[Dict]:
        """检查自选股异动"""
        alerts = []
        alert_change = self.config.get("alert_change_pct", 5.0)
        alert_volume = self.config.get("alert_volume_ratio", 2.0)

        for code in watchlist:
            try:
                info = self.data.get_realtime_quote(code)
                if not info:
                    continue
                change_pct = info.get("change_pct", 0)
                volume_ratio = info.get("volume_ratio", 0)

                reasons = []
                if abs(change_pct) >= alert_change:
                    reasons.append(f"涨跌幅 {change_pct:+.2f}% 超阈值 ±{alert_change}%")
                if volume_ratio >= alert_volume:
                    reasons.append(f"量比 {volume_ratio:.2f} 超阈值 {alert_volume}")

                if reasons:
                    info["reason"] = "; ".join(reasons)
                    alerts.append(info)
            except Exception as e:
                logger.debug(f"自选股检查异常 {code}: {e}")

        return alerts

    def get_risk_summary(self) -> Dict:
        """获取风险总结"""
        emotion = self.data.get_market_emotion()
        return {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "limit_up": emotion.get("limit_up_count", 0),
            "limit_down": emotion.get("limit_down_count", 0),
            "max_height": emotion.get("max_board_height", 0),
            "up_count": emotion.get("up_count", 0),
            "down_count": emotion.get("down_count", 0),
            "up_down_ratio": emotion.get("up_down_ratio", 0),
            "alert_count": len(self._alerts),
            "alerts": self._alerts,
        }
