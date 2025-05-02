"""Custom graphics view for experiment canvas."""
from PyQt5.QtWidgets import QGraphicsView
from PyQt5.QtCore import Qt, QLineF, QRectF
from PyQt5.QtGui import QPainter, QPen, QColor, QBrush

class CustomGraphicsView(QGraphicsView):
    """Custom QGraphicsView with drag-and-drop and zoom support"""
    def __init__(self, scene, parent_window):
        super().__init__(scene, parent_window)
        self.parent_window = parent_window
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        
        # Enable drag and drop
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        
        # Set background
        self.setBackgroundBrush(QBrush(QColor(255, 255, 224)))  # Light yellow
        
        # Setup for zooming
        self.zoom_factor = 1.0
        self.min_zoom = 0.1
        self.max_zoom = 10.0
        
        # For panning support
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.panning = False
        self.last_pan_point = None
        
        # For grid
        self.show_grid = True
        self.grid_size = 20
        self.snap_to_grid = False
    
    def drawBackground(self, painter, rect):
        """Draw background with optional grid"""
        super().drawBackground(painter, rect)
        
        if not self.show_grid:
            return
            
        # Save the painter state
        painter.save()
        
        # Set up the grid pen
        grid_pen = QPen(QColor(200, 200, 200, 100))
        grid_pen.setWidth(1)
        painter.setPen(grid_pen)
        
        # Calculate grid lines
        left = int(rect.left()) - (int(rect.left()) % self.grid_size)
        top = int(rect.top()) - (int(rect.top()) % self.grid_size)
        
        # Draw vertical grid lines
        for x in range(left, int(rect.right()), self.grid_size):
            # Create a QLineF object instead of using individual coordinates
            line = QLineF(x, rect.top(), x, rect.bottom())
            painter.drawLine(line)
        
        # Draw horizontal grid lines
        for y in range(top, int(rect.bottom()), self.grid_size):
            # Create a QLineF object instead of using individual coordinates
            line = QLineF(rect.left(), y, rect.right(), y)
            painter.drawLine(line)
        
        # Restore the painter state
        painter.restore()
    
    def toggle_grid(self):
        """Toggle grid visibility"""
        self.show_grid = not self.show_grid
        self.viewport().update()
    
    def toggle_snap_to_grid(self):
        """Toggle snap to grid"""
        self.snap_to_grid = not self.snap_to_grid
        return self.snap_to_grid
    
    def dragEnterEvent(self, event):
        """Handle drag enter event for instruments"""
        if event.mimeData().hasText() and event.mimeData().text() == "instrument-drag":
            event.setDropAction(Qt.CopyAction)
            event.acceptProposedAction()
            from cannex.config.settings import logger
            logger.debug("Drag enter accepted in GraphicsView")
        else:
            event.ignore()
            from cannex.config.settings import logger
            logger.debug("Drag enter ignored (wrong mime type)")
    
    def dragMoveEvent(self, event):
        """Handle drag move events"""
        if event.mimeData().hasText() and event.mimeData().text() == "instrument-drag":
            event.acceptProposedAction()
    
    def dropEvent(self, event):
        """Handle drop event to create new instrument on canvas"""
        if event.mimeData().hasText() and event.mimeData().text() == "instrument-drag":
            # Get drop position in scene coordinates
            drop_pos = self.mapToScene(event.pos())
            
            # Snap to grid if enabled
            if self.snap_to_grid:
                drop_pos.setX(round(drop_pos.x() / self.grid_size) * self.grid_size)
                drop_pos.setY(round(drop_pos.y() / self.grid_size) * self.grid_size)
            
            # Get instrument name from mime data
            raw_data = event.mimeData().data("application/x-instrument-name")
            if not raw_data:
                event.ignore()
                return
                
            name = raw_data.data().decode('utf-8')
            
            # Find instrument data
            instrument_data = None
            for data in self.parent_window.slot_window.instrument_data.values():
                if data["name"] == name:
                    instrument_data = data
                    break
            
            if not instrument_data:
                from cannex.config.settings import logger
                logger.error(f"Drop failed: No matching instrument data for '{name}'")
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.warning(self.parent_window, "Drop Error", f"Instrument '{name}' not found.")
                event.ignore()
                return
            
            # Create functions list if not present
            if "functions" not in instrument_data:
                functions = []
                import inspect
                for idx, (method_name, method) in enumerate(inspect.getmembers(instrument_data["driver_class"])):
                    if (inspect.ismethoddescriptor(method) or inspect.isfunction(method) or 
                        callable(method)) and not method_name.startswith("__"):
                        from cannex.utils.helpers import get_function_name
                        tag, readable_name = get_function_name(method_name, name, idx)
                        functions.append((tag, readable_name))
                instrument_data["functions"] = functions
            
            # Create pixmap for the instrument
            pixmap = self.parent_window.slot_window.create_instrument_icon(name)
            
            # Create instrument item
            from cannex.ui.widgets.instrument_icon import InstrumentIconItem
            instrument_item = InstrumentIconItem(pixmap, instrument_data, self.parent_window)
            
            # Keep in visible scene rect
            scene_rect = self.sceneRect()
            from cannex.config.constants import ICON_SIZE
            drop_pos.setX(max(0, min(drop_pos.x(), scene_rect.width() - ICON_SIZE)))
            drop_pos.setY(max(0, min(drop_pos.y(), scene_rect.height() - ICON_SIZE)))
            instrument_item.setPos(drop_pos)
            
            # Add to scene
            self.scene().addItem(instrument_item)
            
            # Add to tracking data
            self.parent_window.instrument_positions.append({
                "data": instrument_data, 
                "pos": drop_pos, 
                "function": None
            })
            
            # Add to command stack for undo
            self.parent_window.command_stack.append(("add", instrument_item, None))
            
            # Mark experiment as modified
            self.parent_window.is_modified = True
            self.parent_window.update_title()
            
            from cannex.config.settings import logger
            logger.info(f"Dropped instrument '{name}' at {drop_pos}")
            
            event.setDropAction(Qt.CopyAction)
            event.acceptProposedAction()
        else:
            event.ignore()
    
    def wheelEvent(self, event):
        """Handle mouse wheel for zooming"""
        zoom_in_factor = 1.25
        zoom_out_factor = 1 / zoom_in_factor
        
        # Save the scene pos
        old_pos = self.mapToScene(event.pos())
        
        # Zoom
        if event.angleDelta().y() > 0:
            # Zoom in
            new_zoom = min(self.zoom_factor * zoom_in_factor, self.max_zoom)
            zoom_factor = new_zoom / self.zoom_factor
            self.scale(zoom_factor, zoom_factor)
            self.zoom_factor = new_zoom
        else:
            # Zoom out
            new_zoom = max(self.zoom_factor * zoom_out_factor, self.min_zoom)
            zoom_factor = new_zoom / self.zoom_factor
            self.scale(zoom_factor, zoom_factor)
            self.zoom_factor = new_zoom
        
        # Get the new position
        new_pos = self.mapToScene(event.pos())
        
        # Move to keep the point under the mouse
        delta = new_pos - old_pos
        self.translate(delta.x(), delta.y())
        
        # Update parent with zoom info
        if hasattr(self.parent_window, 'update_zoom_display'):
            self.parent_window.update_zoom_display(self.zoom_factor)
    
    def mousePressEvent(self, event):
        """Handle mouse press for panning and selection"""
        if event.button() == Qt.MiddleButton:
            # Start panning with middle mouse button
            self.panning = True
            self.last_pan_point = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Handle mouse move for panning"""
        if self.panning and self.last_pan_point:
            # Calculate delta
            delta = event.pos() - self.last_pan_point
            self.last_pan_point = event.pos()
            
            # Pan the view
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
        else:
            super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release to end panning"""
        if event.button() == Qt.MiddleButton:
            self.panning = False
            self.setCursor(Qt.ArrowCursor)
            event.accept()
        else:
            super().mouseReleaseEvent(event)
    
    def reset_zoom(self):
        """Reset zoom to 100%"""
        # Calculate scale factor to reset
        scale_factor = 1.0 / self.zoom_factor
        
        # Apply scaling
        self.scale(scale_factor, scale_factor)
        
        # Reset zoom factor
        self.zoom_factor = 1.0
        
        # Reset scroll position
        self.centerOn(0, 0)
        
        # Update parent with zoom info
        if hasattr(self.parent_window, 'update_zoom_display'):
            self.parent_window.update_zoom_display(self.zoom_factor)
            
        from cannex.config.settings import logger
        logger.info("View zoom reset")
    
    def fit_content(self):
        """Fit all content in the view"""
        # Get the bounding rect of all items
        all_items = self.scene().items()
        if not all_items:
            return
            
        bounding_rect = self.scene().itemsBoundingRect()
        
        # Add some margin
        margin = 50
        bounding_rect.adjust(-margin, -margin, margin, margin)
        
        # Fit the rect
        self.fitInView(bounding_rect, Qt.KeepAspectRatio)
        
        # Update zoom factor based on the transform
        self.zoom_factor = self.transform().m11()  # Extract scale from transform matrix
        
        # Update parent with zoom info
        if hasattr(self.parent_window, 'update_zoom_display'):
            self.parent_window.update_zoom_display(self.zoom_factor)
            
        from cannex.config.settings import logger
        logger.info(f"Fit content to view (zoom: {self.zoom_factor:.2f})")