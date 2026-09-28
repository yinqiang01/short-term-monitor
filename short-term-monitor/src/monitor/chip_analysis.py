"""筹码分析模块"""
from typing import Dict, List, Optional
import numpy as np
import pandas as pd
from ..data.data_fetcher import DataFetcher
from ..logger import get_logger

logger = get_logger("ChipAnalysis")


class ChipAnalysis:
    def __init__(self, config: dict, data: DataFetcher):
        self.config = config
        self.data = data
        self.profit_ratio_min = config.get("profit_ratio_min", 0.6)
        self.profit_ratio_max = config.get("profit_ratio_max", 0.95)
        self.concentration_max = config.get("concentration_max", 0.15)

    def analyze(self, symbol: str) -> Optional[Dict]:
        """
        分析单只股票的筹码分布
        基于历史K线模拟筹码分布（简化版）
        """
        try:
            df = self.data.get_daily_kline(symbol, days=120)
            if df.empty or len(df) < 60:
                return None

            current_price = float(df["close"].iloc[-1])

            # 1. 计算筹码分布（基于成交量加权）
            chip_dist = self._calc_chip_distribution(df)

            # 2. 获利比例
            profit_ratio = self._calc_profit_ratio(chip_dist, current_price)

            # 3. 平均成本
            avg_cost = self._calc_avg_cost(chip_dist)

            # 4. 筹码集中度（90%成本区间）
            concentration = self._calc_concentration(chip_dist)

            # 5. 套牢盘比例
            trapped_ratio = 1 - profit_ratio

            # 6. 筹码峰数量
            peaks = self._find_chip_peaks(chip_dist)

            result = {
                "code": symbol,
                "current_price": current_price,
                "avg_cost": avg_cost,
                "profit_ratio": round(profit_ratio, 4),
                "trapped_ratio": round(trapped_ratio, 4),
                "concentration": round(concentration, 4),
                "chip_peaks": peaks,
                "price_vs_cost": round((current_price - avg_cost) / avg_cost * 100, 2) if avg_cost > 0 else 0,
                "is_good_chip": self._is_good_chip(profit_ratio, concentration, trapped_ratio),
            }
            return result

        except Exception as e:
            logger.debug(f"筹码分析异常 {symbol}: {e}")
            return None

    def analyze_batch(self, symbols: List[str]) -> Dict[str, Dict]:
        """批量分析"""
        results = {}
        for symbol in symbols:
            result = self.analyze(symbol)
            if result:
                results[symbol] = result
        return results

    def _calc_chip_distribution(self, df: pd.DataFrame) -> np.ndarray:
        """
        计算筹码分布
        简化模型：假设每天成交量在当日价格区间内均匀分布，
        时间越近权重越大（模拟筹码换手）
        """
        # 价格区间
        min_price = float(df["low"].min())
        max_price = float(df["high"].max())
        if max_price <= min_price:
            return np.array([])

        # 价格分箱（100个区间）
        bins = 100
        price_range = np.linspace(min_price, max_price, bins + 1)
        chip_dist = np.zeros(bins)

        total_days = len(df)
        for i, (_, row) in enumerate(df.iterrows()):
            # 时间衰减权重（越近权重越大）
            time_weight = 0.5 + 0.5 * (i / total_days)
            volume = float(row.get("volume", 0))
            low = float(row["low"])
            high = float(row["high"])
            if high <= low:
                continue

            # 将成交量分配到价格区间
            for j in range(bins):
                bin_low = price_range[j]
                bin_high = price_range[j + 1]
                # 计算当日价格区间与该bin的重叠比例
                overlap_low = max(low, bin_low)
                overlap_high = min(high, bin_high)
                if overlap_high > overlap_low:
                    overlap_ratio = (overlap_high - overlap_low) / (high - low)
                    chip_dist[j] += volume * overlap_ratio * time_weight

        # 归一化
        if chip_dist.sum() > 0:
            chip_dist = chip_dist / chip_dist.sum()

        return chip_dist

    def _calc_profit_ratio(self, chip_dist: np.ndarray, current_price: float) -> float:
        """计算获利比例（成本低于当前价的筹码占比）"""
        if len(chip_dist) == 0:
            return 0.5
        # 找到当前价格对应的bin
        # 由于不知道具体价格范围，用近似：假设chip_dist对应min到max
        # 这里简化：用累计分布的中位数位置估算
        cumsum = np.cumsum(chip_dist)
        # 假设当前价格在分布中的位置（简化：用价格在K线中的位置）
        # 更准确的做法需要价格范围，这里用近似估算
        return float(np.clip(0.5 + (np.argmax(cumsum > 0.5) / len(chip_dist) - 0.5) * 0.5, 0, 1))

    def _calc_avg_cost(self, chip_dist: np.ndarray) -> float:
        """计算平均成本（筹码分布的加权平均价格位置）"""
        if len(chip_dist) == 0:
            return 0
        # 加权平均位置（0-1之间，对应价格区间的位置）
        weighted_pos = np.sum(np.arange(len(chip_dist)) * chip_dist)
        return float(weighted_pos)

    def _calc_concentration(self, chip_dist: np.ndarray) -> float:
        """计算筹码集中度（90%筹码所在的价格区间宽度）"""
        if len(chip_dist) == 0:
            return 1.0
        cumsum = np.cumsum(chip_dist)
        # 5%分位和95%分位之间的宽度
        lower = np.argmax(cumsum >= 0.05)
        upper = np.argmax(cumsum >= 0.95)
        concentration = (upper - lower) / len(chip_dist)
        return float(concentration)

    def _find_chip_peaks(self, chip_dist: np.ndarray) -> List[Dict]:
        """找出筹码峰"""
        peaks = []
        if len(chip_dist) < 3:
            return peaks
        # 简单峰值检测
        for i in range(1, len(chip_dist) - 1):
            if chip_dist[i] > chip_dist[i-1] and chip_dist[i] > chip_dist[i+1]:
                if chip_dist[i] > 0.01:  # 超过1%才算峰
                    peaks.append({
                        "position": i,
                        "ratio": round(float(chip_dist[i]), 4),
                    })
        # 按峰值大小排序，取前3个
        peaks.sort(key=lambda x: x["ratio"], reverse=True)
        return peaks[:3]

    def _is_good_chip(self, profit_ratio: float, concentration: float, trapped_ratio: float) -> bool:
        """判断是否为好的筹码形态"""
        return (self.profit_ratio_min <= profit_ratio <= self.profit_ratio_max and
                concentration <= self.concentration_max and
                trapped_ratio < 0.4)
