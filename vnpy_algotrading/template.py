from typing import Dict, Optional

from vnpy.trader.engine import BaseEngine
from vnpy.trader.object import TickData, OrderData, TradeData, ContractData
from vnpy.trader.constant import OrderType, Offset, Direction
from vnpy.trader.utility import virtual


class AlgoTemplate:
    """"""
    _count: int = 0
    display_name: str = ""
    default_setting: dict = {}
    variables: list = []

    def __init__(
        self,
        algo_engine: BaseEngine,
        algo_name: str,
        setting: dict,
        vt_symbol: str
    ) -> None:
        """构造函数"""
        self.algo_engine: BaseEngine = algo_engine
        self.algo_name: str = algo_name
        self.vt_symbol: str = vt_symbol

        self.active: bool = False
        self.active_orders: Dict[str, OrderData] = {}  # vt_orderid:order

        self.variables.insert(0, "active")

    @classmethod
    def new(cls, algo_engine: BaseEngine, setting: dict) -> "AlgoTemplate":
        """创建一个新的算法实例"""
        cls._count += 1
        algo_name: str = f"{cls.__name__}_{cls._count}"
        algo: AlgoTemplate = cls(algo_engine, algo_name, setting, setting["vt_symbol"])
        return algo

    def update_tick(self, tick: TickData) -> None:
        """"""
        if self.active:
            self.on_tick(tick)

    def update_order(self, order: OrderData) -> None:
        """"""
        if order.is_active():
            self.active_orders[order.vt_orderid] = order
        elif order.vt_orderid in self.active_orders:
            self.active_orders.pop(order.vt_orderid)

        self.on_order(order)

    def update_trade(self, trade: TradeData) -> None:
        """"""
        self.on_trade(trade)

    def update_timer(self) -> None:
        """"""
        if self.active:
            self.on_timer()

    def on_start(self) -> None:
        """"""
        pass

    @virtual
    def on_stop(self) -> None:
        """"""
        pass

    @virtual
    def on_tick(self, tick: TickData) -> None:
        """"""
        pass

    @virtual
    def on_order(self, order: OrderData) -> None:
        """"""
        pass

    @virtual
    def on_trade(self, trade: TradeData) -> None:
        """"""
        pass

    @virtual
    def on_timer(self) -> None:
        """"""
        pass

    def start(self) -> None:
        """"""
        self.active = True
        self.on_start()
        self.put_variables_event()

    def stop(self) -> None:
        """"""
        self.active = False
        self.cancel_all()
        self.on_stop()
        self.put_variables_event()

        self.write_log("停止算法")

    def subscribe(self) -> None:
        """"""
        self.algo_engine.subscribe(self)

    def buy(
        self,
        price: float,
        volume: float,
        order_type: OrderType = OrderType.LIMIT,
        offset: Offset = Offset.NONE
    ) -> None:
        """"""
        if not self.active:
            return

        msg: str = f"委托买入{self.vt_symbol}：{volume}@{price}"
        self.write_log(msg)

        return self.algo_engine.send_order(
            self,
            Direction.LONG,
            price,
            volume,
            order_type,
            offset
        )

    def sell(
        self,
        price: float,
        volume: float,
        order_type: OrderType = OrderType.LIMIT,
        offset: Offset = Offset.NONE
    ) -> None:
        """"""
        if not self.active:
            return

        msg: str = f"委托卖出{self.vt_symbol}：{volume}@{price}"
        self.write_log(msg)

        return self.algo_engine.send_order(
            self,
            Direction.SHORT,
            price,
            volume,
            order_type,
            offset
        )

    def cancel_order(self, vt_orderid: str) -> None:
        """"""
        self.algo_engine.cancel_order(self, vt_orderid)

    def cancel_all(self) -> None:
        """"""
        if not self.active_orders:
            return

        for vt_orderid in self.active_orders.keys():
            self.cancel_order(vt_orderid)

    def get_tick(self) -> Optional[TickData]:
        """"""
        return self.algo_engine.get_tick(self)

    def get_contract(self) -> Optional[ContractData]:
        """"""
        return self.algo_engine.get_contract(self)

    def write_log(self, msg: str) -> None:
        """"""
        self.algo_engine.write_log(msg, self)

    def put_parameters_event(self) -> None:
        """"""
        parameters: dict = {}
        for name in self.default_setting.keys():
            parameters[name] = getattr(self, name)

        self.algo_engine.put_parameters_event(self, parameters)

    def put_variables_event(self) -> None:
        """"""
        variables: dict = {}
        for name in self.variables:
            variables[name] = getattr(self, name)

        self.algo_engine.put_variables_event(self, variables)
