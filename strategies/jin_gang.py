from typing import List

from vnpy_ctastrategy import (
    CtaTemplate,
    StopOrder,
    TickData,
    BarData,
    TradeData,
    OrderData,
    BarGenerator,
    ArrayManager,
)
from vnpy.trader.object import PositionData
from vnpy.trader.constant import Interval, Direction, Offset


class JinGangV2(CtaTemplate):
    author = "张强"

    fixed_size = 1  # 开仓手数
    twenty_window = 20
    twenty_ma = 0  # 20日均线
    boll_window = 10  # 布林线计算的间隔
    boll_dev = 2  # 标准差的限度
    tolerance = 10  # 股价相对中轨波动的容忍范围，可调整
    band_width_threshold = 20  # 布林带宽度阈值，较窄时认为震荡，可调整

    boll_up = 0
    boll_down = 0
    parameters = ["twenty_window", "boll_window", "boll_dev", "tolerance", "band_width_threshold"]
    variables = ["twenty_ma", "boll_up", "boll_down", "tolerance", "band_width_threshold"]

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """"""
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)

        self.bg = BarGenerator(self.on_bar, 15, self.on_15min_bar)
        self.am = ArrayManager()
        self.std_long_close_price = 0.0
        self.std_short_close_price = 0.0
        self.stop_long_price = 0
        self.stop_short_price = 0
        self.orders: List[OrderData] = []
        self.bars = []
        self.flag = 0
        self.std = 0
        self.stop_flag = False
        self.twenty_mas = 0.0
        self.five_mas = 0.0
        self.ten_mas = 0.0
        self.positions: List[PositionData] = []

    def on_tick(self, tick: TickData):
        """
        Callback of new tick data update.
        """

        self.bg.update_tick(tick)

        # 开仓逻辑
        self.open_position(tick)
        self.take_profit(tick)

    def on_15min_bar(self, bar: BarData):

        # 初始化计算指标
        if bar.interval == Interval.FIFTEEN:
            self.flag = 0
            self.stop_flag = False
            self.am.update_bar(bar)
            if not self.am.inited:
                return
            self.cancel_all()
            self.twenty_mas = self.am.sma(self.twenty_window, True)
            self.five_mas = self.am.sma(5, True)
            self.ten_mas = self.am.sma(10, True)
            self.twenty_ma = self.twenty_mas[-1]
            # 计算布林指标，以k线的收盘价计算标准差，判断是否是震荡
            std = self.am.std(3, 1, False)
            self.std = std
            self.boll_up = self.twenty_ma + std * self.boll_dev
            self.boll_down = self.twenty_ma - std * self.boll_dev
            self.orders = self.cta_engine.main_engine.get_all_orders()
         
        if not self.trading:
            return

        # 判断震荡行情的条件
        # 这里简单定义为股价大部分时间在布林带中轨上下一定范围内波动，且布林带宽度较窄
        if ((self.boll_up - self.boll_down < self.band_width_threshold)
                or (self.twenty_ma - self.boll_down < self.tolerance)
                or (self.boll_up - self.twenty_ma < self.tolerance)) or self.std <= self.boll_window:
            # 震荡行情不开单
            return
        
        else:
            if (bar.high_price > self.twenty_ma and bar.high_price > self.am.high[-1]
                    and self.am.close[-1] <= self.twenty_mas[-2] and self.std <= self.boll_window):
                if self.five_mas[-1] < self.twenty_ma or self.ten_mas[-1] < self.twenty_ma or self.five_mas[-1] < self.ten_mas[-1]:
                    """通过增加5分钟和15分钟均线做比较，如果有一个快速均线在20日下面就不开多，防止假突破和震荡"""
                    return
                price = bar.high_price + 2
                if self.pos == 0:
                    if self.flag < 0:
                        return

                    self.buy(price, self.fixed_size)
                    self.write_log(
                       f"pos=0条件穿破中轨开多，开仓预设价{price}, bar.low_price{bar.low_price} 仓位 {self.fixed_size} close_price{bar.close_price}, ma{self.twenty_ma}")
                    print(f"pos=0条件穿破中轨开多，开仓预设价{price}, bar.low_price{bar.low_price} 仓位 {self.fixed_size} close_price{bar.close_price}, ma{self.twenty_ma}")
                    self.flag = - 1
            elif bar.low_price < self.twenty_ma and bar.low_price < self.am.low[-1] and self.am.high[-1] >= self.twenty_mas[-2]:
                if self.five_mas[-1] > self.twenty_ma or self.ten_mas[-1] > self.twenty_ma or self.five_mas[-1] > self.ten_mas[-1]:
                    """通过增加5分钟和15分钟均线做比较，如果有一个快速均线在20日上面就不开空，防止假突破和震荡"""
                    return
                price = bar.low_price - 2
                if self.pos == 0:
                    if self.flag < 0:
                        return
                    self.short(price, self.fixed_size)
                    self.write_log(
                        f"pos=0条件跌破中轨开空，开仓预设价{price}, bar.low_price{bar.low_price} 仓位 {self.fixed_size} close_price{bar.close_price}, ma{self.twenty_ma}")
                    print(f"pos=0条件跌破中轨开空，开仓预设价{price}, bar.low_price{bar.low_price} 仓位 {self.fixed_size} close_price{bar.close_price}, ma{self.twenty_ma}")
                    self.flag = -1

        self.put_event()

    def open_position(self, tick: TickData):

        bar = BarData(
                symbol=tick.symbol,
                exchange=tick.exchange,
                interval=Interval.MINUTE,
                datetime=tick.datetime,
                gateway_name=tick.gateway_name,
                open_price=tick.last_price,
                high_price=tick.last_price,
                low_price=tick.last_price,
                close_price=tick.last_price,
                open_interest=tick.open_interest
            )
        self.on_15min_bar(bar)

    def take_profit(self, tick: TickData):
        # 止盈
        orders = self.orders
        if self.pos == 0:
            return
        elif self.pos > 0:

            if tick.last_price < self.am.low[-1]:
                if orders:
                    for order in orders:
                        if order.vt_symbol == self.vt_symbol and order.direction == Direction.SHORT and order.offset == Offset.CLOSE:
                            return
                        else:
                            if self.stop_flag:
                                return
                            else:
                                for p in self.positions:
                                    if p.vt_symbol == self.vt_symbol:
                                        print(p)
                                        self.write_log(f"开始发送平多单:{p}, self.pos={self.pos}")
                                self.sell(tick.last_price - 2, self.pos)
                                self.stop_flag = True

        else:
            if tick.last_price > self.am.high[-1]:
                if orders:
                    for order in orders:
                        if order.vt_symbol == self.vt_symbol and order.direction == Direction.SHORT and order.offset == Offset.CLOSE:
                            return
                        else:
                            if self.stop_flag:
                                return
                            else:
                                for p in self.positions:
                                    if p.vt_symbol == self.vt_symbol:
                            
                                        self.write_log(f"开始发送平空单:{p}, self.pos={abs(self.pos)}")
                                self.cover(tick.last_price + 2, abs(self.pos))
                                self.stop_flag = True

    def on_bar(self, bar: BarData):
        self.bg.update_bar(bar)

    def on_init(self):
        """
        Callback when strategy is inited.
        """
        self.write_log("策略初始化")
        self.load_bar(100)

    def on_start(self):
        """
        Callback when strategy is started.
        """
        self.write_log("策略启动")
        print("策略启动")
        self.put_event()

    def on_stop(self):
        """
        Callback when strategy is stopped.
        """
        self.write_log("策略停止")

        self.put_event()

    def on_order(self, order: OrderData):
        """
        Callback of new order data update.
        """
        pass

    def on_trade(self, trade: TradeData):
        """
        开仓成功后立即创建止损单
        """
        self.positions = self.cta_engine.main_engine.get_all_positions()
        if trade.direction == Direction.LONG and trade.offset == Offset.OPEN:
            self.stop_long_price = self.am.low[-1]
            self.sell(float(self.stop_long_price), trade.volume, True)
        elif trade.direction == Direction.SHORT and trade.offset == Offset.OPEN:
            self.stop_short_price = self.am.high[-1]
            self.cover(float(self.am.high[-1]), trade.volume, True)
        self.write_log(f"{trade.vt_symbol}:{trade.direction}:{trade.offset},成功")
        print(f"{trade.vt_symbol}:{trade.direction}:{trade.offset},成功")
        self.put_event()

    def on_stop_order(self, stop_order: StopOrder):
        """
        Callback of stop order update.
        """
        pass


    
