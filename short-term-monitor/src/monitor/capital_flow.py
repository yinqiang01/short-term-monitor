"""资金流向监控模块"""
from datetime import datetime
from typing import Dict, List
import pandas as pd
from ..data.data_fetcher import DataFetcher
from ..logger import get_logger

logger = get_logger("CapitalFlowMonitor")


class CapitalFlowMonitor:
    def __init__(self, config: dict, data: DataFetcher):
        self.config = config
        self.data = data
        self.main_inflow_threshold = config.get("main_inflow_threshold", 50000000)
        self.big_order_ratio_threshold = config.get("big_order_ratio_threshold", 0.3)

    def check(self) -> Dict:
        """检查资金流向异动"""
        result = {
            "time": datetime.now().strftime("%H:%M"),
            "main_inflow_stocks": [],
            "main_outflow_stocks": [],
            "hot_sectors": [],
            "north_flow": 0,
            "lhb_stocks": [],
        }
        try:
            # 1. 个股主力资金流向
            df = self.data.get_main_capital_flow()
            if not df.empty:
                # 主力净流入TOP
                inflow_col = "主力净流入-净额" if "主力净流入-净额" in df.columns else "主力净流入"
                if inflow_col in df.columns:
                    df_sorted = df.sort_values(inflow_col, ascending=False)
                    for _, row in df_sorted.head(10).iterrows():
                        inflow = float(row.get(inflow_col, 0))
                        if inflow > self.main_inflow_threshold:
                            result["main_inflow_stocks"].append({
                                "code": str(row.get("代码", "")),
                                "name": str(row.get("名称", "")),
                                "inflow": inflow,
                                "change_pct": float(row.get("涨跌幅", 0)),
                            })
                    # 主力净流出TOP
                    for _, row in df_sorted.tail(5).iterrows():
                        outflow = float(row.get(inflow_col, 0))
                        if outflow < -self.main_inflow_threshold:
                            result["main_outflow_stocks"].append({
                                "code": str(row.get("代码", "")),
                                "name": str(row.get("名称", "")),
                                "outflow": outflow,
                                "change_pct": float(row.get("涨跌幅", 0)),
                            })

            # 2. 板块资金流向
            sector_df = self.data.get_sector_capital_flow()
            if not sector_df.empty:
                inflow_col = "净流入-净额" if "净流入-净额" in sector_df.columns else "主力净流入"
                if inflow_col in sector_df.columns:
                    sector_sorted = sector_df.sort_values(inflow_col, ascending=False)
                    for _, row in sector_sorted.head(5).iterrows():
                        result["hot_sectors"].append({
                            "name": str(row.get("名称", row.get("板块", ""))),
                            "inflow": float(row.get(inflow_col, 0)),
                            "change_pct": float(row.get("涨跌幅", 0)),
                        })

            # 3. 北向资金
            north = self.data.get_north_flow()
            if north:
                result["north_flow"] = north.get("net_inflow", 0)

            # 4. 龙虎榜
            lhb = self.data.get_lhb_list()
            if not lhb.empty:
                for _, row in lhb.head(10).iterrows():
                    result["lhb_stocks"].append({
                        "code": str(row.get("代码", "")),
                        "name": str(row.get("名称", "")),
                        "reason": str(row.get("上榜原因", "")),
                        "net_buy": float(row.get("净买入", row.get("净额", 0))),
                    })

            logger.info(f"资金流向检查完成: 净流入{len(result['main_inflow_stocks'])}只, "
                       f"热门板块{len(result['hot_sectors'])}个, 北向{result['north_flow']/1e8:.2f}亿")

        except Exception as e:
            logger.error(f"资金流向监控异常: {e}")

        return result

    def has_alert(self, data: Dict) -> bool:
        """判断是否有需要告警的异动"""
        # 主力净流入超阈值的股票超过3只
        if len(data.get("main_inflow_stocks", [])) >= 3:
            return True
        # 北向资金大幅流入（超5亿）
        if abs(data.get("north_flow", 0)) > 500000000:
            return True
        # 有龙虎榜
        if len(data.get("lhb_stocks", [])) > 0:
            return True
        return False
