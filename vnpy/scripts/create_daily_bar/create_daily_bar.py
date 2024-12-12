
from datetime import datetime
from vnpy.trader.utility import BarGenerator
from vnpy.trader.object import BarData
from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.database import get_database


class DailyBarGenerator:
    def __init__(self):
        self.database = get_database()
        self.bg = None


    def on_bar(self, bar: BarData) -> None:
        self.bg.update_bar(bar)

    def on_daily_bar(self, bar: BarData) -> None:
        self.database.save_bar_data([bar])

    def load_bar_data(self, start: str, end: str):
        self.bg = BarGenerator(self.on_bar,0, self.on_daily_bar, Interval.DAILY, datetime.strptime("15:00:00", "%H:%M:%S").time())
        start_time = datetime.strptime(start, "%Y-%m-%d %H:%M:%S")
        end_time = datetime.strptime(end, "%Y-%m-%d %H:%M:%S")
        symbol_data = self.database.load_bar_symbols()
        for symbol in symbol_data:
            bars = self.database.load_bar_data(symbol.symbol, Exchange.__getitem__(symbol.exchange), Interval.MINUTE, start_time, end_time)
            for bar in bars:
                self.on_bar(bar)


if __name__ == '__main__':
    start_time = "2024-1-10 20:59:00"
    end_time = "2024-12-11 15:00:00"
    bg = DailyBarGenerator()
    bg.load_bar_data(start_time, end_time)