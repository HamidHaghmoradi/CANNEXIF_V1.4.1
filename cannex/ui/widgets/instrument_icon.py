"""Instrument icon widget for the experiment canvas."""
from PyQt5.QtWidgets import (QGraphicsPixmapItem, QMenu, QDialog, QVBoxLayout, QHBoxLayout,
                            QLabel, QListWidget, QDialogButtonBox, QListWidgetItem,
                            QTextEdit, QPushButton, QMessageBox, QSpinBox, QDoubleSpinBox,
                            QCheckBox, QLineEdit, QFormLayout, QTableWidget, QTableWidgetItem,
                            QHeaderView)
from PyQt5.QtCore import Qt, QSize, QDateTime, QPoint, QPointF
from PyQt5.QtGui import QPainter, QPen, QColor, QFont, QFontMetrics, QPixmap

from cannex.config.constants import INSTRUMENT_COLORS, ICON_SIZE
from cannex.config.settings import logger
from cannex.utils.exceptions import LabVIEWError

class InstrumentIconItem(QGraphicsPixmapItem):
    """Represents an instrument in the experiment canvas"""
    def __init__(self, pixmap, instrument_data, window):
        super().__init__(pixmap)
        self.instrument_data = instrument_data
        self.window = window
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setToolTip(self.instrument_data["name"])
        
        # Instrument properties
        self.selected_function = None
        self.function_tag = None
        self.is_locked = False
        self.parameters = {}
        self.status = "Idle"
        self.last_execution_time = None
        self.connections = []
        self.results_history = []
        
        # For connecting mode
        self.setAcceptHoverEvents(True)
    
    def mousePressEvent(self, event):
        """Handle mouse press events"""
        # Check if we're in connecting mode
        if hasattr(self.window, 'connecting_mode') and self.window.connecting_mode:
            # If no start instrument is selected, make this the start
            if self.window.start_instrument is None:
                self.window.start_instrument = self
                logger.info(f"Started connection from {self.instrument_data['name']}")
            else:
                # If we already have a start instrument, create the connection
                self.window.add_connection(self.window.start_instrument, self)
                self.window.start_instrument = None
                self.window.connecting_mode = False
                self.window.view.setCursor(Qt.ArrowCursor)
            event.accept()
        else:
            super().mousePressEvent(event)
    
    def mouseDoubleClickEvent(self, event):
        """Open function selection dialog on double-click"""
        if event.button() == Qt.LeftButton:
            logger.info(f"Double-click on {self.instrument_data['name']}")
            self.show_function_dialog()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)
    
    def mouseMoveEvent(self, event):
        """Update connections when instrument is moved"""
        super().mouseMoveEvent(event)
        # Update all connections
        for conn in self.connections:
            conn.update_position()
        
        # Update stored position data
        for item in self.window.instrument_positions:
            if item["data"] == self.instrument_data:
                item["pos"] = self.pos()
                break
                
        # Check if we need to add to command stack for undo
        if not hasattr(self, '_moving'):
            self._moving = True
            self._original_pos = self.pos()
        
    def mouseReleaseEvent(self, event):
        """Handle mouse release after drag"""
        super().mouseReleaseEvent(event)
        if hasattr(self, '_moving') and self._moving:
            if self.pos() != self._original_pos:
                self.window.command_stack.append(("move", self, self._original_pos))
            self._moving = False
            delattr(self, '_original_pos')
    
    def hoverEnterEvent(self, event):
        """Handle hover effects"""
        if hasattr(self.window, 'connecting_mode') and self.window.connecting_mode:
            self.setCursor(Qt.CrossCursor)
            # Add highlight effect
            self.setOpacity(0.8)
        super().hoverEnterEvent(event)
    
    def hoverLeaveEvent(self, event):
        """Remove hover effects"""
        self.setOpacity(1.0)
        self.setCursor(Qt.ArrowCursor)
        super().hoverLeaveEvent(event)
    
    def contextMenuEvent(self, event):
        """Show context menu on right-click"""
        menu = QMenu()
        menu.addAction("Connect", lambda: self.window.toggle_connecting_mode())
        menu.addAction("Select Function", self.show_function_dialog)
        
        # Copy and paste actions
        menu.addAction("Copy", self.copy_instrument)
        
        # Set parameters action
        params_action = menu.addAction("Parameters", self.edit_parameters)
        params_action.setEnabled(self.selected_function is not None)
        
        # Run function action
        run_action = menu.addAction("Run", self.run_function)
        run_action.setEnabled(self.selected_function is not None)
        
        # View results history
        if self.results_history:
            menu.addAction("Results History", self.show_results_history)
        
        # Properties action
        menu.addAction("Properties", self.show_properties)
        
        # Lock/unlock action
        if self.is_locked:
            menu.addAction("Unlock", self.toggle_lock)
        else:
            menu.addAction("Lock", self.toggle_lock)
        
        # Delete action
        menu.addSeparator()
        menu.addAction("Delete", self.delete_instrument)
        
        menu.exec_(event.screenPos())
    
    def toggle_lock(self):
        """Toggle the locked state of the instrument"""
        self.is_locked = not self.is_locked
        self.setFlag(QGraphicsItem.ItemIsMovable, not self.is_locked)
        logger.info(f"Instrument {self.instrument_data['name']} {'locked' if self.is_locked else 'unlocked'}")
    
    def show_function_dialog(self):
        """Show dialog to select instrument function"""
        dialog = QDialog(self.window)
        dialog.setWindowTitle(f"Select Function - {self.instrument_data['name']}")
        dialog.setMinimumWidth(400)
        layout = QVBoxLayout(dialog)
        
        # Function list
        layout.addWidget(QLabel("Available Functions:"))
        function_list = QListWidget()
        for tag, readable_name in self.instrument_data["functions"]:
            item = QListWidgetItem(f"{tag} - {readable_name}")
            item.setData(Qt.UserRole, (tag, readable_name.split(" - ")[1]))
            function_list.addItem(item)
        layout.addWidget(function_list)
        
        # Description area
        description = QTextEdit()
        description.setReadOnly(True)
        description.setMaximumHeight(100)
        layout.addWidget(QLabel("Description:"))
        layout.addWidget(description)
        
        # Update description when selection changes
        def update_description():
            selected_items = function_list.selectedItems()
            if selected_items:
                tag, func_name = selected_items[0].data(Qt.UserRole)
                description.setText(f"Function: {func_name}\nTag: {tag}\n\nNo additional documentation available.")
        
        function_list.itemSelectionChanged.connect(update_description)
        
        # Dialog buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        # Process result
        if dialog.exec_() == QDialog.Accepted:
            selected_items = function_list.selectedItems()
            if selected_items:
                tag, func_name = selected_items[0].data(Qt.UserRole)
                self.set_function(tag, func_name)
                logger.info(f"Set function {tag} ({func_name}) for {self.instrument_data['name']}")
    
    def set_function(self, tag, function_name):
        """Set the instrument's function"""
        self.selected_function = function_name
        self.function_tag = tag
        
        # Update the visual appearance
        self.update_icon()
        
        # Update stored data
        for item in self.window.instrument_positions:
            if item["data"] == self.instrument_data:
                item["function"] = function_name
                break
    
    def update_icon(self):
        """Update the icon to reflect the current state"""
        pixmap = QPixmap(200, 200)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Set background color based on function type and status
        if self.status == "Error":
            background_color = QColor(INSTRUMENT_COLORS['error'])
        elif self.function_tag and self.function_tag.startswith("RE"):
            background_color = QColor(INSTRUMENT_COLORS['active'])
        else:
            background_color = QColor(INSTRUMENT_COLORS['default'])
        
        # Draw rounded rectangle background
        painter.setBrush(background_color)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(0, 0, 200, 200, 30, 30)
        
        # Draw CANNEX label at top
        painter.setPen(QColor(200, 200, 200))
        painter.setFont(QFont("Arial", 24, QFont.Bold))
        painter.drawText(QRect(0, 20, 200, 50), Qt.AlignCenter, "CANNEX")
        
        # Draw instrument name at bottom
        painter.setPen(Qt.white)
        max_width = 180
        font = QFont("Arial", 24)
        metrics = QFontMetrics(font)
        text = metrics.elidedText(self.instrument_data["name"], Qt.ElideRight, max_width)
        painter.setFont(font)
        painter.drawText(QRect(0, 130, 200, 60), Qt.AlignCenter, text)
        
        # Draw function tag in the middle if set
        if self.function_tag:
            painter.setFont(QFont("Arial", 20, QFont.Bold))
            painter.drawText(QRect(0, 80, 200, 50), Qt.AlignCenter, self.function_tag)
        
        # Draw locked icon if instrument is locked
        if self.is_locked:
            painter.setPen(QColor(255, 255, 0))  # Yellow
            painter.setBrush(QColor(255, 255, 0, 100))
            painter.drawEllipse(160, 20, 20, 20)
            
            # Draw lock symbol
            painter.setPen(QPen(QColor(255, 255, 0), 2))
            painter.drawRect(165, 25, 10, 8)
            painter.drawLine(170, 25, 170, 23)
            
        painter.end()
        
        # Scale the pixmap and apply to item
        self.setPixmap(pixmap.scaled(ICON_SIZE, ICON_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation))
    
    def copy_instrument(self):
        """Create a copy of this instrument"""
        scene = self.scene()
        if scene:
            # Create a new instrument with the same data
            new_item = InstrumentIconItem(self.pixmap(), self.instrument_data.copy(), self.window)
            # Position slightly offset from original
            new_item.setPos(self.pos() + QPointF(20, 20))
            # Copy function and parameters
            new_item.selected_function = self.selected_function
            new_item.function_tag = self.function_tag
            new_item.parameters = self.parameters.copy()
            new_item.update_icon()
            
            # Add to scene and tracking data
            scene.addItem(new_item)
            self.window.instrument_positions.append({
                "data": new_item.instrument_data, 
                "pos": new_item.pos(), 
                "function": new_item.selected_function
            })
            
            # Add to command stack for undo
            self.window.command_stack.append(("add", new_item, None))
            
            logger.info(f"Copied instrument {self.instrument_data['name']}")
    
    def edit_parameters(self):
        """Open dialog to edit function parameters"""
        if not self.selected_function:
            QMessageBox.warning(self.window, "Edit Parameters", "Please select a function first.")
            return
            
        dialog = QDialog(self.window)
        dialog.setWindowTitle(f"Parameters: {self.instrument_data['name']} - {self.function_tag}")
        dialog.setMinimumWidth(400)
        layout = QVBoxLayout(dialog)
        
        # Parameter form
        form_layout = QFormLayout()
        layout.addWidget(QLabel("Function Parameters:"))
        
        # Get parameter information from function docstring if available
        param_info = {}
        driver_class = self.instrument_data["driver_class"]
        func = getattr(driver_class, self.selected_function, None)
        if func and func.__doc__:
            # Parse docstring for parameter info
            docstring = func.__doc__
            param_sections = docstring.split("Parameters:")
            if len(param_sections) > 1:
                param_text = param_sections[1].split("Returns:")[0].strip()
                for line in param_text.split('\n'):
                    if ':' in line:
                        param_name, param_desc = line.split(':', 1)
                        param_info[param_name.strip()] = param_desc.strip()
        
        # Create parameter widgets based on current parameters
        param_widgets = {}
        
        # Try to get parameter type hints from function signature
        import inspect
        try:
            signature = inspect.signature(func)
            for param_name, param in signature.parameters.items():
                if param_name == 'self':
                    continue
                    
                # Get current value or default
                current_value = self.parameters.get(param_name, param.default if param.default is not inspect.Parameter.empty else None)
                
                # Get annotation (type hint) if available
                annotation = param.annotation if param.annotation is not inspect.Parameter.empty else None
                
                # Create appropriate widget based on type hint
                if annotation == int or (annotation is None and isinstance(current_value, int)):
                    spin = QSpinBox()
                    spin.setRange(-1000000, 1000000)
                    spin.setValue(current_value or 0)
                    if param_name in param_info:
                        spin.setToolTip(param_info[param_name])
                    form_layout.addRow(f"{param_name}:", spin)
                    param_widgets[param_name] = spin
                    
                elif annotation == float or (annotation is None and isinstance(current_value, float)):
                    spin = QDoubleSpinBox()
                    spin.setRange(-1000000, 1000000)
                    spin.setDecimals(6)
                    spin.setValue(current_value or 0.0)
                    if param_name in param_info:
                        spin.setToolTip(param_info[param_name])
                    form_layout.addRow(f"{param_name}:", spin)
                    param_widgets[param_name] = spin
                    
                elif annotation == bool or (annotation is None and isinstance(current_value, bool)):
                    check = QCheckBox()
                    check.setChecked(current_value or False)
                    if param_name in param_info:
                        check.setToolTip(param_info[param_name])
                    form_layout.addRow(f"{param_name}:", check)
                    param_widgets[param_name] = check
                    
                elif annotation == str or (annotation is None and isinstance(current_value, str)):
                    text = QLineEdit()
                    text.setText(current_value or "")
                    if param_name in param_info:
                        text.setToolTip(param_info[param_name])
                    form_layout.addRow(f"{param_name}:", text)
                    param_widgets[param_name] = text
                    
                else:
                    # Default to text input for unknown types
                    text = QLineEdit()
                    text.setText(str(current_value) if current_value is not None else "")
                    if param_name in param_info:
                        text.setToolTip(param_info[param_name])
                    form_layout.addRow(f"{param_name}:", text)
                    param_widgets[param_name] = text
        
        except Exception as e:
            # Fallback to general parameter editor if we can't parse signature
            logger.warning(f"Could not parse function signature: {str(e)}")
            
            param_edit = QTextEdit()
            param_edit.setText(str(self.parameters))
            layout.addWidget(param_edit)
            
            # Buttons
            buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            buttons.accepted.connect(lambda: self._save_parameters_text(param_edit, dialog))
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)
            
            dialog.exec_()
            return
        
        # Add parameter form if we have parameters
        if param_widgets:
            layout.addLayout(form_layout)
        else:
            layout.addWidget(QLabel("This function has no parameters."))
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(lambda: self._save_parameters_form(param_widgets, dialog))
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        dialog.exec_()
    
    def _save_parameters_form(self, param_widgets, dialog):
        """Save parameters from the form widgets"""
        try:
            # Build parameter dictionary from widgets
            params = {}
            for param_name, widget in param_widgets.items():
                if isinstance(widget, QSpinBox):
                    params[param_name] = widget.value()
                elif isinstance(widget, QDoubleSpinBox):
                    params[param_name] = widget.value()
                elif isinstance(widget, QCheckBox):
                    params[param_name] = widget.isChecked()
                elif isinstance(widget, QLineEdit):
                    # Try to convert to appropriate type
                    text = widget.text()
                    try:
                        # Try to eval as a Python expression
                        params[param_name] = eval(text)
                    except:
                        # Fallback to string
                        params[param_name] = text
                else:
                    # Default to string for unknown widget types
                    params[param_name] = str(widget.text())
            
            self.parameters = params
            dialog.accept()
            logger.info(f"Updated parameters for {self.instrument_data['name']}: {self.parameters}")
        
        except Exception as e:
            QMessageBox.warning(dialog, "Error", f"Invalid parameters: {str(e)}")
    
    def _save_parameters_text(self, param_edit, dialog):
        """Save parameters from the text editor"""
        try:
            # Parse parameters from text
            new_params = eval(param_edit.toPlainText())
            if not isinstance(new_params, dict):
                raise ValueError("Parameters must be a dictionary")
                
            self.parameters = new_params
            dialog.accept()
            logger.info(f"Updated parameters for {self.instrument_data['name']}: {self.parameters}")
        except Exception as e:
            QMessageBox.warning(dialog, "Error", f"Invalid parameters: {str(e)}")
    
    def run_function(self):
        """Execute the selected function"""
        if not self.selected_function:
            QMessageBox.warning(self.window, "Run", "No function assigned.")
            return None
            
        # Update status
        self.status = "Running"
        self.last_execution_time = QDateTime.currentDateTime()
        
        # Get driver instance
        try:
            driver_instance = self.instrument_data["driver_class"]()
        except Exception as e:
            logger.error(f"Failed to instantiate driver for {self.instrument_data['name']}: {str(e)}")
            self.status = "Error"
            error = LabVIEWError(1000, self.instrument_data['name'], f"Driver instantiation failed: {str(e)}")
            QMessageBox.warning(self.window, "Run Error", str(error))
            self.results_history.append({
                "time": self.last_execution_time.toString(),
                "params": self.parameters.copy(),
                "result": str(error),
                "status": "error"
            })
            return error
            
        # Run the function
        try:
            method = getattr(driver_instance, self.selected_function)
            result = method(**self.parameters) if self.parameters else method()
            self.status = "Idle"
            
            # Add to results history
            self.results_history.append({
                "time": self.last_execution_time.toString(),
                "params": self.parameters.copy(),
                "result": result,
                "status": "success"
            })
            
            # Trim history if too long
            if len(self.results_history) > 100:
                self.results_history = self.results_history[-100:]
            
            # Show results
            QMessageBox.information(self.window, "Run",
                                   f"Executed {self.function_tag}\nParameters: {self.parameters}\nResult: {result}")
            logger.info(f"Executed {self.function_tag} on {self.instrument_data['name']} with result: {result}")
            
            # Mark experiment as active
            from cannex.config.constants import EXPERIMENT_COLORS
            self.window.slot_window.update_experiment_tile_color(self.window.experiment_name, EXPERIMENT_COLORS['running'])
            
            return result
        except Exception as e:
            self.status = "Error"
            error = LabVIEWError(1001, self.instrument_data['name'], str(e))
            
            # Add to results history
            self.results_history.append({
                "time": self.last_execution_time.toString(),
                "params": self.parameters.copy(),
                "result": str(error),
                "status": "error"
            })
            
            logger.error(str(error))
            QMessageBox.warning(self.window, "Run Error", str(error))
            return error
    
    def show_results_history(self):
        """Show results history in a dialog"""
        if not self.results_history:
            QMessageBox.information(self.window, "Results History", "No results history available.")
            return
            
        dialog = QDialog(self.window)
        dialog.setWindowTitle(f"Results History: {self.instrument_data['name']}")
        dialog.setMinimumSize(600, 400)
        layout = QVBoxLayout(dialog)
        
        # Create table widget
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["Time", "Parameters", "Result", "Status"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        
        # Add data to table
        table.setRowCount(len(self.results_history))
        for i, result in enumerate(reversed(self.results_history)):
            table.setItem(i, 0, QTableWidgetItem(result["time"]))
            table.setItem(i, 1, QTableWidgetItem(str(result["params"])))
            table.setItem(i, 2, QTableWidgetItem(str(result["result"])))
            
            status_item = QTableWidgetItem(result["status"])
            if result["status"] == "error":
                status_item.setBackground(QColor(255, 200, 200))
            else:
                status_item.setBackground(QColor(200, 255, 200))
            table.setItem(i, 3, status_item)
        
        layout.addWidget(table)
        
        # Add export button
        export_btn = QPushButton("Export to CSV")
        export_btn.clicked.connect(lambda: self.export_results_history())
        layout.addWidget(export_btn)
        
        # Add close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        
        dialog.exec_()
    
    def export_results_history(self):
        """Export results history to CSV file"""
        import csv
        from PyQt5.QtWidgets import QFileDialog
        
        if not self.results_history:
            return
            
        file_name, _ = QFileDialog.getSaveFileName(self.window, "Export Results History", 
                                                f"{self.instrument_data['name']}_results.csv", 
                                                "CSV Files (*.csv)")
        if not file_name:
            return
            
        try:
            with open(file_name, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["Time", "Parameters", "Result", "Status"])
                
                for result in self.results_history:
                    writer.writerow([
                        result["time"],
                        str(result["params"]),
                        str(result["result"]),
                        result["status"]
                    ])
            
            QMessageBox.information(self.window, "Export", f"Results history exported to {file_name}")
            logger.info(f"Exported results history for {self.instrument_data['name']} to {file_name}")
        
        except Exception as e:
            QMessageBox.warning(self.window, "Export Error", f"Failed to export results: {str(e)}")
            logger.error(f"Failed to export results history: {str(e)}")
    
    def show_properties(self):
        """Show instrument properties dialog"""
        dialog = QDialog(self.window)
        dialog.setWindowTitle(f"Properties: {self.instrument_data['name']}")
        dialog.setMinimumWidth(500)
        layout = QVBoxLayout(dialog)
        
        # Create tabbed interface
        from PyQt5.QtWidgets import QTabWidget
        tabs = QTabWidget()
        layout.addWidget(tabs)
        
        # Basic info tab
        basic_tab = QWidget()
        basic_layout = QVBoxLayout(basic_tab)
        
        # Instrument details
        basic_layout.addWidget(QLabel(f"<b>Name:</b> {self.instrument_data['name']}"))
        basic_layout.addWidget(QLabel(f"<b>Driver Class:</b> {self.instrument_data['driver_class'].__name__}"))
        basic_layout.addWidget(QLabel(f"<b>Function:</b> {self.function_tag or 'None'}"))
        basic_layout.addWidget(QLabel(f"<b>Status:</b> {self.status}"))
        if self.last_execution_time:
            basic_layout.addWidget(QLabel(f"<b>Last Run:</b> {self.last_execution_time.toString()}"))
        
        # Parameters section
        if self.parameters:
            basic_layout.addWidget(QLabel("<b>Parameters:</b>"))
            param_text = QTextEdit()
            param_text.setReadOnly(True)
            param_text.setText(str(self.parameters))
            param_text.setMaximumHeight(100)
            basic_layout.addWidget(param_text)
        
        tabs.addTab(basic_tab, "Basic Info")
        
        # Connections tab
        conn_tab = QWidget()
        conn_layout = QVBoxLayout(conn_tab)
        
        if self.connections:
            conn_list = QListWidget()
            for conn in self.connections:
                if conn.start_item == self:
                    conn_list.addItem(f"To: {conn.end_item.instrument_data['name']} ({conn.direction}, {conn.datatype})")
                else:
                    conn_list.addItem(f"From: {conn.start_item.instrument_data['name']} ({conn.direction}, {conn.datatype})")
            conn_layout.addWidget(conn_list)
        else:
            conn_layout.addWidget(QLabel("No connections."))
        
        tabs.addTab(conn_tab, "Connections")
        
        # Documentation tab
        doc_tab = QWidget()
        doc_layout = QVBoxLayout(doc_tab)
        
        doc_text = QTextEdit()
        doc_text.setReadOnly(True)
        
        # Get class and function docstrings
        class_doc = self.instrument_data["driver_class"].__doc__ or "No class documentation available."
        func_doc = ""
        if self.selected_function:
            func = getattr(self.instrument_data["driver_class"], self.selected_function, None)
            if func and func.__doc__:
                func_doc = func.__doc__
            else:
                func_doc = "No function documentation available."
        
        doc_text.setText(f"Class Documentation:\n{class_doc}\n\nFunction Documentation:\n{func_doc}")
        doc_layout.addWidget(doc_text)
        
        tabs.addTab(doc_tab, "Documentation")
        
        # Statistics tab if we have results history
        if self.results_history:
            stats_tab = QWidget()
            stats_layout = QVBoxLayout(stats_tab)
            
            # Calculate some statistics
            success_count = sum(1 for r in self.results_history if r["status"] == "success")
            error_count = sum(1 for r in self.results_history if r["status"] == "error")
            success_rate = success_count / len(self.results_history) * 100
            
            stats_layout.addWidget(QLabel(f"Total Executions: {len(self.results_history)}"))
            stats_layout.addWidget(QLabel(f"Successful: {success_count} ({success_rate:.1f}%)"))
            stats_layout.addWidget(QLabel(f"Errors: {error_count}"))
            
            # Try to calculate numeric stats if applicable
            try:
                numeric_results = [float(r["result"]) for r in self.results_history 
                                 if r["status"] == "success" and isinstance(r["result"], (int, float)) or 
                                 (isinstance(r["result"], str) and r["result"].replace('.', '', 1).isdigit())]
                
                if numeric_results:
                    avg = sum(numeric_results) / len(numeric_results)
                    minimum = min(numeric_results)
                    maximum = max(numeric_results)
                    
                    stats_layout.addWidget(QLabel(f"Average Result: {avg:.6g}"))
                    stats_layout.addWidget(QLabel(f"Minimum: {minimum:.6g}"))
                    stats_layout.addWidget(QLabel(f"Maximum: {maximum:.6g}"))
            except:
                # Non-numeric results
                pass
            
            tabs.addTab(stats_tab, "Statistics")
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        
        dialog.exec_()
    
    def delete_instrument(self):
        """Remove this instrument and its connections"""
        # Confirm deletion if there are connections
        if self.connections and len(self.connections) > 0:
            reply = QMessageBox.question(self.window, "Confirm Deletion",
                                        f"Delete {self.instrument_data['name']} and {len(self.connections)} connection(s)?",
                                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply != QMessageBox.Yes:
                return
        
        # Get scene
        scene = self.scene()
        if not scene:
            return
            
        # Track original position for undo
        original_pos = self.pos()
        
        # Remove connections
        for conn in list(self.connections):  # Use a copy as we'll modify during iteration
            # Remove line from scene
            scene.removeItem(conn)
            
            # Remove from other instrument's connections
            other_instrument = conn.end_item if conn.start_item == self else conn.start_item
            if conn in other_instrument.connections:
                other_instrument.connections.remove(conn)
                
            # Remove from own connections
            if conn in self.connections:
                self.connections.remove(conn)
        
        # Remove instrument from scene
        scene.removeItem(self)
        
        # Remove from tracking data
        self.window.instrument_positions = [pos for pos in self.window.instrument_positions 
                                          if pos["data"] != self.instrument_data]
        
        # Add to command stack for undo
        self.window.command_stack.append(("delete", self, original_pos))
        
        logger.info(f"Deleted instrument {self.instrument_data['name']}")
        
        # Update experiment status
        self.window.is_modified = True
        self.window.update_title()