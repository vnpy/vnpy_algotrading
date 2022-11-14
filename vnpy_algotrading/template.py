from typing import Dict, Optional

from vnpy.trader.engine import BaseEngine
from vnpy.trader.object import TickData, OrderData, TradeData, ContractData
from vnpy.trader.constant import OrderType, Offset, Direction
from vnpy.trader.utility import virtual

from .base import AlgoStatus


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
        vt_symbol: str,
        direction: str,
        offset: str,
        volume: float,
        setting: dict
    ) -> None:
        """构造函数"""
        self.algo_engine: BaseEngine = algo_engine
        self.algo_name: str = algo_name

        self.vt_symbol: str = vt_symbol
        self.direction = Direction(direction)
        self.volume = volume
        self.offset = Offset(offset)

        self.status: str = AlgoStatus.PAUSED
        self.active_orders: Dict[str, OrderData] = {}  # vt_orderid:order

        self.variables.insert(0, "status")

    def update_tick(self, tick: TickData) -> None:
        """"""
        if self.status == AlgoStatus.RUNNING:
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
        if self.status == AlgoStatus.RUNNING:
            self.on_timer()

    @virtual
    def on_start(self) -> None:
        """"""
        pass

    @virtual
    def on_stop(self) -> None:
        """"""
        pass

    @virtual
    def on_pause(self) -> None:
        """"""
        pass

    @virtual
    def on_resume(self) -> None:
        """"""
        pass

    @virtual
    def on_terminate(self) -> None:
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
        self.status = AlgoStatus.RUNNING
        self.on_start()
        self.put_variables_event()

        self.write_log("算法启动")

    def stop(self) -> None:
        """"""
        self.status = AlgoStatus.FINISHED
        self.cancel_all()
        self.on_stop()
        self.put_variables_event()

        self.write_log("算法结束")

    def terminate(self) -> None:
        """"""
        self.status = AlgoStatus.STOPPED
        self.cancel_all()
        self.on_terminate()
        self.put_variables_event()

        self.write_log("算法停止")

    def pause(self) -> None:
        """"""
        self.status = AlgoStatus.PAUSED
        self.cancel_all()
        self.on_pause()
        self.put_variables_event()

        self.write_log("算法暂停")

    def resume(self) -> None:
        """"""
        self.status = AlgoStatus.RUNNING
        self.on_resume()
        self.put_variables_event()

        self.write_log("算法重启")

    def buy(
        self,
        price: float,
        volume: float,
        order_type: OrderType = OrderType.LIMIT,
        offset: Offset = Offset.NONE
    ) -> None:
        """"""
        if self.status == AlgoStatus.RUNNING:
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
        if self.status == AlgoStatus.RUNNING:
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
