"""飞书机器人通知模块"""
import hashlib
import hmac
import base64
import time
import json
from datetime import datetime
from typing import List, Optional
import requests
from ..logger import get_logger

logger = get_logger("FeishuBot")


class FeishuBot:
    """飞书自定义机器人"""

    def __init__(self, config: dict):
        self.config = config
        self.enabled = config.get("enabled", False)
        self.webhook_url = config.get("webhook_url", "")
        self.secret = config.get("secret", "")
        self.notify_on = set(config.get("notify_on", []))
        self._last_notify_time = {}  # 防重复发送

    def _gen_sign(self, timestamp: str) -> str:
        """生成签名"""
        string_to_sign = f"{timestamp}\n{self.secret}"
        hmac_code = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
        return base64.b64encode(hmac_code).decode("utf-8")

    def _should_notify(self, alert_type: str) -> bool:
        """判断是否应该发送该类型通知"""
        if not self.enabled:
            return False
        if not self.webhook_url:
            return False
        if alert_type not in self.notify_on:
            return False
        # 防重复：同一类型1分钟内只发一次
        now = time.time()
        last = self._last_notify_time.get(alert_type, 0)
        if now - last < 60:
            return False
        self._last_notify_time[alert_type] = now
        return True

    def send_text(self, content: str, alert_type: str = "general") -> bool:
        """发送纯文本消息"""
        if not self._should_notify(alert_type):
            return False
        try:
            payload = {"msg_type": "text", "content": {"text": content}}
            if self.secret:
                timestamp = str(int(time.time()))
                payload["timestamp"] = timestamp
                payload["sign"] = self._gen_sign(timestamp)
            resp = requests.post(self.webhook_url, json=payload, timeout=10)
            result = resp.json()
            if result.get("code") == 0 or result.get("StatusCode") == 0:
                logger.info(f"飞书通知发送成功: {alert_type}")
                return True
            else:
                logger.warning(f"飞书通知发送失败: {result}")
                return False
        except Exception as e:
            logger.error(f"飞书通知异常: {e}")
            return False

    def send_rich_text(self, title: str, content_lines: List[dict], alert_type: str = "general") -> bool:
        """发送富文本消息（post格式）"""
        if not self._should_notify(alert_type):
            return False
        try:
            content = []
            for line in content_lines:
                tag = line.get("tag", "text")
                if tag == "a":
                    content.append([{"tag": "a", "text": line.get("text", ""), "href": line.get("href", "")}])
                elif tag == "at":
                    content.append([{"tag": "at", "user_id": line.get("user_id", "all")}])
                else:
                    content.append([{"tag": "text", "text": line.get("text", "")}])

            payload = {
                "msg_type": "post",
                "content": {
                    "post": {
                        "zh_cn": {
                            "title": title,
                            "content": content
                        }
                    }
                }
            }
            if self.secret:
                timestamp = str(int(time.time()))
                payload["timestamp"] = timestamp
                payload["sign"] = self._gen_sign(timestamp)

            resp = requests.post(self.webhook_url, json=payload, timeout=10)
            result = resp.json()
            if result.get("code") == 0 or result.get("StatusCode") == 0:
                logger.info(f"飞书富文本通知成功: {title}")
                return True
            else:
                logger.warning(f"飞书富文本通知失败: {result}")
                return False
        except Exception as e:
            logger.error(f"飞书富文本通知异常: {e}")
            return False

    def send_interactive_card(self, title: str, elements: List[dict],
                               header_color: str = "red", alert_type: str = "general") -> bool:
        """发送交互卡片消息"""
        if not self._should_notify(alert_type):
            return False
        try:
            payload = {
                "msg_type": "interactive",
                "card": {
                    "header": {
                        "title": {"tag": "plain_text", "content": title},
                        "template": header_color
                    },
                    "elements": elements
                }
            }
            if self.secret:
                timestamp = str(int(time.time()))
                payload["timestamp"] = timestamp
                payload["sign"] = self._gen_sign(timestamp)

            resp = requests.post(self.webhook_url, json=payload, timeout=10)
            result = resp.json()
            if result.get("code") == 0 or result.get("StatusCode") == 0:
                logger.info(f"飞书卡片通知成功: {title}")
                return True
            else:
                logger.warning(f"飞书卡片通知失败: {result}")
                return False
        except Exception as e:
            logger.error(f"飞书卡片通知异常: {e}")
            return False

    # ===== 快捷通知方法 =====

    def alert_news(self, news_list: List[dict]):
        """新闻异动告警"""
        if not news_list:
            return
        lines = [f"📰 【新闻热点异动】{datetime.now().strftime('%H:%M')}\n"]
        for i, news in enumerate(news_list[:5], 1):
            lines.append(f"{i}. {news.get('title', '')[:50]}")
            if news.get("stock"):
                lines.append(f"   相关: {news['stock']}")
            lines.append("")
        self.send_text("\n".join(lines), "news_alert")

    def alert_limit_up(self, limit_up_data: dict):
        """涨停板异动告警"""
        title = f"🚀 【涨停板复盘】{datetime.now().strftime('%m-%d')}"
        elements = [
            {"tag": "div", "text": {"tag": "lark_md",
             "content": f"**涨停家数**: {limit_up_data.get('count', 0)} 家\n"
                        f"**连板高度**: {limit_up_data.get('max_height', 0)} 板\n"
                        f"**跌停家数**: {limit_up_data.get('limit_down', 0)} 家"}},
            {"tag": "hr"},
        ]
        # 龙头股
        leaders = limit_up_data.get("leaders", [])
        if leaders:
            leader_text = "**🔥 龙头股**\n"
            for s in leaders[:5]:
                leader_text += f"- {s.get('name','')}({s.get('code','')}) {s.get('boards','')}板 封单{s.get('seal','')}万\n"
            elements.append({"tag": "div", "text": {"tag": "lark_md", "content": leader_text}})
        self.send_interactive_card(title, elements, "red", "limit_up_alert")

    def alert_dragon2(self, dragon2_list: List[dict]):
        """龙二选股结果告警"""
        title = f"🐉 【龙二选股】{datetime.now().strftime('%m-%d')}"
        elements = [{"tag": "div", "text": {"tag": "lark_md",
                     "content": f"共筛选出 **{len(dragon2_list)}** 只龙二候选股"}}]
        if dragon2_list:
            text = "**候选标的**\n"
            for i, s in enumerate(dragon2_list[:10], 1):
                text += (f"{i}. {s.get('name','')}({s.get('code','')}) "
                         f"涨幅{s.get('change_pct',0):.1f}% "
                         f"市值{s.get('market_cap',0)/1e8:.0f}亿 "
                         f"主力净流入{s.get('main_inflow',0)/1e4:.0f}万\n")
            elements.append({"tag": "hr"})
            elements.append({"tag": "div", "text": {"tag": "lark_md", "content": text}})
        elements.append({"tag": "note", "elements": [{"tag": "plain_text",
                         "content": "⚠️ 仅供参考，不构成投资建议"}]})
        self.send_interactive_card(title, elements, "orange", "dragon2_alert")

    def alert_capital(self, capital_data: dict):
        """资金异动告警"""
        lines = [f"💰 【资金异动】{datetime.now().strftime('%H:%M')}\n"]
        if capital_data.get("main_inflow_stocks"):
            lines.append("📈 主力净流入TOP5:")
            for s in capital_data["main_inflow_stocks"][:5]:
                lines.append(f"  {s.get('name','')}({s.get('code','')}): {s.get('inflow',0)/1e4:.0f}万")
        if capital_data.get("north_flow"):
            lines.append(f"\n🌐 北向资金: {capital_data['north_flow']/1e8:.2f}亿")
        self.send_text("\n".join(lines), "capital_alert")

    def alert_risk(self, risk_data: dict):
        """风险预警"""
        title = "⚠️ 【风险预警】"
        elements = [{"tag": "div", "text": {"tag": "lark_md",
                     "content": risk_data.get("message", "")}}]
        color = "red" if risk_data.get("level", "warning") == "danger" else "orange"
        self.send_interactive_card(title, elements, color, "risk_alert")

    def alert_watchlist(self, stock_info: dict):
        """自选股异动告警"""
        lines = [f"👀 【自选股异动】{datetime.now().strftime('%H:%M')}\n"]
        lines.append(f"{stock_info.get('name','')}({stock_info.get('code','')})")
        lines.append(f"当前价: {stock_info.get('price',0):.2f}")
        lines.append(f"涨跌幅: {stock_info.get('change_pct',0):.2f}%")
        if stock_info.get("volume_ratio", 0) > 0:
            lines.append(f"量比: {stock_info.get('volume_ratio',0):.2f}")
        lines.append(f"\n异动原因: {stock_info.get('reason','')}")
        self.send_text("\n".join(lines), "watchlist_alert")

    def daily_summary(self, summary: dict):
        """每日总结"""
        title = f"📊 【每日复盘】{datetime.now().strftime('%Y-%m-%d')}"
        elements = [
            {"tag": "div", "text": {"tag": "lark_md",
             "content": f"**市场情绪**\n"
                        f"涨停: {summary.get('limit_up',0)}家 | 跌停: {summary.get('limit_down',0)}家\n"
                        f"连板高度: {summary.get('max_height',0)}板 | 涨跌比: {summary.get('up_down_ratio',0)}\n\n"
                        f"**资金面**\n"
                        f"北向资金: {summary.get('north_flow',0)/1e8:.2f}亿\n"
                        f"主力净流入TOP: {summary.get('top_inflow_sector','')}\n\n"
                        f"**热点题材**\n"
                        f"{summary.get('hot_topics','无')}"}},
            {"tag": "hr"},
            {"tag": "note", "elements": [{"tag": "plain_text",
             "content": "短线监控系统自动生成 | 仅供参考，不构成投资建议"}]},
        ]
        self.send_interactive_card(title, elements, "blue", "daily_summary")
