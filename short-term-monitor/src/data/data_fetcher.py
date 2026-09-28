"""数据获取模块 - 基于akshare"""
import time
from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd
from ..logger import get_logger

logger = get_logger("DataFetcher")


class DataFetcher:
    def __init__(self, config: dict):
        self.config = config
        self._ak = None
        self._cache: Dict[str, pd.DataFrame] = {}
        self._init_akshare()

    def _init_akshare(self):
        try:
            import akshare as ak
            self._ak = ak
            logger.info("akshare 初始化成功")
        except ImportError:
            logger.warning("未安装 akshare，数据功能受限")

    def _safe_float(self, v):
        try:
            if v is None:
                return 0.0
            s = str(v).replace("%", "").replace(",", "").replace("亿", "").replace("万", "")
            return float(s)
        except (ValueError, TypeError):
            return 0.0

    # ===== 涨停板数据 =====
    def get_limit_up_list(self) -> pd.DataFrame:
        """获取当日涨停板列表"""
        try:
            if self._ak:
                df = self._ak.stock_zt_pool_em(date=datetime.now().strftime("%Y%m%d"))
                if df is not None and not df.empty:
                    return df
        except Exception as e:
            logger.debug(f"获取涨停板失败: {e}")
        return pd.DataFrame()

    def get_limit_down_list(self) -> pd.DataFrame:
        """获取当日跌停板列表"""
        try:
            if self._ak:
                df = self._ak.stock_zt_pool_dtgc_em(date=datetime.now().strftime("%Y%m%d"))
                if df is not None and not df.empty:
                    return df
        except Exception as e:
            logger.debug(f"获取跌停板失败: {e}")
        return pd.DataFrame()

    # ===== 资金流向 =====
    def get_main_capital_flow(self) -> pd.DataFrame:
        """获取个股主力资金流向"""
        try:
            if self._ak:
                df = self._ak.stock_individual_fund_flow_rank(indicator="今日")
                if df is not None and not df.empty:
                    return df
        except Exception as e:
            logger.debug(f"获取主力资金流向失败: {e}")
        return pd.DataFrame()

    def get_sector_capital_flow(self) -> pd.DataFrame:
        """获取行业板块资金流向"""
        try:
            if self._ak:
                df = self._ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="行业资金流")
                if df is not None and not df.empty:
                    return df
        except Exception as e:
            logger.debug(f"获取板块资金流向失败: {e}")
        return pd.DataFrame()

    def get_north_flow(self) -> dict:
        """获取北向资金"""
        try:
            if self._ak:
                df = self._ak.stock_hsgt_north_net_flow_in_em(symbol="北上")
                if df is not None and not df.empty:
                    latest = df.iloc[-1]
                    return {"date": str(latest.iloc[0]), "net_inflow": self._safe_float(latest.iloc[1])}
        except Exception as e:
            logger.debug(f"获取北向资金失败: {e}")
        return {}

    # ===== 龙虎榜 =====
    def get_lhb_list(self) -> pd.DataFrame:
        """获取龙虎榜"""
        try:
            if self._ak:
                df = self._ak.stock_lhb_detail_em(start_date=datetime.now().strftime("%Y%m%d"),
                                                     end_date=datetime.now().strftime("%Y%m%d"))
                if df is not None and not df.empty:
                    return df
        except Exception as e:
            logger.debug(f"获取龙虎榜失败: {e}")
        return pd.DataFrame()

    # ===== 新闻资讯 =====
    def get_news_cctv(self) -> pd.DataFrame:
        """获取新闻联播文字稿"""
        try:
            if self._ak:
                df = self._ak.news_cctv(date=datetime.now().strftime("%Y%m%d"))
                if df is not None and not df.empty:
                    return df
        except Exception as e:
            logger.debug(f"获取新闻联播失败: {e}")
        return pd.DataFrame()

    def get_stock_news(self, symbol: str) -> pd.DataFrame:
        """获取个股新闻"""
        try:
            if self._ak:
                df = self._ak.stock_news_em(symbol=symbol)
                if df is not None and not df.empty:
                    return df.head(20)
        except Exception as e:
            logger.debug(f"获取个股新闻失败 {symbol}: {e}")
        return pd.DataFrame()

    # ===== 行情数据 =====
    def get_realtime_quote(self, symbol: str) -> dict:
        """获取实时行情"""
        try:
            if self._ak:
                df = self._ak.stock_zh_a_spot_em()
                if df is not None and not df.empty:
                    row = df[df["代码"] == symbol.replace(".SH", "").replace(".SZ", "")]
                    if not row.empty:
                        r = row.iloc[0]
                        return {
                            "code": symbol,
                            "name": str(r.get("名称", "")),
                            "price": self._safe_float(r.get("最新价", 0)),
                            "change_pct": self._safe_float(r.get("涨跌幅", 0)),
                            "volume": self._safe_float(r.get("成交量", 0)),
                            "amount": self._safe_float(r.get("成交额", 0)),
                            "turnover": self._safe_float(r.get("换手率", 0)),
                            "volume_ratio": self._safe_float(r.get("量比", 0)),
                        }
        except Exception as e:
            logger.debug(f"获取实时行情失败 {symbol}: {e}")
        return {}

    def get_all_realtime_quotes(self) -> pd.DataFrame:
        """获取全市场实时行情"""
        try:
            if self._ak:
                df = self._ak.stock_zh_a_spot_em()
                if df is not None and not df.empty:
                    return df
        except Exception as e:
            logger.debug(f"获取全市场行情失败: {e}")
        return pd.DataFrame()

    def get_daily_kline(self, symbol: str, days: int = 120) -> pd.DataFrame:
        """获取日K线"""
        try:
            if self._ak:
                code = symbol.replace(".SH", "").replace(".SZ", "")
                df = self._ak.stock_zh_a_hist(symbol=code, period="daily",
                                                start_date=(datetime.now().timestamp() - days*86400).__str__()[:10].replace("-",""),
                                                end_date=datetime.now().strftime("%Y%m%d"), adjust="qfq")
                if df is not None and not df.empty:
                    df = df.rename(columns={"日期":"date","开盘":"open","收盘":"close","最高":"high","最低":"low","成交量":"volume"})
                    return df.tail(days).reset_index(drop=True)
        except Exception as e:
            logger.debug(f"获取K线失败 {symbol}: {e}")
        return pd.DataFrame()

    # ===== 板块/概念 =====
    def get_concept_list(self) -> pd.DataFrame:
        """获取概念板块列表"""
        try:
            if self._ak:
                df = self._ak.stock_board_concept_name_em()
                if df is not None and not df.empty:
                    return df
        except Exception as e:
            logger.debug(f"获取概念板块失败: {e}")
        return pd.DataFrame()

    def get_concept_stocks(self, concept_name: str) -> pd.DataFrame:
        """获取概念板块成分股"""
        try:
            if self._ak:
                df = self._ak.stock_board_concept_cons_em(symbol=concept_name)
                if df is not None and not df.empty:
                    return df
        except Exception as e:
            logger.debug(f"获取概念成分股失败 {concept_name}: {e}")
        return pd.DataFrame()

    # ===== 市场情绪 =====
    def get_market_emotion(self) -> dict:
        """获取市场情绪指标"""
        emotion = {"date": datetime.now().strftime("%Y-%m-%d")}
        try:
            limit_up = self.get_limit_up_list()
            limit_down = self.get_limit_down_list()
            emotion["limit_up_count"] = len(limit_up)
            emotion["limit_down_count"] = len(limit_down)
            # 连板高度
            if not limit_up.empty and "连板数" in limit_up.columns:
                emotion["max_board_height"] = int(limit_up["连板数"].max())
            else:
                emotion["max_board_height"] = 0
            # 涨跌比
            quotes = self.get_all_realtime_quotes()
            if not quotes.empty:
                up = len(quotes[quotes["涨跌幅"] > 0])
                down = len(quotes[quotes["涨跌幅"] < 0])
                emotion["up_count"] = up
                emotion["down_count"] = down
                emotion["up_down_ratio"] = round(up / down, 2) if down > 0 else 999
        except Exception as e:
            logger.debug(f"获取市场情绪失败: {e}")
        return emotion

    def clear_cache(self):
        self._cache.clear()
