"""Slot button widget for instrument slots."""
from PyQt5.QtWidgets import QPushButton, QSizePolicy
from PyQt5.QtCore import QTimer, Qt, QSize

class SlotButton(QPushButton):
    """Custom button for instrument slots in the main window"""
    def __init__(self, row, col, parent=None):
        super().__init__(parent)
        self.row = row
        self.col = col
        self.setFixedSize(80, 80)  # Using ICON_SIZE constant
        self.setStyleSheet("""
            QPushButton {
                background-color: rgba(200, 200, 200, 50);
                border-radius: 15px;
                border: none;
            }
            QPushButton:hover {
                background-color: rgba(200, 200, 200, 100);
            }
        """)
        self.hold_timer = QTimer()
        self.hold_timer.setSingleShot(True)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        
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