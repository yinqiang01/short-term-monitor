"""涨停板监控模块"""
from datetime import datetime
from typing import Dict, List
import pandas as pd
from ..data.data_fetcher import DataFetcher
from ..logger import get_logger

logger = get_logger("LimitUpMonitor")


class LimitUpMonitor:
    def __init__(self, config: dict, data: DataFetcher):
        self.config = config
        self.data = data
        self.min_seal_amount = config.get("min_seal_amount", 50000000)

    def analyze(self) -> Dict:
        """分析涨停板，返回结构化数据"""
        result = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "count": 0,
            "limit_down": 0,
            "max_height": 0,
            "leaders": [],
            "seal_quality": {},
            "board_distribution": {},
        }
        try:
            # 涨停板
            df = self.data.get_limit_up_list()
            if not df.empty:
                result["count"] = len(df)
                # 连板分布
                if "连板数" in df.columns:
                    result["max_height"] = int(df["连板数"].max())
                    board_dist = df["连板数"].value_counts().sort_index()
                    result["board_distribution"] = {int(k): int(v) for k, v in board_dist.items()}

                # 龙头股（连板最高 + 封单最大）
                leaders = self._find_leaders(df)
                result["leaders"] = leaders

                # 封板质量统计
                result["seal_quality"] = self._analyze_seal_quality(df)

                logger.info(f"涨停板分析: {result['count']}家涨停, 最高{result['max_height']}板")

            # 跌停板
            df_down = self.data.get_limit_down_list()
            if not df_down.empty:
                result["limit_down"] = len(df_down)

        except Exception as e:
            logger.error(f"涨停板分析异常: {e}")

        return result

    def _find_leaders(self, df: pd.DataFrame) -> List[Dict]:
        """找出龙头股"""
        leaders = []
        try:
            # 按连板数降序，封单金额降序
            sort_cols = []
            if "连板数" in df.columns:
                sort_cols.append("连板数")
            if "封单金额" in df.columns:
                sort_cols.append("封单金额")
            elif "封单资金" in df.columns:
                sort_cols.append("封单资金")

            if sort_cols:
                df_sorted = df.sort_values(sort_cols, ascending=False)
            else:
                df_sorted = df

            for _, row in df_sorted.head(10).iterrows():
                code = str(row.get("代码", ""))
                name = str(row.get("名称", ""))
                boards = int(row.get("连板数", 1)) if "连板数" in df.columns else 1
                seal = float(row.get("封单金额", row.get("封单资金", 0)))
                leaders.append({
                    "code": code,
                    "name": name,
                    "boards": boards,
                    "seal": round(seal / 10000, 0),  # 转万元
                    "change_pct": float(row.get("涨跌幅", 10)),
                    "turnover": float(row.get("换手率", 0)),
                    "industry": str(row.get("所属行业", "")),
                })
        except Exception as e:
            logger.debug(f"找龙头异常: {e}")
        return leaders

    def _analyze_seal_quality(self, df: pd.DataFrame) -> Dict:
        """分析封板质量"""
        quality = {"strong": 0, "medium": 0, "weak": 0}
        try:
            seal_col = "封单金额" if "封单金额" in df.columns else "封单资金"
            if seal_col in df.columns:
                for _, row in df.iterrows():
                    seal = float(row.get(seal_col, 0))
                    amount = float(row.get("成交额", 1))
                    ratio = seal / amount if amount > 0 else 0
                    if ratio > 0.5 or seal > self.min_seal_amount * 2:
                        quality["strong"] += 1
                    elif ratio > 0.1 or seal > self.min_seal_amount:
                        quality["medium"] += 1
                    else:
                        quality["weak"] += 1
        except Exception as e:
            logger.debug(f"封板质量分析异常: {e}")
        return quality

    def get_board_stocks(self, board_height: int) -> List[Dict]:
        """获取指定连板数的股票"""
        stocks = []
        try:
            df = self.data.get_limit_up_list()
            if not df.empty and "连板数" in df.columns:
                filtered = df[df["连板数"] == board_height]
                for _, row in filtered.iterrows():
                    stocks.append({
                        "code": str(row.get("代码", "")),
                        "name": str(row.get("名称", "")),
                        "boards": int(row.get("连板数", 1)),
                    })
        except Exception as e:
            logger.debug(f"获取连板股异常: {e}")
        return stocks
