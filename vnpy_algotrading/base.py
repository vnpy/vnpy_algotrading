from enum import Enum


EVENT_ALGO_LOG = "eAlgoLog"
EVENT_ALGO_SETTING = "eAlgoSetting"
EVENT_ALGO_VARIABLES = "eAlgoVariables"
EVENT_ALGO_PARAMETERS = "eAlgoParameters"

APP_NAME = "AlgoTrading"


class AlgoStatus(Enum):
    """
    Order status.
    """
    RUNNING = "运行中"
    PAUSED = "暂停"
    STOPPED = "停止"
