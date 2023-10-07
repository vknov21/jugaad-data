from PyQt5 import QtCore, QtGui, QtWidgets, QtTest
from PyQt5.QtCore import QSize, Qt, QObject, pyqtSignal
import threading
import time
from PyQt5.QtGui import QPainter, QPen, QPainterPath, QBrush, QFontMetrics
import math
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QMenu, QAction
import sys


class MyMainWindow(QtWidgets.QMainWindow):
    def __init__(self, workerThread, mouseClickCallable=None, scrollWheelCallable=None, sides=(106, 20), *args, **kwargs):
        # Add Windows Types:
        # .... QtCore.Qt.WindowType.Tool to make it a Dialog instead of a Window
        # .... QtCore.Qt.WindowType.WindowStaysOnTopHint to keep it always at top
        # .... QtCore.Qt.WindowType.FramelessWindowHint to remove title bar to reduce unnecessary space
        up_threshold = kwargs.get('up_threshold', 0)
        down_threshold = kwargs.get('down_threshold', 0)
        kwargs.pop('up_threshold', 0)
        kwargs.pop('down_threshold', 0)
        super().__init__(flags=QtCore.Qt.WindowType.Tool | QtCore.Qt.WindowType.WindowStaysOnTopHint | QtCore.Qt.WindowType.FramelessWindowHint, *args, **kwargs)
        # Get the workerThread which will tasked in updating the label message with the fed refresh rate
        self.worker_thread = workerThread
        self.mousePressPos = None
        self.windowPos = None
        # Context Menu
        self.context_menu = QMenu(self)
        # Create actions for the context menu
        self.set_on_top_action = QAction("Always on Top", self)
        self.set_on_top_action.setCheckable(True)
        self.set_on_top_action.setChecked(True)
        self.refresh_action = QAction("Refresh Page", self)
        self.context_menu.addAction(self.set_on_top_action)
        self.context_menu.addAction(self.refresh_action)
        # Mouse enter Event
        self.central_widget = QtWidgets.QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.ui = Ui_Dialog(self, workerThread, mouseClickCallable, scrollWheelCallable)
        self.label = self.ui.label
        self.label.up_threshold = up_threshold
        self.label.down_threshold = down_threshold
        # See through factor
        self.setWindowOpacity(0.8)
        self.opacity = self.windowOpacity()
        # Resizes as per the amount provided during initialization. The sides are provided in width and height
        self.resize(sides[0], sides[1])

    def closeEvent(self, event):
        # Send signal to exit the thread, otherwise, the application doesn't exist, if workerThread is meant to run for infinite times
        self.worker_thread.stop(self)

    def enterEvent(self, event):
        # Trigger your desired action when the mouse enters the window
        self.opacity = self.windowOpacity()
        self.setWindowOpacity(1.0)

    def leaveEvent(self, event):
        # Trigger your desired action when the mouse leaves the main window
        self.setWindowOpacity(self.opacity)
        self.opacity = self.windowOpacity()


class Ui_Dialog():
    def __init__(self, MainWindow, workerThread, mouseClickCallable, scrollWheelCallable, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Stores the workerThread, MainWindiw instances
        self.workerThread = workerThread
        self.MainWindow = MainWindow
        self.mouseClickCallable = mouseClickCallable
        self.scrollWheelCallable = scrollWheelCallable
        # Window select and move operation's initialization
        self.mousePressPos = None
        self.windowPos = None
        self.resizing = False
        self.resize_start_pos = None
        # Mouse double click verification
        self.single_click = False
        self.click_timer = None
        # Scroll page initialization
        self.wheel_count = 0
        self.scroll_timer = None
        self.triggered_callable = False
        # Mouse Click Event Initialization
        self.clicked_pos_x = None
        self.clicked_pos_y = None
        self.context_menu = MainWindow.context_menu
        MainWindow.set_on_top_action.triggered.connect(self.toggle_always_on_top)
        self.setupUi(MainWindow)
        MainWindow.refresh_action.triggered.connect(self.refresh_action)
        self.workerThread.windowResized.connect(self.resizeMainWindow)

    # Define the slot function
    def resizeMainWindow(self, width, height):
        self.MainWindow.resize(width, height)

    def object_mouse_event(self, obj):
        obj.mousePressEvent = lambda event, obj=obj: self.mousePressEvent(event, obj)
        obj.mouseMoveEvent = lambda event, obj=obj: self.mouseMoveEvent(event, obj)
        obj.mouseReleaseEvent = lambda event, obj=obj: self.mouseReleaseEvent(event, obj)
        obj.mouseDoubleClickEvent = lambda event, obj=obj: self.mouseDoubleClickEvent(event, obj)
        obj.wheelEvent = lambda event, obj=obj: self.mouseWheelEvent(event, obj)

    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        # self.label.setStyleSheet("color: white; border: 2px solid black;")
        font = QtGui.QFont("Droid Sans Mono Dotted for Powerline")
        self.label = CustomQLabel(font, parent=MainWindow)
        self.object_mouse_event(self.label)
        self.object_mouse_event(MainWindow)
        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)
        self.start_updating()

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "MainWindow"))

    def start_updating(self):
        self.workerThread = self.workerThread(self)
        self.workerThread.start()

    def refresh_action(self):
        self.workerThread.refresh()

    def toggle_always_on_top(self):
        # Whenever StayOnTop is disabled, Tool will automatically be made enabled, to avoid its disappearance from the taskbar
        if self.MainWindow.windowFlags() & QtCore.Qt.WindowType.WindowStaysOnTopHint == QtCore.Qt.WindowType.WindowStaysOnTopHint:
            self.MainWindow.setWindowFlags(
                self.MainWindow.windowFlags() & ~(QtCore.Qt.WindowType.WindowStaysOnTopHint | QtCore.Qt.WindowType.Tool)
            )
        else:
            self.MainWindow.setWindowFlags(
                (self.MainWindow.windowFlags() | QtCore.Qt.WindowType.WindowStaysOnTopHint | QtCore.Qt.WindowType.Tool)
            )
        self.MainWindow.show()

    def mouseClickEvent(self, event, source_obj):
        self.scroll_timer = None
        if callable(self.mouseClickCallable) is False:
            return
        if not isinstance(source_obj, CustomQLabel):
            return
        if not source_obj.line_link_dict:
            return
        initial_rel = time.time()
        while (time.time() - self.click_timer) * 1000 < 500:
            if self.single_click is False:
                break
            QtTest.QTest.qWait(20)
        if self.single_click and (initial_rel - self.click_timer) * 1000 < 170:
            line_spacing = QFontMetrics(self.label.font()).lineSpacing()
            line_clicked = self.clicked_pos_y // line_spacing + 1
            self.mouseClickCallable(workerThread=self.workerThread, line=line_clicked, source_obj=source_obj)
        return

    def mousePressEvent(self, event, source_obj):
        self.scroll_timer = None
        if isinstance(source_obj, CustomQLabel):
            self.clicked_pos_x = event.globalPos().x() - self.MainWindow.pos().x() - self.label.pos().x()
            self.clicked_pos_y = event.globalPos().y() - self.MainWindow.pos().y() - self.label.pos().y()
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.click_timer = time.time()
            self.single_click = True
            self.MainWindow.mousePressPos = event.globalPos()
            self.MainWindow.windowPos = self.MainWindow.pos()
        elif event.button() == QtCore.Qt.MouseButton.RightButton:
            self.context_menu.exec_(event.globalPos())

    def mouseDoubleClickEvent(self, event, source_obj):
        self.scroll_timer = None
        self.single_click = False
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            # If the Window has StayOnTop Active, only then FramelessWindowHint will be disabled
            if self.MainWindow.windowFlags() & QtCore.Qt.WindowType.FramelessWindowHint == QtCore.Qt.WindowType.FramelessWindowHint:
                self.MainWindow.setWindowFlags(
                    self.MainWindow.windowFlags() & ~QtCore.Qt.WindowType.FramelessWindowHint
                )
            else:
                self.MainWindow.setWindowFlags(
                    self.MainWindow.windowFlags() | QtCore.Qt.WindowType.FramelessWindowHint
                )
            self.MainWindow.show()

    def mouseMoveEvent(self, event, source_obj):
        self.scroll_timer = None
        self.single_click = False
        if self.MainWindow.mousePressPos is not None:
            delta = event.globalPos() - self.MainWindow.mousePressPos
            self.MainWindow.move(self.MainWindow.windowPos + delta)

    def mouseReleaseEvent(self, event, source_obj):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.scroll_timer = None
            self.mouseClickEvent(event, source_obj)
            self.single_click = False
            self.MainWindow.mousePressPos = None
            self.MainWindow.windowPos = None
        self.sender = None

    def mouseWheelEvent(self, event, source_obj):
        if callable(self.scrollWheelCallable) is False:
            return
        if not isinstance(source_obj, CustomQLabel):
            return
        if self.scroll_timer is None:
            self.scroll_timer = time.time()
        scroll_direction = 'up' if event.angleDelta().y() > 0 else 'down'
        if (time.time() - self.scroll_timer) * 1000 < 150:
            if scroll_direction == 'up' and self.wheel_count >= 0:
                self.wheel_count += 1
                if self.wheel_count >= source_obj.up_threshold:
                    if self.triggered_callable is False:
                        self.triggered_callable = True
                    else:
                        return
                    self.scrollWheelCallable(workerThread=self.workerThread, scroll_direction=scroll_direction)
                    self.triggered_callable = False
            elif scroll_direction == 'down' and self.wheel_count <= 0:
                self.wheel_count -= 1
                if abs(self.wheel_count) >= source_obj.down_threshold:
                    if self.triggered_callable is False:
                        self.triggered_callable = True
                    else:
                        return
                    self.scrollWheelCallable(workerThread=self.workerThread, scroll_direction=scroll_direction)
                    self.triggered_callable = False
            else:
                self.scroll_timer = None
                self.wheel_count = 0
        else:
            self.wheel_count = 0
            self.scroll_timer = None


class CustomQLabel(QtWidgets.QLabel):
    def __init__(self, font, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.MainWindow = self.parent
        self.line_link_dict = {}
        self.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        self.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        self.setGeometry(QtCore.QRect(0, 0, 150, 25))
        self.position = self.geometry().getRect()[0:2]
        # self.setStyleSheet("color: white; border: 2px solid black;")
        self.setFont(font)
        self.setText("")

    def set_link(self, line_link_dict={}):
        """
        Sets the link corresponding to the line no in Label
        """
        self.line_link_dict = line_link_dict
        if self.line_link_dict:
            self.setStyleSheet("color: blue;")

    def get_link(self, line: int, delim='\n'):
        """Returns the clicked text and corresponding link in {clicked_text: corresponding_link} format

        Args:
            line (int): The clicked line no. in the QLabel

        Raises:
            Exception: Instances passed should have datatypes, strictly followed

        Returns:
            dict: Returns {clicked_text: corresponding_link}
        """
        if not isinstance(line, int):
            raise Exception(f"Excepted instance of 'int' for line but received '{line.__class__.__name__}'")
        return {self.text().split(delim)[line - 1].strip(): self.line_link_dict[line]}


class BaseWorkerThread(threading.Thread, QObject):
    windowResized = pyqtSignal(int, int)

    def __init__(self, window):
        super().__init__()
        QObject.__init__(self)
        self.window = window
        self.MainWindow = self.window.MainWindow
        self._stop_event = threading.Event()

    def stop(self):
        # Set the stop event to signal the thread to exit
        raise Exception("MainWindow was Terminated")

    def resizeMainWindow(self, width, height):
        # Emit a signal to resize the main window
        label_pos = self.window.label.position
        self.windowResized.emit(width + 2 * label_pos[0], height + 2 * label_pos[1])


class OutlinedLabel(QtWidgets.QLabel):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.w = 1 / 25
        self.mode = True
        self.setBrush(Qt.white)
        self.setPen(Qt.black)

    def scaledOutlineMode(self):
        return self.mode

    def setScaledOutlineMode(self, state):
        self.mode = state

    def outlineThickness(self):
        return self.w * self.font().pointSize() if self.mode else self.w

    def setOutlineThickness(self, value):
        self.w = value

    def setBrush(self, brush):
        if not isinstance(brush, QBrush):
            brush = QBrush(brush)
        self.brush = brush

    def setPen(self, pen):
        if not isinstance(pen, QPen):
            pen = QPen(pen)
        pen.setJoinStyle(Qt.RoundJoin)
        self.pen = pen

    def sizeHint(self):
        w = math.ceil(self.outlineThickness() * 2)
        return super().sizeHint() + QSize(w, w)

    def minimumSizeHint(self):
        w = math.ceil(self.outlineThickness() * 2)
        return super().minimumSizeHint() + QSize(w, w)

    def paintEvent(self, event):
        w = self.outlineThickness()
        rect = self.rect()
        metrics = QFontMetrics(self.font())
        tr = metrics.boundingRect(self.text()).adjusted(0, 0, w, w)
        if self.indent() == -1:
            if self.frameWidth():
                indent = (metrics.boundingRect('x').width() + w * 2) / 2
            else:
                indent = w
        else:
            indent = self.indent()

        if self.alignment() & Qt.AlignLeft:
            x = 0
            if self.text():
                x = rect.left() + indent - min(metrics.leftBearing(self.text()[0]), 0)
        elif self.alignment() & Qt.AlignRight:
            x = rect.x() + rect.width() - indent - tr.width()
        else:
            x = (rect.width() - tr.width()) / 2

        if self.alignment() & Qt.AlignTop:
            y = rect.top() + indent + metrics.ascent()
        elif self.alignment() & Qt.AlignBottom:
            y = rect.y() + rect.height() - indent - metrics.descent()
        else:
            y = (rect.height() + metrics.ascent() - metrics.descent()) / 2

        path = QPainterPath()
        path.addText(x, y, self.font(), self.text())
        qp = QPainter(self)
        qp.setRenderHint(QPainter.Antialiasing)

        self.pen.setWidthF(w * 2)
        qp.strokePath(path, self.pen)
        if 1 < self.brush.style() < 15:
            qp.fillPath(path, self.palette().window())
        qp.fillPath(path, self.brush)
