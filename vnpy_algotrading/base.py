from enum import Enum


EVENT_ALGO_LOG = "eAlgoLog"
EVENT_ALGO_UPDATE = "eAlgoUpdate"


APP_NAME = "AlgoTrading"


class AlgoStatus(Enum):
    """算法状态"""

    RUNNING = "运行"
    PAUSED = "暂停"
    STOPPED = "停止"
    FINISHED = "结束"
