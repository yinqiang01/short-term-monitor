"""龙二选股模块"""
from datetime import datetime
from typing import Dict, List
import pandas as pd
from ..data.data_fetcher import DataFetcher
from ..logger import get_logger

logger = get_logger("Dragon2Selector")


class Dragon2Selector:
    def __init__(self, config: dict, data: DataFetcher):
        self.config = config
        self.data = data
        self.max_market_cap = config.get("max_market_cap", 10000000000)
        self.max_gain_ratio = config.get("max_gain_ratio", 0.5)
        self.min_volume_ratio = config.get("min_volume_ratio", 1.2)

    def select(self, leaders: List[Dict]) -> List[Dict]:
        """
        根据龙头股选出龙二候选
        leaders: 龙头股列表，来自涨停板监控
        """
        candidates = []
        if not leaders:
            logger.info("无龙头股，跳过龙二选股")
            return candidates

        try:
            # 获取全市场行情
            quotes = self.data.get_all_realtime_quotes()
            if quotes.empty:
                return candidates

            # 对每个龙头，找同题材/同行业的低位股
            for leader in leaders[:3]:  # 只看前3个龙头
                leader_code = leader.get("code", "")
                leader_name = leader.get("name", "")
                leader_gain = leader.get("change_pct", 10)
                leader_industry = leader.get("industry", "")

                logger.info(f"为龙头 {leader_name}({leader_code}) 寻找龙二...")

                # 方法1：同行业筛选
                if leader_industry and "所属行业" in quotes.columns:
                    industry_stocks = quotes[quotes["所属行业"] == leader_industry]
                else:
                    industry_stocks = quotes

                # 筛选条件
                for _, row in industry_stocks.iterrows():
                    code = str(row.get("代码", ""))
                    name = str(row.get("名称", ""))

                    # 排除龙头自己
                    if code == leader_code:
                        continue
                    # 排除ST
                    if "ST" in name.upper():
                        continue
                    # 排除已经涨停的（龙二应该还没涨停或刚启动）
                    change_pct = float(row.get("涨跌幅", 0))
                    if change_pct >= 9.9:
                        continue
                    # 涨幅小于龙头的50%
                    if change_pct > leader_gain * self.max_gain_ratio:
                        continue
                    # 市值限制
                    market_cap = float(row.get("总市值", 0))
                    if market_cap > self.max_market_cap or market_cap < 1000000000:
                        continue
                    # 量比
                    volume_ratio = float(row.get("量比", 0))
                    if volume_ratio < self.min_volume_ratio:
                        continue
                    # 换手率适中
                    turnover = float(row.get("换手率", 0))
                    if turnover < 1 or turnover > 25:
                        continue

                    # 去重
                    if any(c["code"] == code for c in candidates):
                        continue

                    candidates.append({
                        "code": code,
                        "name": name,
                        "leader": leader_name,
                        "industry": leader_industry,
                        "price": float(row.get("最新价", 0)),
                        "change_pct": change_pct,
                        "market_cap": market_cap,
                        "volume_ratio": volume_ratio,
                        "turnover": turnover,
                        "main_inflow": float(row.get("主力净流入", 0)),
                        "score": self._calc_score(change_pct, volume_ratio, market_cap, turnover),
                    })

            # 按评分排序
            candidates.sort(key=lambda x: x["score"], reverse=True)
            logger.info(f"龙二选股完成，共 {len(candidates)} 只候选")

        except Exception as e:
            logger.error(f"龙二选股异常: {e}")

        return candidates[:20]  # 最多返回20只

    def _calc_score(self, change_pct: float, volume_ratio: float,
                     market_cap: float, turnover: float) -> float:
        """计算龙二评分"""
        score = 50.0
        # 涨幅适中（3%-7%最好，太高追高，太低没启动）
        if 3 <= change_pct <= 7:
            score += 20
        elif 1 <= change_pct < 3:
            score += 10
        elif change_pct < 0:
            score -= 10
        # 量比越高越好
        score += min(volume_ratio * 5, 20)
        # 市值越小弹性越大
        if market_cap < 3000000000:
            score += 15
        elif market_cap < 5000000000:
            score += 10
        # 换手率适中
        if 3 <= turnover <= 10:
            score += 10
        return round(score, 1)
