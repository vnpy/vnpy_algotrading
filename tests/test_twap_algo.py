from datetime import datetime

from vnpy.trader.constant import Direction, Exchange, Offset, OrderType, Product, Status
from vnpy.trader.object import ContractData, OrderData, TickData, TradeData

from vnpy_algotrading.algos.twap_algo import TwapAlgo
from vnpy_algotrading.base import AlgoStatus
from vnpy_algotrading.template import AlgoTemplate


ChildOrder = tuple[str, Direction, float, float, OrderType, Offset]


class FakeAlgoEngine:
    def __init__(self) -> None:
        self.orders: list[ChildOrder] = []
        self.cancels: list[str] = []
        self.tick: TickData | None = None
        self.contract: ContractData | None = None
        self._next_order: int = 0

    def send_order(
        self,
        algo: AlgoTemplate,
        direction: Direction,
        price: float,
        volume: float,
        order_type: OrderType,
        offset: Offset,
    ) -> str:
        self._next_order += 1
        vt_orderid: str = f"FAKE.{self._next_order}"
        self.orders.append((vt_orderid, direction, price, volume, order_type, offset))
        return vt_orderid

    def cancel_order(self, algo: AlgoTemplate, vt_orderid: str) -> None:
        self.cancels.append(vt_orderid)

    def get_tick(self, algo: AlgoTemplate) -> TickData | None:
        return self.tick

    def get_contract(self, algo: AlgoTemplate) -> ContractData | None:
        return self.contract

    def write_log(self, msg: str, algo: AlgoTemplate | None = None) -> None:
        return

    def put_algo_event(self, algo: AlgoTemplate, data: dict) -> None:
        return


def advance(algo: TwapAlgo, steps: int) -> None:
    for _step in range(steps):
        algo.update_timer()


def make_twap(
    volume: float,
    time: int,
    interval: int,
    price: float,
    direction: Direction = Direction.LONG,
    offset: Offset = Offset.OPEN,
    min_volume: float = 1,
    ask_price: float = 0,
    bid_price: float = 0,
    running: bool = True,
) -> tuple[TwapAlgo, FakeAlgoEngine]:
    engine: FakeAlgoEngine = FakeAlgoEngine()
    engine.contract = ContractData(
        gateway_name="FAKE",
        symbol="ag2506",
        exchange=Exchange.SHFE,
        name="ag2506",
        product=Product.FUTURES,
        size=15,
        pricetick=1,
        min_volume=min_volume,
    )
    engine.tick = TickData(
        gateway_name="FAKE",
        symbol="ag2506",
        exchange=Exchange.SHFE,
        datetime=datetime(2024, 1, 2, 9, 0),
        ask_price_1=ask_price,
        bid_price_1=bid_price,
    )
    algo: TwapAlgo = TwapAlgo(
        engine,
        "TwapAlgo_test",
        "ag2506.SHFE",
        direction,
        offset,
        price,
        volume,
        {"time": time, "interval": interval},
    )
    if running:
        algo.start()
    return algo, engine


def test_twap_slices_parent_until_time_expires() -> None:
    price: float = 10.5
    algo, engine = make_twap(
        volume=30,
        time=90,
        interval=30,
        price=price,
        ask_price=price,
    )

    assert algo.status == AlgoStatus.RUNNING
    assert algo.order_volume == 10

    advance(algo, 29)
    assert engine.orders == []
    assert algo.total_count == 29
    assert algo.status == AlgoStatus.RUNNING

    advance(algo, 1)
    assert engine.orders == [
        ("FAKE.1", Direction.LONG, price, 10, OrderType.LIMIT, Offset.OPEN),
    ]

    resting: OrderData = OrderData(
        gateway_name="FAKE",
        symbol="ag2506",
        exchange=Exchange.SHFE,
        orderid="1",
        direction=Direction.LONG,
        price=price,
        volume=10,
        status=Status.NOTTRADED,
    )
    algo.update_order(resting)
    assert resting.vt_orderid in algo.active_orders

    advance(algo, 30)
    assert engine.cancels == ["FAKE.1"]
    assert engine.orders == [
        ("FAKE.1", Direction.LONG, price, 10, OrderType.LIMIT, Offset.OPEN),
        ("FAKE.2", Direction.LONG, price, 10, OrderType.LIMIT, Offset.OPEN),
    ]
    assert algo.status == AlgoStatus.RUNNING
    assert algo.traded == 0

    # total_count 到达 time 时先结束，这一拍不再发子单。
    advance(algo, 30)
    assert algo.total_count == 90
    assert algo.status == AlgoStatus.FINISHED
    assert len(engine.orders) == 2
    assert sum(item[3] for item in engine.orders) == 20

    advance(algo, 5)
    assert len(engine.orders) == 2
    assert algo.status == AlgoStatus.FINISHED


def test_twap_rounds_slice_and_caps_it_by_remaining_volume() -> None:
    price: float = 7
    algo, engine = make_twap(
        volume=30,
        time=70,
        interval=30,
        price=price,
        ask_price=price,
    )

    assert algo.order_volume == 13

    advance(algo, 30)
    assert engine.orders == [
        ("FAKE.1", Direction.LONG, price, 13, OrderType.LIMIT, Offset.OPEN),
    ]

    algo.update_trade(
        TradeData(
            gateway_name="FAKE",
            symbol="ag2506",
            exchange=Exchange.SHFE,
            orderid="1",
            tradeid="t1",
            direction=Direction.LONG,
            price=price,
            volume=20,
        )
    )
    assert algo.traded == 20
    assert algo.traded_price == price
    assert algo.status == AlgoStatus.RUNNING

    advance(algo, 30)
    assert engine.orders[1] == (
        "FAKE.2",
        Direction.LONG,
        price,
        10,
        OrderType.LIMIT,
        Offset.OPEN,
    )
    assert algo.total_count == 60

    advance(algo, 10)
    assert algo.total_count == 70
    assert algo.status == AlgoStatus.FINISHED
    assert len(engine.orders) == 2
    assert [item[3] for item in engine.orders] == [13, 10]


def test_twap_skips_child_until_ask_is_within_limit() -> None:
    price: float = 20
    algo, engine = make_twap(
        volume=50,
        time=100,
        interval=20,
        price=price,
        ask_price=price + 1,
    )
    assert algo.order_volume == 10

    advance(algo, 20)
    assert engine.orders == []
    assert algo.timer_count == 0
    assert algo.total_count == 20
    assert algo.status == AlgoStatus.RUNNING

    assert engine.tick is not None
    engine.tick.ask_price_1 = price
    advance(algo, 20)

    assert engine.orders == [
        ("FAKE.1", Direction.LONG, price, 10, OrderType.LIMIT, Offset.OPEN),
    ]
    assert algo.status == AlgoStatus.RUNNING
    assert algo.traded == 0


def test_twap_short_slices_when_bid_reaches_price() -> None:
    price: float = 8
    algo, engine = make_twap(
        volume=20,
        time=50,
        interval=20,
        price=price,
        direction=Direction.SHORT,
        offset=Offset.CLOSE,
        bid_price=price,
        running=False,
    )
    assert algo.order_volume == 8

    advance(algo, 20)
    assert algo.status == AlgoStatus.PAUSED
    assert algo.timer_count == 0
    assert algo.total_count == 0
    assert engine.orders == []

    algo.start()
    advance(algo, 20)
    assert engine.orders == [
        ("FAKE.1", Direction.SHORT, price, 8, OrderType.LIMIT, Offset.CLOSE),
    ]

    advance(algo, 20)
    assert algo.status == AlgoStatus.RUNNING
    assert algo.total_count == 40
    assert engine.orders == [
        ("FAKE.1", Direction.SHORT, price, 8, OrderType.LIMIT, Offset.CLOSE),
        ("FAKE.2", Direction.SHORT, price, 8, OrderType.LIMIT, Offset.CLOSE),
    ]

    advance(algo, 10)
    assert algo.total_count == 50
    assert algo.status == AlgoStatus.FINISHED
    assert len(engine.orders) == 2


def test_twap_rounds_odd_slice_down_to_min_volume() -> None:
    price: float = 4
    algo, engine = make_twap(
        volume=10,
        time=31,
        interval=10,
        price=price,
        ask_price=price,
        min_volume=1,
    )

    assert algo.order_volume == 3

    advance(algo, 30)
    assert [item[3] for item in engine.orders] == [3, 3, 3]
    assert {item[2] for item in engine.orders} == {price}
    assert {item[1] for item in engine.orders} == {Direction.LONG}
    assert algo.status == AlgoStatus.RUNNING

    advance(algo, 1)
    assert algo.total_count == 31
    assert algo.status == AlgoStatus.FINISHED
    assert len(engine.orders) == 3
