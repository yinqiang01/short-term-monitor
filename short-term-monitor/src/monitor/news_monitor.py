"""新闻热点监控模块"""
from datetime import datetime
from typing import List, Dict
from ..data.data_fetcher import DataFetcher
from ..logger import get_logger

logger = get_logger("NewsMonitor")


class NewsMonitor:
    def __init__(self, config: dict, data: DataFetcher):
        self.config = config
        self.data = data
        self.keywords = config.get("keywords", [])
        self.excluded = config.get("excluded_keywords", [])
        self._seen_news = set()  # 去重

    def check(self) -> List[Dict]:
        """检查新闻热点，返回异动新闻列表"""
        alerts = []
        try:
            # 1. 新闻联播
            cctv_news = self.data.get_news_cctv()
            if not cctv_news.empty:
                for _, row in cctv_news.iterrows():
                    content = str(row.get("内容", "")) + str(row.get("标题", ""))
                    if self._match_keywords(content):
                        news_id = hashlib.md5(content[:50].encode()).hexdigest()
                        if news_id not in self._seen_news:
                            self._seen_news.add(news_id)
                            alerts.append({
                                "source": "新闻联播",
                                "title": content[:60],
                                "content": content[:200],
                                "time": datetime.now().strftime("%H:%M"),
                                "matched_keywords": self._extract_keywords(content),
                                "stock": ""
                            })

            # 2. 全市场行情中涨幅异常的股票，查其新闻
            quotes = self.data.get_all_realtime_quotes()
            if not quotes.empty:
                # 涨幅超5%的股票
                hot_stocks = quotes[quotes["涨跌幅"] > 5].head(10)
                for _, row in hot_stocks.iterrows():
                    code = str(row.get("代码", ""))
                    name = str(row.get("名称", ""))
                    news = self.data.get_stock_news(code)
                    if not news.empty:
                        latest = news.iloc[0]
                        title = str(latest.get("新闻标题", ""))
                        if self._match_keywords(title):
                            news_id = hashlib.md5(title[:50].encode()).hexdigest()
                            if news_id not in self._seen_news:
                                self._seen_news.add(news_id)
                                alerts.append({
                                    "source": "个股新闻",
                                    "title": title[:60],
                                    "content": str(latest.get("新闻内容", ""))[:200],
                                    "time": str(latest.get("发布时间", ""))[:16],
                                    "matched_keywords": self._extract_keywords(title),
                                    "stock": f"{name}({code}) 涨幅{row.get('涨跌幅',0):.1f}%"
                                })

            if alerts:
                logger.info(f"发现 {len(alerts)} 条新闻异动")

        except Exception as e:
            logger.error(f"新闻监控异常: {e}")

        return alerts

    def _match_keywords(self, text: str) -> bool:
        """匹配关键词"""
        if not text:
            return False
        # 排除词
        for kw in self.excluded:
            if kw in text:
                return False
        # 匹配词
        for kw in self.keywords:
            if kw in text:
                return True
        return False

    def _extract_keywords(self, text: str) -> List[str]:
        """提取匹配到的关键词"""
        return [kw for kw in self.keywords if kw in text]


def hashlib_md5(s: str) -> str:
    import hashlib
    return hashlib.md5(s.encode("utf-8")).hexdigest()
