"""Draggable instrument button for the instrument sidebar."""
from PyQt5.QtWidgets import QPushButton
from PyQt5.QtCore import Qt, QSize, QPoint
from PyQt5.QtGui import QIcon, QDrag, QPixmap
from PyQt5.QtCore import QMimeData

from cannex.config.constants import ICON_SIZE
from cannex.config.settings import logger

class DraggableInstrumentButton(QPushButton):
    """Button for instrument in sidebar that can be dragged to canvas"""
    def __init__(self, pixmap, data, parent_window):
        super().__init__(parent_window)
        self.setIcon(QIcon(pixmap))
        self.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        self.setFixedSize(ICON_SIZE, ICON_SIZE)
        self.setStyleSheet("QPushButton { background-color: transparent; border: none; }")
        self._data = data
        self.parent_window = parent_window
        self.setToolTip(data['name'])
        self.setAcceptDrops(True)
        self.setMouseTracking(True)
    
    def mousePressEvent(self, event):
        """Start potential drag operation"""
        if event.button() == Qt.LeftButton:
            self.drag_start_position = event.pos()
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Handle mouse move to initiate drag if threshold is passed"""
        if not (event.buttons() & Qt.LeftButton):
            return
            
        # Check if we've moved far enough to start a drag
        if (event.pos() - self.drag_start_position).manhattanLength() < QApplication.startDragDistance():
            return
            
        # Create a drag operation
        drag = QDrag(self)
        mimeData = QMimeData()
        
        # Set data for the drag
        mimeData.setText("instrument-drag")
        mimeData.setData("application/x-instrument-name", self._data["name"].encode('utf-8'))
        drag.setMimeData(mimeData)
        
        # Create a pixmap for the drag icon
        pixmap = self.icon().pixmap(self.iconSize())
        drag.setPixmap(pixmap)
        drag.setHotSpot(event.pos())
        
        # Execute the drag
        logger.info(f"Starting drag for instrument: {self._data['name']}")
        result = drag.exec_(Qt.CopyAction)
        
        if result == Qt.CopyAction:
            logger.debug(f"Drag completed successfully for {self._data['name']}")
        else:
            logger.debug(f"Drag cancelled for {self._data['name']}")