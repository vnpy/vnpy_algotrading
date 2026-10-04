"""算法交易的事件名、应用名和状态。"""
from enum import Enum


EVENT_ALGO_LOG: str = "eAlgoLog"
EVENT_ALGO_UPDATE: str = "eAlgoUpdate"


APP_NAME: str = "AlgoTrading"


class AlgoStatus(Enum):
    """算法状态"""

    RUNNING = "运行"
    PAUSED = "暂停"
    STOPPED = "停止"
    FINISHED = "结束"
