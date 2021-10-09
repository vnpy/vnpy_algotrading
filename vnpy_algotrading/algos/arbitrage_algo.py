from vnpy.trader.constant import Direction
from vnpy.trader.object import TradeData, OrderData
from vnpy.trader.engine import BaseEngine

from ..template import AlgoTemplate


class ArbitrageAlgo(AlgoTemplate):
    """"""

    display_name = "Arbitrage 套利"

    default_setting = {
        "active_vt_symbol": "",
        "passive_vt_symbol": "",
        "spread_up": 0.0,
        "spread_down": 0.0,
        "max_pos": 0,
        "interval": 0,
    }

    variables = [
        "timer_count",
        "active_vt_orderid",
        "passive_vt_orderid",
        "active_pos",
        "passive_pos"
    ]

    def __init__(
        self,
        algo_engine: BaseEngine,
        algo_name: str,
        setting: dict
    ):
        """"""
        super().__init__(algo_engine, algo_name, setting)

        # 参数
        self.active_vt_symbol = setting["active_vt_symbol"]
        self.passive_vt_symbol = setting["passive_vt_symbol"]
        self.spread_up = setting["spread_up"]
        self.spread_down = setting["spread_down"]
        self.max_pos = setting["max_pos"]
        self.interval = setting["interval"]

        # 变量
        self.active_vt_orderid = ""
        self.passive_vt_orderid = ""
        self.active_pos = 0
        self.passive_pos = 0
        self.timer_count = 0

        self.subscribe(self.active_vt_symbol)
        self.subscribe(self.passive_vt_symbol)

        self.put_parameters_event()
        self.put_variables_event()

    def on_stop(self):
        """"""
        self.write_log("停止算法")

    def on_order(self, order: OrderData):
        """"""
        if order.vt_symbol == self.active_vt_symbol:
            if not order.is_active():
                self.active_vt_orderid = ""
        elif order.vt_symbol == self.passive_vt_symbol:
            if not order.is_active():
                self.passive_vt_orderid = ""
        self.put_variables_event()

    def on_trade(self, trade: TradeData):
        """"""
        # 更新持仓
        if trade.direction == Direction.LONG:
            if trade.vt_symbol == self.active_vt_symbol:
                self.active_pos += trade.volume
            else:
                self.passive_pos += trade.volume
        else:
            if trade.vt_symbol == self.active_vt_symbol:
                self.active_pos -= trade.volume
            else:
                self.passive_pos -= trade.volume

        # 主动腿成交，执行对冲
        if trade.vt_symbol == self.active_vt_symbol:
            self.write_log("收到主动腿成交回报，执行对冲")
            self.hedge()

        self.put_variables_event()

    def on_timer(self):
        """"""
        # 定时执行算法
        self.timer_count += 1
        if self.timer_count < self.interval:
            self.put_variables_event()
            return
        self.timer_count = 0

        # 继续运行前撤销所有活动中订单
        if self.active_vt_orderid or self.passive_vt_orderid:
            self.write_log("有未成交委托，执行撤单")
            self.cancel_all()
            return

        # 确保主动腿和被动腿完全对冲
        if (self.active_pos + self.passive_pos) != 0:
            self.write_log("主动腿和被动腿数量不一致，执行对冲")
            self.hedge()
            return

        # 确保两条套利腿的行情数据都通畅
        active_tick = self.get_tick(self.active_vt_symbol)
        passive_tick = self.get_tick(self.passive_vt_symbol)
        if not active_tick or not passive_tick:
            self.write_log("获取某条套利腿的行情失败，无法交易")
            return

        # 计算价差
        spread_bid_price = active_tick.bid_price_1 - passive_tick.ask_price_1
        spread_ask_price = active_tick.ask_price_1 - passive_tick.bid_price_1

        spread_bid_volume = min(active_tick.bid_volume_1,
                                passive_tick.ask_volume_1)
        spread_ask_volume = min(active_tick.ask_volume_1,
                                passive_tick.bid_volume_1)

        msg = f"价差盘口，买：{spread_bid_price} ({spread_bid_volume})，卖：{spread_ask_price} ({spread_ask_volume})"
        self.write_log(msg)

        # 做空条件
        if spread_bid_price > self.spread_up:
            self.write_log("套利价差超过上限，满足做空条件")

            if self.active_pos > -self.max_pos:
                self.write_log("当前持仓小于最大持仓限制，执行卖出操作")

                volume = min(spread_bid_volume,
                             self.active_pos + self.max_pos)

                self.active_vt_orderid = self.sell(
                    self.active_vt_symbol,
                    active_tick.bid_price_1,
                    volume
                )

        # 做多条件
        elif spread_ask_price < -self.spread_down:
            self.write_log("套利价差超过下限，满足做多条件")

            if self.active_pos < self.max_pos:
                self.write_log("当前持仓小于最大持仓限制，执行买入操作")

                volume = min(spread_ask_volume,
                             self.max_pos - self.active_pos)

                self.active_vt_orderid = self.buy(
                    self.active_vt_symbol,
                    active_tick.ask_price_1,
                    volume
                )

        self.put_variables_event()

    def hedge(self):
        """对冲"""
        tick = self.get_tick(self.passive_vt_symbol)
        volume = -self.active_pos - self.passive_pos

        if volume > 0:
            self.passive_vt_orderid = self.buy(
                self.passive_vt_symbol,
                tick.ask_price_1,
                volume
            )
        elif volume < 0:
            self.passive_vt_orderid = self.sell(
                self.passive_vt_symbol,
                tick.bid_price_1,
                abs(volume)
            )
