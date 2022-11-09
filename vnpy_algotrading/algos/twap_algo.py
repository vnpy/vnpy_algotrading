from vnpy.trader.utility import round_to
from vnpy.trader.constant import Offset, Direction
from vnpy.trader.object import TradeData, TickData
from vnpy.trader.engine import BaseEngine

from ..template import AlgoTemplate


class TwapAlgo(AlgoTemplate):
    """"""

    display_name = "TWAP 时间加权平均"

    default_setting = {
        "vt_symbol": "",
        "direction": [Direction.LONG.value, Direction.SHORT.value],
        "price": 0.0,
        "volume": 0.0,
        "time": 600,
        "interval": 60,
        "offset": [
            Offset.NONE.value,
            Offset.OPEN.value,
            Offset.CLOSE.value,
            Offset.CLOSETODAY.value,
            Offset.CLOSEYESTERDAY.value
        ]
    }

    variables = [
        "traded",
        "order_volume",
        "timer_count",
        "total_count"
    ]

    def __init__(
        self,
        algo_engine: BaseEngine,
        algo_name: str,
        vt_symbol: str,
        direction: str,
        offset: str,
        volume: float,
        setting: dict
    ):
        """"""
        super().__init__(algo_engine, algo_name, vt_symbol, direction, offset, volume, setting)

        # 参数
        self.price = setting["price"]
        self.time = setting["time"]
        self.interval = setting["interval"]

        # 变量
        self.order_volume = self.volume / (self.time / self.interval)
        contract = self.get_contract()
        if contract:
            self.order_volume = round_to(self.order_volume, contract.min_volume)

        self.timer_count = 0
        self.total_count = 0
        self.traded = 0

        self.last_tick = None

        self.put_parameters_event()
        self.put_variables_event()

    def on_tick(self, tick: TickData):
        """"""
        self.last_tick = tick

    def on_trade(self, trade: TradeData):
        """"""
        self.traded += trade.volume

        if self.traded >= self.volume:
            self.write_log(f"已交易数量：{self.traded}，总数量：{self.volume}")
            self.stop()
        else:
            self.put_variables_event()

    def on_timer(self):
        """"""
        self.timer_count += 1
        self.total_count += 1
        self.put_variables_event()

        if self.total_count >= self.time:
            self.write_log("执行时间已结束，停止算法")
            self.stop()
            return

        if self.timer_count < self.interval:
            return
        self.timer_count = 0

        if not self.last_tick:
            return
        tick = self.last_tick
        self.last_tick = None

        self.cancel_all()

        left_volume = self.volume - self.traded
        order_volume = min(self.order_volume, left_volume)

        if self.direction == Direction.LONG:
            if tick.ask_price_1 <= self.price:
                self.buy(self.price, order_volume, offset=self.offset)
        else:
            if tick.bid_price_1 >= self.price:
                self.sell(self.price, order_volume, offset=self.offset)
