import csv
from functools import partial
from datetime import datetime
from typing import Any, Dict, Optional

from vnpy.event import EventEngine, Event
from vnpy.trader.engine import MainEngine, LogData
from vnpy.trader.ui import QtWidgets, QtCore

from ..engine import (
    AlgoEngine,
    AlgoTemplate,
    APP_NAME,
    EVENT_ALGO_LOG,
    EVENT_ALGO_PARAMETERS,
    EVENT_ALGO_VARIABLES,
    AlgoStatus,
    Direction,
    Offset
)
from .display import NAME_DISPLAY_MAP


class AlgoWidget(QtWidgets.QWidget):
    """算法启动控件"""

    def __init__(
        self,
        algo_engine: AlgoEngine,
        algo_template: AlgoTemplate
    ) -> None:
        """构造函数"""
        super().__init__()

        self.algo_engine: AlgoEngine = algo_engine
        self.template_name: str = algo_template.__name__

        self.default_setting: dict = {
            "vt_symbol": "",
            "direction": [
                Direction.LONG.value,
                Direction.SHORT.value
            ],
            "offset": [
                Offset.NONE.value,
                Offset.OPEN.value,
                Offset.CLOSE.value,
                Offset.CLOSETODAY.value,
                Offset.CLOSEYESTERDAY.value
            ],
            "price": 0.0,
            "volume": 0,
        }
        self.default_setting.update(algo_template.default_setting)

        self.widgets: dict = {}

        self.init_ui()

    def init_ui(self) -> None:
        """使用默认配置初始化输入框和表单布局"""
        self.setMaximumWidth(400)

        form: QtWidgets.QFormLayout = QtWidgets.QFormLayout()

        for field_name, field_value in self.default_setting.items():
            field_type: Any = type(field_value)

            if field_type == list:
                widget: QtWidgets.QComboBox = QtWidgets.QComboBox()
                widget.addItems(field_value)
            else:
                widget: QtWidgets.QLineEdit = QtWidgets.QLineEdit()

            display_name: str = NAME_DISPLAY_MAP.get(field_name, field_name)

            form.addRow(display_name, widget)
            self.widgets[field_name] = (widget, field_type)

        start_algo_button: QtWidgets.QPushButton = QtWidgets.QPushButton("启动算法")
        start_algo_button.clicked.connect(self.start_algo)
        form.addRow(start_algo_button)

        load_csv_button: QtWidgets.QPushButton = QtWidgets.QPushButton("CSV启动")
        load_csv_button.clicked.connect(self.load_csv)
        form.addRow(load_csv_button)

        form.addRow(QtWidgets.QLabel(""))
        form.addRow(QtWidgets.QLabel(""))
        form.addRow(QtWidgets.QLabel(""))

        for button in [
            start_algo_button,
            load_csv_button
        ]:
            button.setFixedHeight(button.sizeHint().height() * 2)

        self.setLayout(form)

    def load_csv(self) -> None:
        """加载CSV文件中的算法配置"""
        # 从对话框获取csv地址
        path, type_ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            u"加载算法配置",
            "",
            "CSV(*.csv)"
        )

        if not path:
            return

        # 创建csv DictReader
        with open(path, "r") as f:
            buf: list = [line for line in f]
            reader: csv.DictReader = csv.DictReader(buf)

        # 检查csv文件是否有字段缺失
        for field_name in self.widgets.keys():
            if field_name not in reader.fieldnames:
                QtWidgets.QMessageBox.warning(
                    self,
                    "字段缺失",
                    f"CSV文件缺失算法{self.template_name}所需字段{field_name}"
                )
                return

        settings: list = []

        for d in reader:
            # 用模版名初始化算法配置
            setting: dict = {
                "template_name": self.template_name
            }

            # 读取csv文件每行中各个字段内容
            for field_name, tp in self.widgets.items():
                field_type: Any = tp[-1]
                field_text: str = d[field_name]

                if field_type == list:
                    field_value = field_text
                else:
                    try:
                        field_value = field_type(field_text)
                    except ValueError:
                        QtWidgets.QMessageBox.warning(
                            self,
                            "参数错误",
                            f"{field_name}参数类型应为{field_type}，请检查！"
                        )
                        return

                setting[field_name] = field_value

            # 将setting添加到settings
            settings.append(setting)

        # 当没有错误发生时启动算法
        for setting in settings:
            vt_symbol: str = setting.pop("vt_symbol")
            direction: Direction = Direction(setting.pop("direction"))
            offset: Offset = Offset(setting.pop("offset"))
            price: float = setting.pop("price")
            volume: float = setting.pop("volume")
            self.algo_engine.start_algo(vt_symbol, direction, offset, price, volume, setting)

    def get_setting(self) -> dict:
        """获取当前配置"""
        setting: dict = {"template_name": self.template_name}

        for field_name, tp in self.widgets.items():
            widget, field_type = tp
            if field_type == list:
                field_value: str = str(widget.currentText())
            else:
                try:
                    field_value: Any = field_type(widget.text())
                except ValueError:
                    display_name: str = NAME_DISPLAY_MAP.get(field_name, field_name)
                    QtWidgets.QMessageBox.warning(
                        self,
                        "参数错误",
                        f"{display_name}参数类型应为{field_type}，请检查！"
                    )
                    return None

            setting[field_name] = field_value

        return setting

    def start_algo(self) -> None:
        """启动交易算法"""
        setting: dict = self.get_setting()

        if setting:
            vt_symbol: str = setting.pop("vt_symbol")
            direction: Direction = Direction(setting.pop("direction"))
            offset: Offset = Offset(setting.pop("offset"))
            price: float = setting.pop("price")
            volume: int = setting.pop("volume")
            self.algo_engine.start_algo(vt_symbol, direction, offset, price, volume, setting)


class AlgoMonitor(QtWidgets.QTableWidget):
    """算法监控组件"""

    parameters_signal: QtCore.pyqtSignal = QtCore.pyqtSignal(Event)
    variables_signal: QtCore.pyqtSignal = QtCore.pyqtSignal(Event)

    def __init__(
        self,
        algo_engine: AlgoEngine,
        event_engine: EventEngine,
        mode_active: bool
    ):
        """"""
        super().__init__()

        self.algo_engine: AlgoEngine = algo_engine
        self.event_engine: EventEngine = event_engine
        self.mode_active: bool = mode_active

        self.algo_cells: dict = {}

        self.init_ui()
        self.register_event()

    def init_ui(self) -> None:
        """"""
        labels: list = [
            "",
            "",
            "算法",
            "本地代码",
            "方向",
            "开平",
            "价格",
            "数量",
            "参数",
            "状态"
        ]
        self.setColumnCount(len(labels))
        self.setHorizontalHeaderLabels(labels)
        self.verticalHeader().setVisible(False)
        self.setEditTriggers(self.NoEditTriggers)

        self.verticalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeToContents
        )

        for column in range(8, 10):
            self.horizontalHeader().setSectionResizeMode(
                column,
                QtWidgets.QHeaderView.Stretch
            )
        self.setWordWrap(True)

        if not self.mode_active:
            self.hideColumn(0)
            self.hideColumn(1)

    def register_event(self) -> None:
        """"""
        self.parameters_signal.connect(self.process_parameters_event)
        self.variables_signal.connect(self.process_variables_event)

        self.event_engine.register(
            EVENT_ALGO_PARAMETERS, self.parameters_signal.emit)
        self.event_engine.register(
            EVENT_ALGO_VARIABLES, self.variables_signal.emit)

    def process_parameters_event(self, event: Event) -> None:
        """"""
        data: Any = event.data
        algo_name: str = data["algo_name"]
        vt_symbol: str = data["vt_symbol"]
        direction: str = data["direction"].value
        offset: str = data["offset"].value
        price: str = str(data["price"])
        volume: str = str(data["volume"])
        parameters: dict = data["parameters"]

        cells: dict = self.get_algo_cells(algo_name)

        cells["vt_symbol"].setText(vt_symbol)
        cells["direction"].setText(direction)
        cells["offset"].setText(offset)
        cells["price"].setText(price)
        cells["volume"].setText(volume)

        text: str = to_text(parameters)
        cells["parameters"].setText(text)

    def process_variables_event(self, event: Event) -> None:
        """"""
        data: Any = event.data
        algo_name: str = data["algo_name"]
        variables: dict = data["variables"]

        cells: dict = self.get_algo_cells(algo_name)
        variables_cell: Optional[QtWidgets.QTableWidgetItem] = cells["variables"]
        text: str = to_text(variables)
        variables_cell.setText(text)

        row: int = self.row(variables_cell)
        active: bool = variables["status"] not in [AlgoStatus.STOPPED, AlgoStatus.FINISHED]

        if self.mode_active:
            if active:
                self.showRow(row)
            else:
                self.hideRow(row)
        else:
            if active:
                self.hideRow(row)
            else:
                self.showRow(row)

    def stop_algo(self, algo_name: str) -> None:
        """"""
        self.algo_engine.stop_algo(algo_name)

    def switch(self, algo_name: str) -> None:
        """"""
        button: QtWidgets.QPushButton = self.algo_cells[algo_name]["button"]
        if button.text() == "暂停":
            self.algo_engine.pause_algo(algo_name)
            button.setText("启动")
        else:
            self.algo_engine.resume_algo(algo_name)
            button.setText("暂停")

        self.algo_cells[algo_name]["button"] = button

    def get_algo_cells(self, algo_name: str) -> dict:
        """"""
        cells: Optional[dict] = self.algo_cells.get(algo_name, None)

        if not cells:
            stop_func = partial(self.stop_algo, algo_name=algo_name)
            stop_button: QtWidgets.QPushButton = QtWidgets.QPushButton("停止")
            stop_button.clicked.connect(stop_func)

            # 初始化时先设置暂停按钮
            switch_func = partial(self.switch, algo_name=algo_name)
            switch_button: QtWidgets.QPushButton = QtWidgets.QPushButton("暂停")
            switch_button.clicked.connect(switch_func)

            name_cell: QtWidgets.QTableWidgetItem = QtWidgets.QTableWidgetItem(algo_name)
            name_cell.setTextAlignment(QtCore.Qt.AlignCenter)

            vtsymbol_cell: QtWidgets.QTableWidgetItem = QtWidgets.QTableWidgetItem()
            vtsymbol_cell.setTextAlignment(QtCore.Qt.AlignCenter)
            direction_cell: QtWidgets.QTableWidgetItem = QtWidgets.QTableWidgetItem()
            direction_cell.setTextAlignment(QtCore.Qt.AlignCenter)
            offset_cell: QtWidgets.QTableWidgetItem = QtWidgets.QTableWidgetItem()
            offset_cell.setTextAlignment(QtCore.Qt.AlignCenter)
            price_cell: QtWidgets.QTableWidgetItem = QtWidgets.QTableWidgetItem()
            price_cell.setTextAlignment(QtCore.Qt.AlignCenter)
            volume_cell: QtWidgets.QTableWidgetItem = QtWidgets.QTableWidgetItem()
            volume_cell.setTextAlignment(QtCore.Qt.AlignCenter)

            parameters_cell: QtWidgets.QTableWidgetItem = QtWidgets.QTableWidgetItem()
            variables_cell: QtWidgets.QTableWidgetItem = QtWidgets.QTableWidgetItem()

            self.insertRow(0)
            self.setCellWidget(0, 0, stop_button)
            self.setCellWidget(0, 1, switch_button)
            self.setItem(0, 2, name_cell)
            self.setItem(0, 3, vtsymbol_cell)
            self.setItem(0, 4, direction_cell)
            self.setItem(0, 5, offset_cell)
            self.setItem(0, 6, price_cell)
            self.setItem(0, 7, volume_cell)
            self.setItem(0, 8, parameters_cell)
            self.setItem(0, 9, variables_cell)

            cells: dict = {
                "name": name_cell,
                "vt_symbol": vtsymbol_cell,
                "direction": direction_cell,
                "offset": offset_cell,
                "price": price_cell,
                "volume": volume_cell,
                "parameters": parameters_cell,
                "variables": variables_cell,
                "button": switch_button        # 缓存对应algo_name的button进字典便于更新按钮状态
            }
            self.algo_cells[algo_name] = cells

        return cells


class ActiveAlgoMonitor(AlgoMonitor):
    """活动算法监控组件"""

    def __init__(self, algo_engine: AlgoEngine, event_engine: EventEngine) -> None:
        """"""
        super().__init__(algo_engine, event_engine, True)


class InactiveAlgoMonitor(AlgoMonitor):
    """结束算法监控组件"""

    def __init__(self, algo_engine: AlgoEngine, event_engine: EventEngine) -> None:
        """"""
        super().__init__(algo_engine, event_engine, False)


class LogMonitor(QtWidgets.QTableWidget):
    """日志组件"""

    signal: QtCore.pyqtSignal = QtCore.pyqtSignal(Event)

    def __init__(self, event_engine: EventEngine) -> None:
        """"""
        super().__init__()

        self.event_engine: EventEngine = event_engine

        self.init_ui()
        self.register_event()

    def init_ui(self) -> None:
        """"""
        labels: list = [
            "时间",
            "信息"
        ]
        self.setColumnCount(len(labels))
        self.setHorizontalHeaderLabels(labels)
        self.verticalHeader().setVisible(False)
        self.setEditTriggers(self.NoEditTriggers)

        self.verticalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeToContents
        )

        self.horizontalHeader().setSectionResizeMode(
            1,
            QtWidgets.QHeaderView.Stretch
        )
        self.setWordWrap(True)

    def register_event(self) -> None:
        """"""
        self.signal.connect(self.process_log_event)

        self.event_engine.register(EVENT_ALGO_LOG, self.signal.emit)

    def process_log_event(self, event: Event) -> None:
        """"""
        log: LogData = event.data
        msg: str = log.msg
        timestamp: str = datetime.now().strftime("%H:%M:%S")

        timestamp_cell: QtWidgets.QTableWidgetItem = QtWidgets.QTableWidgetItem(timestamp)
        msg_cell: QtWidgets.QTableWidgetItem = QtWidgets.QTableWidgetItem(msg)

        self.insertRow(0)
        self.setItem(0, 0, timestamp_cell)
        self.setItem(0, 1, msg_cell)


class AlgoManager(QtWidgets.QWidget):
    """算法交易管理控件"""

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine) -> None:
        """"""
        super().__init__()

        self.main_engine: MainEngine = main_engine
        self.event_engine: EventEngine = event_engine
        self.algo_engine: AlgoEngine = main_engine.get_engine(APP_NAME)

        self.algo_widgets: Dict[str, AlgoWidget] = {}

        self.init_ui()
        self.algo_engine.init_engine()

    def init_ui(self) -> None:
        """"""
        self.setWindowTitle("算法交易")

        # 左边控制控件
        self.template_combo: QtWidgets.QComboBox = QtWidgets.QComboBox()
        self.template_combo.currentIndexChanged.connect(self.show_algo_widget)

        form: QtWidgets.QFormLayout = QtWidgets.QFormLayout()
        form.addRow("算法", self.template_combo)
        widget: QtWidgets.QWidget = QtWidgets.QWidget()
        widget.setLayout(form)

        vbox: QtWidgets.QVBoxLayout = QtWidgets.QVBoxLayout()
        vbox.addWidget(widget)

        algo_templates: dict = self.algo_engine.get_algo_template()
        for algo_template in algo_templates.values():
            widget: AlgoWidget = AlgoWidget(self.algo_engine, algo_template)
            vbox.addWidget(widget)

            template_name: str = algo_template.__name__
            display_name: str = algo_template.display_name

            self.algo_widgets[template_name] = widget
            self.template_combo.addItem(display_name, template_name)

        vbox.addStretch()

        stop_all_button: QtWidgets.QPushButton = QtWidgets.QPushButton("全部停止")
        stop_all_button.setFixedHeight(stop_all_button.sizeHint().height() * 2)
        stop_all_button.clicked.connect(self.algo_engine.stop_all)

        vbox.addWidget(stop_all_button)

        # 右边监控控件
        active_algo_monitor: ActiveAlgoMonitor = ActiveAlgoMonitor(
            self.algo_engine, self.event_engine
        )
        inactive_algo_monitor: InactiveAlgoMonitor = InactiveAlgoMonitor(
            self.algo_engine, self.event_engine
        )
        tab1: QtWidgets.QTabWidget = QtWidgets.QTabWidget()
        tab1.addTab(active_algo_monitor, "执行中")
        tab1.addTab(inactive_algo_monitor, "已结束")

        log_monitor: LogMonitor = LogMonitor(self.event_engine)
        tab2: QtWidgets.QTabWidget = QtWidgets.QTabWidget()
        tab2.addTab(log_monitor, "日志")

        vbox2: QtWidgets.QVBoxLayout = QtWidgets.QVBoxLayout()
        vbox2.addWidget(tab1)
        vbox2.addWidget(tab2)

        hbox2: QtWidgets.QHBoxLayout = QtWidgets.QHBoxLayout()
        hbox2.addLayout(vbox)
        hbox2.addLayout(vbox2)
        self.setLayout(hbox2)

        self.show_algo_widget()

    def show_algo_widget(self) -> None:
        """"""
        ix: int = self.template_combo.currentIndex()
        current_name: Any = self.template_combo.itemData(ix)

        for template_name, widget in self.algo_widgets.items():
            if template_name == current_name:
                widget.show()
            else:
                widget.hide()

    def show(self) -> None:
        """"""
        self.showMaximized()


def to_text(data: dict) -> str:
    """将字典数据转化为字符串数据"""
    buf: list = []
    for key, value in data.items():
        key: str = NAME_DISPLAY_MAP.get(key, key)
        buf.append(f"{key}：{value}")
    text: str = "，".join(buf)
    return text
