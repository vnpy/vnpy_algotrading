from vnpy.trader.constant import Direction
from vnpy.trader.object import TradeData, OrderData, TickData
from vnpy.trader.engine import BaseEngine

from ..template import AlgoTemplate


class IcebergAlgo(AlgoTemplate):
    """冰山算法类"""

    display_name: str = "Iceberg 冰山"

    default_setting: dict = {
        "display_volume": 0.0,
        "interval": 0
    }

    variables: list = [
        "timer_count",
        "vt_orderid"
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
        self.display_volume: float = setting["display_volume"]
        self.interval: int = setting["interval"]

        # 变量
        self.timer_count: int = 0
        self.vt_orderid: str = ""

        self.put_event()

    def on_order(self, order: OrderData) -> None:
        """委托回调"""
        msg: str = f"委托号：{order.vt_orderid}，委托状态：{order.status.value}"
        self.write_log(msg)

        if not order.is_active():
            self.vt_orderid = ""
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

        if self.timer_count < self.interval:
            self.put_event()
            return

        self.timer_count = 0

        tick: TickData = self.get_tick()
        if not tick:
            return

        # 当委托完成后，发起新的委托
        if not self.vt_orderid:
            order_volume: float = self.volume - self.traded
            order_volume = min(order_volume, self.display_volume)

            if self.direction == Direction.LONG:
                self.vt_orderid = self.buy(
                    self.price,
                    order_volume,
                    offset=self.offset
                )
            else:
                self.vt_orderid = self.sell(
                    self.price,
                    order_volume,
                    offset=self.offset
                )
        # 否则检查撤单
        else:
            if self.direction == Direction.LONG:
                if tick.ask_price_1 <= self.price:
                    self.cancel_order(self.vt_orderid)
                    self.vt_orderid = ""
                    self.write_log(u"最新Tick卖一价，低于买入委托价格，之前委托可能丢失，强制撤单")
            else:
                if tick.bid_price_1 >= self.price:
                    self.cancel_order(self.vt_orderid)
                    self.vt_orderid = ""
                    self.write_log(u"最新Tick买一价，高于卖出委托价格，之前委托可能丢失，强制撤单")

        self.put_event()
