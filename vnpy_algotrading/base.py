from enum import Enum


EVENT_ALGO_LOG = "eAlgoLog"
EVENT_ALGO_SETTING = "eAlgoSetting"
EVENT_ALGO_VARIABLES = "eAlgoVariables"
EVENT_ALGO_PARAMETERS = "eAlgoParameters"

APP_NAME = "AlgoTrading"


class AlgoStatus(Enum):
    """
    Algo status.
    """
    RUNNING = "运行中"
    PAUSED = "暂停"
    TERMINATED = "终止"
    FINISHED = "结束"

    def is_active(self) -> bool:
        """
        Check if the algo is active.
        """
        return self == AlgoStatus.RUNNING
