from vnpy.trader.utility import round_to
from vnpy.trader.constant import Direction
from vnpy.trader.object import TradeData, TickData, ContractData
from vnpy.trader.engine import BaseEngine

from ..template import AlgoTemplate


class TwapAlgo(AlgoTemplate):
    """TWAP算法类"""

    display_name: str = "TWAP 时间加权平均"

    default_setting: dict = {
        "time": 600,
        "interval": 60
    }

    variables: list = [
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
        price: float,
        volume: float,
        setting: dict
    ) -> None:
        """构造函数"""
        super().__init__(algo_engine, algo_name, vt_symbol, direction, offset, price, volume, setting)

        # 参数
        self.time: int = setting["time"]
        self.interval: int = setting["interval"]

        # 变量
        self.order_volume: int = self.volume / (self.time / self.interval)
        contract: ContractData = self.get_contract()
        if contract:
            self.order_volume = round_to(self.order_volume, contract.min_volume)

        self.timer_count: int = 0
        self.total_count: int = 0

        self.put_event()

    def on_trade(self, trade: TradeData) -> None:
        """成交回调"""
        if self.traded >= self.volume:
            self.write_log(f"已交易数量：{self.traded}，总数量：{self.volume}")
            self.finish()
        else:
            self.put_event()

    def on_timer(self) -> None:
        """定时回调"""
        self.timer_count += 1
        self.total_count += 1
        self.put_event()

        if self.total_count >= self.time:
            self.write_log("执行时间已结束，停止算法")
            self.finish()
            return

        if self.timer_count < self.interval:
            return
        self.timer_count = 0

        tick: TickData = self.get_tick()
        if not tick:
            return

        self.cancel_all()

        left_volume: int = self.volume - self.traded
        order_volume = min(self.order_volume, left_volume)

        if self.direction == Direction.LONG:
            if tick.ask_price_1 <= self.price:
                self.buy(self.price, order_volume, offset=self.offset)
        else:
            if tick.bid_price_1 >= self.price:
                self.sell(self.price, order_volume, offset=self.offset)
