"""Connection line widget for connecting instruments."""
from PyQt5.QtWidgets import QGraphicsLineItem, QMenu, QDialog, QDialogButtonBox, QVBoxLayout
from PyQt5.QtWidgets import QLabel, QComboBox, QSpinBox, QCheckBox, QHBoxLayout, QFrame
from PyQt5.QtWidgets import QPushButton, QColorDialog, QMessageBox
from PyQt5.QtCore import Qt, QRectF, QLineF, QPointF
from PyQt5.QtGui import QPen, QColor, QPainterPath, QBrush

class ConnectionLine(QGraphicsLineItem):
    """Represents a connection line between two instruments"""
    def __init__(self, start_item, end_item):
        super().__init__()
        self.start_item = start_item
        self.end_item = end_item
        self.setPen(QPen(Qt.black, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setZValue(-1)  # Draw lines behind instruments
        
        # Connection properties
        self.direction = "Unidirectional"
        self.datatype = "Float"
        self.order = 0
        self.debug_mode = False
        
        self.update_position()
        
    def update_position(self):
        """Update the line position to connect the two instruments"""
        if not self.start_item or not self.end_item:
            return
            
        # Get center points of the instruments
        start_center = self.start_item.sceneBoundingRect().center()
        end_center = self.end_item.sceneBoundingRect().center()
        
        # Calculate vector between centers
        line = QLineF(start_center, end_center)
        
        # Adjust start and end points to be at the edges of the instruments
        start_rect = self.start_item.sceneBoundingRect()
        end_rect = self.end_item.sceneBoundingRect()
        
        # Find intersections with rectangles
        start_line = QLineF(line)
        end_line = QLineF(line)
        
        # Define the four sides of the start rectangle
        top_line = QLineF(start_rect.topLeft(), start_rect.topRight())
        bottom_line = QLineF(start_rect.bottomLeft(), start_rect.bottomRight())
        left_line = QLineF(start_rect.topLeft(), start_rect.bottomLeft())
        right_line = QLineF(start_rect.topRight(), start_rect.bottomRight())
        
        # Find the intersection point for the start item
        intersection_point = QPointF()
        if top_line.intersect(start_line, intersection_point) == QLineF.BoundedIntersection:
            start_line.setP1(intersection_point)
        elif bottom_line.intersect(start_line, intersection_point) == QLineF.BoundedIntersection:
            start_line.setP1(intersection_point)
        elif left_line.intersect(start_line, intersection_point) == QLineF.BoundedIntersection:
            start_line.setP1(intersection_point)
        elif right_line.intersect(start_line, intersection_point) == QLineF.BoundedIntersection:
            start_line.setP1(intersection_point)
        
        # Define the four sides of the end rectangle
        top_line = QLineF(end_rect.topLeft(), end_rect.topRight())
        bottom_line = QLineF(end_rect.bottomLeft(), end_rect.bottomRight())
        left_line = QLineF(end_rect.topLeft(), end_rect.bottomLeft())
        right_line = QLineF(end_rect.topRight(), end_rect.bottomRight())
        
        # Find the intersection point for the end item
        if top_line.intersect(end_line, intersection_point) == QLineF.BoundedIntersection:
            end_line.setP2(intersection_point)
        elif bottom_line.intersect(end_line, intersection_point) == QLineF.BoundedIntersection:
            end_line.setP2(intersection_point)
        elif left_line.intersect(end_line, intersection_point) == QLineF.BoundedIntersection:
            end_line.setP2(intersection_point)
        elif right_line.intersect(end_line, intersection_point) == QLineF.BoundedIntersection:
            end_line.setP2(intersection_point)
        
        # Set the line coordinates
        self.setLine(QLineF(start_line.p1(), end_line.p2()))
        
        # Add an arrow for unidirectional connections
        if self.direction == "Unidirectional":
            # Calculate the arrow points
            angle = self.line().angle() * 3.14159 / 180
            arrow_size = 10
            arrow_p1 = self.line().p2() - QPointF(arrow_size * 1.5 * -pow(angle, 0), arrow_size * 1.5 * 1)
            arrow_p2 = self.line().p2() - QPointF(arrow_size * 1.5 * 1, arrow_size * 1.5 * -pow(angle, 0))
            
            # Create the arrow path
            arrow_path = QPainterPath()
            arrow_path.moveTo(self.line().p2())
            arrow_path.lineTo(arrow_p1)
            arrow_path.lineTo(arrow_p2)
            arrow_path.lineTo(self.line().p2())
            
            # Set the brush based on the line color
            brush = QBrush(self.pen().color())
            
            # Create the arrow item if not already created
            if not hasattr(self, 'arrow_item'):
                self.arrow_item = QGraphicsPathItem(self)
                self.arrow_item.setBrush(brush)
                self.arrow_item.setPen(QPen(self.pen().color()))
            
            # Update the arrow path
            self.arrow_item.setPath(arrow_path)
        elif hasattr(self, 'arrow_item'):
            self.scene().removeItem(self.arrow_item)
            delattr(self, 'arrow_item')
    
    def paint(self, painter, option, widget):
        """Custom paint method to add visual effects for different states"""
        if self.debug_mode:
            # Create a glowing effect for debugging
            original_pen = self.pen()
            glow_pen = QPen(original_pen.color().lighter(150), original_pen.width() + 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(glow_pen)
            painter.drawLine(self.line())
            painter.setPen(original_pen)
            painter.drawLine(self.line())
        else:
            super().paint(painter, option, widget)
    
    def contextMenuEvent(self, event):
        """Show context menu on right-click"""
        menu = QMenu()
        menu.addAction("Delete", self.delete_line)
        menu.addAction("Properties", self.show_properties)
        menu.exec_(event.screenPos())
    
    def mousePressEvent(self, event):
        """Handle mouse press events"""
        if event.button() == Qt.LeftButton:
            self.show_config_window()
            event.accept()
        else:
            super().mousePressEvent(event)
    
    def delete_line(self):
        """Remove this connection line"""
        scene = self.scene()
        if scene:
            # Remove from connections lists
            if self in self.start_item.connections:
                self.start_item.connections.remove(self)
            if self in self.end_item.connections:
                self.end_item.connections.remove(self)
            
            # Store for undo
            window = scene.views()[0].parent()
            if hasattr(window, 'command_stack'):
                window.command_stack.append(("delete_line", self, (self.start_item, self.end_item)))
            
            # Remove from scene
            scene.removeItem(self)
            from cannex.config.settings import logger
            logger.info(f"Deleted connection between {self.start_item.instrument_data['name']} and {self.end_item.instrument_data['name']}")
    
    def show_properties(self):
        """Show connection properties in a message box"""
        QMessageBox.information(None, "Line Properties",
                                f"Connection from {self.start_item.instrument_data['name']} to {self.end_item.instrument_data['name']}\n"
                                f"Direction: {self.direction}\nData Type: {self.datatype}\nExecution Order: {self.order}")
    
    def show_config_window(self):
        """Show configuration dialog for this connection"""
        dialog = QDialog()
        dialog.setWindowTitle("Connection Configuration (LabVIEW-Inspired)")
        dialog.setMinimumWidth(350)
        layout = QVBoxLayout(dialog)
        
        # Connection info
        layout.addWidget(QLabel(f"Source: {self.start_item.instrument_data['name']}"))
        layout.addWidget(QLabel(f"Target: {self.end_item.instrument_data['name']}"))
        
        # Direction dropdown
        direction_combo = QComboBox()
        direction_combo.addItems(["Unidirectional", "Bidirectional"])
        direction_combo.setCurrentText(self.direction)
        layout.addWidget(QLabel("Direction (Flow):"))
        layout.addWidget(direction_combo)
        
        # Data type dropdown
        datatype_combo = QComboBox()
        datatype_combo.addItems(["Integer", "Float", "String", "Boolean"])
        datatype_combo.setCurrentText(self.datatype)
        layout.addWidget(QLabel("Data Type:"))
        layout.addWidget(datatype_combo)
        
        # Execution order spinner
        order_spin = QSpinBox()
        order_spin.setRange(0, 100)
        order_spin.setValue(self.order)
        layout.addWidget(QLabel("Execution Order:"))
        layout.addWidget(order_spin)
        
        # Line style dropdown
        style_combo = QComboBox()
        style_combo.addItems(["Solid", "Dashed", "Dotted"])
        style_combo.setCurrentText({Qt.SolidLine: "Solid", Qt.DashLine: "Dashed", Qt.DotLine: "Dotted"}.get(self.pen().style(), "Solid"))
        layout.addWidget(QLabel("Line Style:"))
        layout.addWidget(style_combo)
        
        # Color button
        color_btn = QPushButton("Change Color")
        current_color = self.pen().color()
        color_indicator = QFrame()
        color_indicator.setFixedSize(20, 20)
        color_indicator.setStyleSheet(f"background-color: {current_color.name()}; border: 1px solid black;")
        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("Line Color:"))
        color_layout.addWidget(color_indicator)
        color_layout.addWidget(color_btn)
        layout.addLayout(color_layout)
        
        # Debug checkbox
        debug_check = QCheckBox("Enable Debugging (Highlight Execution)")
        debug_check.setChecked(self.debug_mode)
        layout.addWidget(debug_check)
        
        # Dialog buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        # Color picker handler
        def update_color():
            color = QColorDialog.getColor(self.pen().color(), dialog)
            if color.isValid():
                color_indicator.setStyleSheet(f"background-color: {color.name()}; border: 1px solid black;")
                self.setPen(QPen(color, self.pen().width(), self.pen().style(), Qt.RoundCap, Qt.RoundJoin))
                self.update()
                from cannex.config.settings import logger
                logger.debug(f"Line color changed to {color.name()}")
        
        color_btn.clicked.connect(update_color)
        
        # Process dialog result
        if dialog.exec_() == QDialog.Accepted:
            # Save changes
            self.direction = direction_combo.currentText()
            self.datatype = datatype_combo.currentText()
            self.order = order_spin.value()
            self.debug_mode = debug_check.isChecked()
            
            # Update line style
            style_map = {"Solid": Qt.SolidLine, "Dashed": Qt.DashLine, "Dotted": Qt.DotLine}
            self.setPen(QPen(self.pen().color(), 2 if not self.debug_mode else 3,
                          style_map[style_combo.currentText()], Qt.RoundCap, Qt.RoundJoin))
            
            # Update position to refresh arrow
            self.update_position()
            
            from cannex.config.settings import logger
            logger.info(f"Configured connection: Direction={self.direction}, DataType={self.datatype}, Order={self.order}, Debug={self.debug_mode}")