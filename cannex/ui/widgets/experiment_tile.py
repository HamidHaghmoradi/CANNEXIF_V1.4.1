"""Experiment tile widget for experiment slots."""
from PyQt5.QtWidgets import QPushButton
from PyQt5.QtCore import QTimer, Qt, QSize

from cannex.config.constants import EXPERIMENT_COLORS

class ExperimentTile(QPushButton):
    """Custom button for experiment tiles in the main window"""
    def __init__(self, name, parent=None):
        super().__init__(parent)
        self.experiment_name = name
        self.setFixedSize(80, 80)  # Using ICON_SIZE constant
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {EXPERIMENT_COLORS['default']};
                border-radius: 15px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: {EXPERIMENT_COLORS['active']};
            }}
        """)
        self.hold_timer = QTimer()
        self.hold_timer.setSingleShot(True)
        self.setProperty("exp_name", name)
        
        # Connect hold timer for iOS-like delete
        self.pressEvent = self.mousePressEvent
        
        def custom_press(self, event, original=self.pressEvent):
            if event.button() == Qt.LeftButton:
                self.hold_timer.start(500)  # 500ms for long press
            original(event)
        
        self.mousePressEvent = lambda event: custom_press(self, event)
        
        # Connect release to cancel timer
        self.releaseEvent = self.mouseReleaseEvent
        
        def custom_release(self, event, original=self.releaseEvent):
            self.hold_timer.stop()
            original(event)
        
        self.mouseReleaseEvent = lambda event: custom_release(self, event)