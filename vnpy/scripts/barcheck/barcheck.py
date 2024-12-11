from datetime import date, timedelta, datetime
from zoneinfo import ZoneInfo
from typing import List


from vnpy.trader.database import get_database
from vnpy.trader.object import BarData, Interval, Exchange


class BarCheck:
    """用于删除非交易时间段的1分钟K线"""
    def __init__(self):
        self.database = get_database()
        self.bars: List[BarData] = []
        self.today = date.today()
        self.last_day = self.today - timedelta(days=1)
        self.tzinfo = ZoneInfo(key='Asia/Shanghai')

    def load_today_bar(self):
        today = self.today
        last_day = self.last_day
        start_time = datetime(last_day.year, last_day.month, last_day.day, 20, 59, 0, tzinfo=self.tzinfo)
        end_time = datetime(today.year, today.month, today.day, 15, 0, 0, tzinfo=self.tzinfo)
        sysmbols = self.database.load_bar_symbols()

        for s in sysmbols:
            bars = self.database.load_bar_data(s.symbol, Exchange.__getitem__(s.exchange), Interval.MINUTE, start_time,
                                               end_time)
            abnormal_bars = self.find_abnormal_bars(bars)
            if abnormal_bars:
                self.delete_abnormal_bar(abnormal_bars)

    def delete_abnormal_bar(self, del_bars: List[BarData]):
        # 先备份再删除
        self.database.save_barbak_data(del_bars)
        for bar in del_bars:
            self.database.delete_specific_bar(symbol=bar.symbol, exchange=bar.exchange, interval=bar.interval,
                                              datetime=bar.datetime)

    def find_abnormal_bars(self, bars: List[BarData]) -> List[BarData]:
        # 非交易时间段
        out_trade_time_1 = datetime(self.last_day.year, self.last_day.month, self.last_day.day, 23, 0, 0, tzinfo=self.tzinfo)
        out_trade_time_1_end = datetime(self.today.year, self.today.month, self.today.day, 8, 59, 0, tzinfo=self.tzinfo)
        out_trade_time_2 = datetime(self.today.year, self.today.month, self.today.day, 15, 0, 0, tzinfo=self.tzinfo)
        out_trade_time_2_end = datetime(self.today.year, self.today.month, self.today.day, 20, 59, 0, tzinfo=self.tzinfo)
        out_trade_time_3 = datetime(self.today.year, self.today.month, self.today.day, 10, 15, 0, tzinfo=self.tzinfo)
        out_trade_time_3_end = datetime(self.today.year, self.today.month, self.today.day, 10, 30, 0, tzinfo=self.tzinfo)
        out_trade_time_4 = datetime(self.today.year, self.today.month, self.today.day, 11, 30, 0, tzinfo=self.tzinfo)
        out_trade_time_4_end = datetime(self.today.year, self.today.month, self.today.day, 13, 30, 0, tzinfo=self.tzinfo)
        # 沪金和沪银交易时间过滤
        #out_trade_time_5 = datetime(self.last_day.year, self.last_day.month, self.last_day.day, 2, 30, 0, tzinfo=self.tzinfo)
        del_bars: List[BarData] = []
        for bar in bars:
            if (bar.datetime > out_trade_time_1 and bar.datetime < out_trade_time_1_end) or (bar.datetime > out_trade_time_2 and bar.datetime < out_trade_time_2_end) or (bar.datetime > out_trade_time_3 and bar.datetime < out_trade_time_3_end) or (bar.datetime > out_trade_time_4 and bar.datetime < out_trade_time_4_end):
                if bar.symbol.startswith('ag') or bar.symbol.startswith('au'):
                    continue
                del_bars.append(bar)
        return del_bars


if __name__ == '__main__':
    bc = BarCheck()
    bc.load_today_bar()
