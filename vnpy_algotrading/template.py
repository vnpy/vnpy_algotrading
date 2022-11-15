from typing import Dict, Optional

from vnpy.trader.engine import BaseEngine
from vnpy.trader.object import TickData, OrderData, TradeData, ContractData
from vnpy.trader.constant import OrderType, Offset, Direction
from vnpy.trader.utility import virtual

from .base import AlgoStatus


class AlgoTemplate:
    """算法模板"""

    _count: int = 0                 # 算法实例的计数

    display_name: str = ""          # 显示名称
    default_setting: dict = {}      # 默认参数
    variables: list = []            # 变量名称

    def __init__(
        self,
        algo_engine: BaseEngine,
        algo_name: str,
        vt_symbol: str,
        direction: Direction,
        offset: Offset,
        price: float,
        volume: int,
        setting: dict
    ) -> None:
        """构造函数"""
        self.algo_engine: BaseEngine = algo_engine
        self.algo_name: str = algo_name

        self.vt_symbol: str = vt_symbol
        self.direction: Direction = direction
        self.offset: Offset = offset
        self.price: float = price
        self.volume: int = volume

        self.status: str = AlgoStatus.PAUSED
        self.traded: float = 0
        self.active_orders: Dict[str, OrderData] = {}  # vt_orderid:order

        self.variables.insert(0, "status")
        self.variables.insert(1, "traded")

    def update_tick(self, tick: TickData) -> None:
        """行情数据更新"""
        if self.status == AlgoStatus.RUNNING:
            self.on_tick(tick)

    def update_order(self, order: OrderData) -> None:
        """委托数据更新"""
        if order.is_active():
            self.active_orders[order.vt_orderid] = order
        elif order.vt_orderid in self.active_orders:
            self.active_orders.pop(order.vt_orderid)

        self.on_order(order)

    def update_trade(self, trade: TradeData) -> None:
        """成交数据更新"""
        self.on_trade(trade)

    def update_timer(self) -> None:
        """每秒定时更新"""
        if self.status == AlgoStatus.RUNNING:
            self.on_timer()

    @virtual
    def on_tick(self, tick: TickData) -> None:
        """行情回调"""
        pass

    @virtual
    def on_order(self, order: OrderData) -> None:
        """委托回调"""
        pass

    @virtual
    def on_trade(self, trade: TradeData) -> None:
        """成交回调"""
        pass

    @virtual
    def on_timer(self) -> None:
        """定时回调"""
        pass

    def start(self) -> None:
        """启动"""
        self.status = AlgoStatus.RUNNING
        self.put_variables_event()

        self.write_log("算法启动")

    def stop(self) -> None:
        """停止"""
        self.status = AlgoStatus.STOPPED
        self.cancel_all()
        self.put_variables_event()

        self.write_log("算法停止")

    def finish(self) -> None:
        """结束"""
        self.status = AlgoStatus.FINISHED
        self.cancel_all()
        self.put_variables_event()

        self.write_log("算法结束")

    def pause(self) -> None:
        """暂停"""
        self.status = AlgoStatus.PAUSED
        self.put_variables_event()

        self.write_log("算法暂停")

    def resume(self) -> None:
        """恢复"""
        self.status = AlgoStatus.RUNNING
        self.put_variables_event()

        self.write_log("算法恢复")

    def buy(
        self,
        price: float,
        volume: float,
        order_type: OrderType = OrderType.LIMIT,
        offset: Offset = Offset.NONE
    ) -> None:
        """买入"""
        if self.status != AlgoStatus.RUNNING:
            return

        msg: str = f"{self.vt_symbol}，委托买入{order_type.value}，{volume}@{price}"
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
        """卖出"""
        if self.status != AlgoStatus.RUNNING:
            return

        msg: str = f"{self.vt_symbol}委托卖出{order_type.value}，{volume}@{price}"
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
        """撤销委托"""
        self.algo_engine.cancel_order(self, vt_orderid)

    def cancel_all(self) -> None:
        """全撤委托"""
        if not self.active_orders:
            return

        for vt_orderid in self.active_orders.keys():
            self.cancel_order(vt_orderid)

    def get_tick(self) -> Optional[TickData]:
        """查询行情"""
        return self.algo_engine.get_tick(self)

    def get_contract(self) -> Optional[ContractData]:
        """查询合约"""
        return self.algo_engine.get_contract(self)

    def write_log(self, msg: str) -> None:
        """输出日志"""
        self.algo_engine.write_log(msg, self)

    def put_parameters_event(self) -> None:
        """推送参数更新"""
        keys: list = ["vt_symbol", "direction", "offset", "price", "volume"]
        keys.extend(self.default_setting.keys())

        parameters: dict = {}
        for name in keys:
            parameters[name] = getattr(self, name)

        self.algo_engine.put_parameters_event(self, parameters)

    def put_variables_event(self) -> None:
        """推送变量更新"""
        variables: dict = {}
        for name in self.variables:
            variables[name] = getattr(self, name)

        self.algo_engine.put_variables_event(self, variables)
