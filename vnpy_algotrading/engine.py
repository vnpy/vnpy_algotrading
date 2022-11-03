from collections import defaultdict
from typing import Dict, List, Optional, Set

from vnpy.event import EventEngine, Event
from vnpy.trader.engine import BaseEngine, MainEngine
from vnpy.trader.event import (
    EVENT_TICK,
    EVENT_TIMER,
    EVENT_ORDER,
    EVENT_TRADE
)
from vnpy.trader.constant import Direction, Offset, OrderType
from vnpy.trader.object import (
    SubscribeRequest,
    OrderRequest,
    LogData,
    ContractData,
    OrderData,
    TickData,
    TradeData,
    CancelRequest
)
from vnpy.trader.utility import load_json, save_json, round_to

from .template import AlgoTemplate
from .base import (
    EVENT_ALGO_LOG,
    EVENT_ALGO_PARAMETERS,
    EVENT_ALGO_SETTING,
    EVENT_ALGO_VARIABLES,
    APP_NAME
)


class AlgoEngine(BaseEngine):
    """"""
    setting_filename: str = "algo_trading_setting.json"

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine) -> None:
        """构造函数"""
        super().__init__(main_engine, event_engine, APP_NAME)

        self.algos: Dict[str, AlgoTemplate] = {}
        self.symbol_algo_map: Dict[str, Set[AlgoTemplate]] = defaultdict(set)
        self.orderid_algo_map: dict = {}

        self.algo_templates: dict = {}
        self.algo_settings: dict = {}

        self.load_algo_template()
        self.register_event()

    def init_engine(self) -> None:
        """"""
        self.write_log("算法交易引擎启动")
        self.load_algo_setting()

    def close(self) -> None:
        """"""
        pass

    def load_algo_template(self) -> None:
        """"""
        from .algos.twap_algo import TwapAlgo
        from .algos.iceberg_algo import IcebergAlgo
        from .algos.sniper_algo import SniperAlgo
        from .algos.stop_algo import StopAlgo
        from .algos.best_limit_algo import BestLimitAlgo
        from .algos.dma_algo import DmaAlgo

        self.add_algo_template(TwapAlgo)
        self.add_algo_template(IcebergAlgo)
        self.add_algo_template(SniperAlgo)
        self.add_algo_template(StopAlgo)
        self.add_algo_template(BestLimitAlgo)
        self.add_algo_template(DmaAlgo)

    def add_algo_template(self, template: AlgoTemplate) -> None:
        """"""
        self.algo_templates[template.__name__] = template

    def get_algo_template(self) -> dict:
        """"""
        return self.algo_templates

    def load_algo_setting(self) -> None:
        """"""
        self.algo_settings: dict = load_json(self.setting_filename)

        for setting_name, setting in self.algo_settings.items():
            self.put_setting_event(setting_name, setting)

        self.write_log("算法配置载入成功")

    def save_algo_setting(self) -> None:
        """"""
        save_json(self.setting_filename, self.algo_settings)

    def register_event(self) -> None:
        """"""
        self.event_engine.register(EVENT_TICK, self.process_tick_event)
        self.event_engine.register(EVENT_TIMER, self.process_timer_event)
        self.event_engine.register(EVENT_ORDER, self.process_order_event)
        self.event_engine.register(EVENT_TRADE, self.process_trade_event)

    def process_tick_event(self, event: Event) -> None:
        """"""
        tick: TickData = event.data
        algos: Optional[Set[AlgoTemplate]] = self.symbol_algo_map[tick.vt_symbol]

        for algo in algos:
            algo.update_tick(tick)

    def process_timer_event(self, event: Event) -> None:
        """"""
        # 生成列表避免字典改变
        algos: List[AlgoTemplate] = list(self.algos.values())

        for algo in algos:
            algo.update_timer()

    def process_trade_event(self, event: Event) -> None:
        """"""
        trade: TradeData = event.data

        algo: Optional[AlgoTemplate] = self.orderid_algo_map.get(trade.vt_orderid, None)
        if algo:
            algo.update_trade(trade)

    def process_order_event(self, event: Event) -> None:
        """"""
        order: OrderData = event.data

        algo: Optional[AlgoTemplate] = self.orderid_algo_map.get(order.vt_orderid, None)
        if algo:
            algo.update_order(order)

    def start_algo(self, setting: dict) -> str:
        """"""
        template_name: str = setting["template_name"]
        algo_template: AlgoTemplate = self.algo_templates[template_name]

        algo: AlgoTemplate = algo_template.new(self, setting)
        algo.start()

        self.algos[algo.algo_name] = algo
        return algo.algo_name

    def stop_algo(self, algo_name: str) -> None:
        """"""
        algo: Optional[AlgoTemplate] = self.algos.get(algo_name, None)
        if algo:
            algo.stop()

    def stop_all(self) -> None:
        """"""
        for algo_name in list(self.algos.keys()):
            self.stop_algo(algo_name)

    def subscribe(self, algo: AlgoTemplate, vt_symbol: str) -> None:
        """"""
        contract: Optional[ContractData] = self.main_engine.get_contract(vt_symbol)
        if not contract:
            self.write_log(f'订阅行情失败，找不到合约：{vt_symbol}', algo)
            return

        algos: set = self.symbol_algo_map[vt_symbol]

        if not algos:
            req: SubscribeRequest = SubscribeRequest(
                symbol=contract.symbol,
                exchange=contract.exchange
            )
            self.main_engine.subscribe(req, contract.gateway_name)

        algos.add(algo)

    def send_order(
        self,
        algo: AlgoTemplate,
        vt_symbol: str,
        direction: Direction,
        price: float,
        volume: float,
        order_type: OrderType,
        offset: Offset
    ) -> str:
        """"""
        contract: Optional[ContractData] = self.main_engine.get_contract(vt_symbol)
        if not contract:
            self.write_log(f'委托下单失败，找不到合约：{vt_symbol}', algo)
            return

        volume: float = round_to(volume, contract.min_volume)
        if not volume:
            return ""

        req: OrderRequest = OrderRequest(
            symbol=contract.symbol,
            exchange=contract.exchange,
            direction=direction,
            type=order_type,
            volume=volume,
            price=price,
            offset=offset,
            reference=f"{APP_NAME}_{algo.algo_name}"
        )
        vt_orderid: str = self.main_engine.send_order(req, contract.gateway_name)

        self.orderid_algo_map[vt_orderid] = algo
        return vt_orderid

    def cancel_order(self, algo: AlgoTemplate, vt_orderid: str) -> None:
        """"""
        order: Optional[OrderData] = self.main_engine.get_order(vt_orderid)

        if not order:
            self.write_log(f"委托撤单失败，找不到委托：{vt_orderid}", algo)
            return

        req: CancelRequest = order.create_cancel_request()
        self.main_engine.cancel_order(req, order.gateway_name)

    def get_tick(self, algo: AlgoTemplate, vt_symbol: str) -> Optional[TickData]:
        """"""
        tick: Optional[TickData] = self.main_engine.get_tick(vt_symbol)

        if not tick:
            self.write_log(f"查询行情失败，找不到行情：{vt_symbol}", algo)

        return tick

    def get_contract(self, algo: AlgoTemplate, vt_symbol: str) -> Optional[ContractData]:
        """"""
        contract: Optional[ContractData] = self.main_engine.get_contract(vt_symbol)

        if not contract:
            self.write_log(f"查询合约失败，找不到合约：{vt_symbol}", algo)

        return contract

    def write_log(self, msg: str, algo: AlgoTemplate = None) -> None:
        """"""
        if algo:
            msg: str = f"{algo.algo_name}：{msg}"

        log: LogData = LogData(msg=msg, gateway_name=APP_NAME)
        event: Event = Event(EVENT_ALGO_LOG, data=log)
        self.event_engine.put(event)

    def put_setting_event(self, setting_name: str, setting: dict) -> None:
        """"""
        event: Event = Event(EVENT_ALGO_SETTING)
        event.data = {
            "setting_name": setting_name,
            "setting": setting
        }
        self.event_engine.put(event)

    def update_algo_setting(self, setting_name: str, setting: dict) -> None:
        """"""
        self.algo_settings[setting_name] = setting

        self.save_algo_setting()

        self.put_setting_event(setting_name, setting)

    def remove_algo_setting(self, setting_name: str) -> None:
        """"""
        if setting_name not in self.algo_settings:
            return
        self.algo_settings.pop(setting_name)

        event: Event = Event(EVENT_ALGO_SETTING)
        event.data = {
            "setting_name": setting_name,
            "setting": None
        }
        self.event_engine.put(event)

        self.save_algo_setting()

    def put_parameters_event(self, algo: AlgoTemplate, parameters: dict) -> None:
        """"""
        event: Event = Event(EVENT_ALGO_PARAMETERS)
        event.data = {
            "algo_name": algo.algo_name,
            "parameters": parameters
        }
        self.event_engine.put(event)

    def put_variables_event(self, algo: AlgoTemplate, variables: dict) -> None:
        """"""
        # 检查算法是否运行结束
        if not variables["active"] and algo in self.algos:
            self.algos.pop(algo.algo_name)

            for algos in self.symbol_algo_map.values():
                if algo in algos:
                    algos.remove(algo)

        # 推送事件
        event: Event = Event(EVENT_ALGO_VARIABLES)
        event.data = {
            "algo_name": algo.algo_name,
            "variables": variables
        }
        self.event_engine.put(event)
