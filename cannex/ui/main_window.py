"""
Experiment window implementation for the CANNEX Interface application.
"""
import os
import json
import inspect
import csv
import h5py
import pandas as pd
import numpy as np
from datetime import datetime

from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                            QLabel, QGraphicsScene, QMenuBar, QAction, QStatusBar, QStyle,
                            QSplitter, QScrollArea, QGridLayout, QDialog, QDialogButtonBox,
                            QComboBox, QSpinBox, QCheckBox, QLineEdit, QFormLayout,
                            QMessageBox, QListWidget, QListWidgetItem, QHeaderView, QTabWidget,
                            QTableWidget, QTableWidgetItem, QToolBar, QInputDialog, QFileDialog,
                            QTextEdit, QFrame, QProgressDialog, QColorDialog, QDateTimeEdit, QTreeWidget,
                            QTreeWidgetItem, QGroupBox, QEvent)
from PyQt5.QtCore import (Qt, QDateTime, QTimer, QSize, QPoint, QPointF, QPropertyAnimation,
                         QParallelAnimationGroup, QEasingCurve, QRect, QRectF, QLineF, QRect)
from PyQt5.QtGui import (QPainter, QPen, QColor, QPixmap, QFont, QIcon, QTransform, QBrush,
                        QPainterPath, QRadialGradient)

from cannex.config.constants import (ICON_SIZE, MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT, 
                                   GRID_SPACING, INSTRUMENT_COLORS, EXPERIMENT_COLORS)
from cannex.config.settings import logger, script_dir, experiment_dir
from cannex.ui.widgets.instrument_icon import InstrumentIconItem
from cannex.ui.widgets.connection_line import ConnectionLine
from cannex.ui.widgets.custom_graphics_view import CustomGraphicsView
from cannex.core.data_logger import DataLogger
from cannex.core.data_analyzer import DataAnalyzer
from cannex.utils.helpers import get_function_name
from cannex.utils.exceptions import LabVIEWError
from cannex.core.experiment_sequence import (ExperimentTask, ExperimentSequence, 
                                          SequenceExecutor, SequenceManager)

class SchedulerWidget(QWidget):
    """Widget for scheduling and sequencing experiments"""
    
    def __init__(self, experiment_window, parent=None):
        super().__init__(parent)
        self.experiment_window = experiment_window
        
        # List of sequences
        self.sequences = []
        self.current_sequence = None
        self.executor = None
        
        # Setup layout
        main_layout = QVBoxLayout(self)
        
        # Tabs for different views
        tab_widget = QTabWidget()
        main_layout.addWidget(tab_widget)
        
        # Sequence editor tab
        sequence_tab = QWidget()
        tab_widget.addTab(sequence_tab, "Sequence Editor")
        
        sequence_layout = QHBoxLayout(sequence_tab)
        
        # Sequence list
        sequence_list_layout = QVBoxLayout()
        sequence_layout.addLayout(sequence_list_layout)
        
        sequence_list_layout.addWidget(QLabel("Sequences:"))
        
        self.sequence_tree = QTreeWidget()
        self.sequence_tree.setHeaderLabels(["Name", "Status", "Scheduled"])
        self.sequence_tree.setColumnWidth(0, 150)
        self.sequence_tree.setColumnWidth(1, 80)
        self.sequence_tree.itemClicked.connect(self.sequence_selected)
        sequence_list_layout.addWidget(self.sequence_tree)
        
        # Sequence buttons
        sequence_buttons = QHBoxLayout()
        
        add_sequence_btn = QPushButton("New")
        add_sequence_btn.clicked.connect(self.add_sequence)
        sequence_buttons.addWidget(add_sequence_btn)
        
        delete_sequence_btn = QPushButton("Delete")
        delete_sequence_btn.clicked.connect(self.delete_sequence)
        sequence_buttons.addWidget(delete_sequence_btn)
        
        duplicate_sequence_btn = QPushButton("Duplicate")
        duplicate_sequence_btn.clicked.connect(self.duplicate_sequence)
        sequence_buttons.addWidget(duplicate_sequence_btn)
        
        sequence_list_layout.addLayout(sequence_buttons)
        
        # Task editor
        task_editor_layout = QVBoxLayout()
        sequence_layout.addLayout(task_editor_layout, stretch=2)
        
        task_editor_layout.addWidget(QLabel("Tasks:"))
        
        self.task_tree = QTreeWidget()
        self.task_tree.setHeaderLabels(["Name", "Type", "Target", "Function", "Status"])
        self.task_tree.setColumnWidth(0, 150)
        self.task_tree.setColumnWidth(1, 100)
        self.task_tree.setColumnWidth(2, 150)
        self.task_tree.setColumnWidth(3, 150)
        task_editor_layout.addWidget(self.task_tree)
        
        # Task buttons
        task_buttons = QHBoxLayout()
        
        add_task_btn = QPushButton("Add Task")
        add_task_btn.clicked.connect(self.add_task)
        task_buttons.addWidget(add_task_btn)
        
        delete_task_btn = QPushButton("Delete Task")
        delete_task_btn.clicked.connect(self.delete_task)
        task_buttons.addWidget(delete_task_btn)
        
        move_up_btn = QPushButton("Move Up")
        move_up_btn.clicked.connect(self.move_task_up)
        task_buttons.addWidget(move_up_btn)
        
        move_down_btn = QPushButton("Move Down")
        move_down_btn.clicked.connect(self.move_task_down)
        task_buttons.addWidget(move_down_btn)
        
        task_editor_layout.addLayout(task_buttons)
        
        # Execution controls
        execution_layout = QHBoxLayout()
        task_editor_layout.addLayout(execution_layout)
        
        run_btn = QPushButton("Run")
        run_btn.clicked.connect(self.run_sequence)
        execution_layout.addWidget(run_btn)
        
        pause_btn = QPushButton("Pause")
        pause_btn.clicked.connect(self.pause_sequence)
        execution_layout.addWidget(pause_btn)
        
        stop_btn = QPushButton("Stop")
        stop_btn.clicked.connect(self.stop_sequence)
        execution_layout.addWidget(stop_btn)
        
        schedule_btn = QPushButton("Schedule")
        schedule_btn.clicked.connect(self.schedule_sequence)
        execution_layout.addWidget(schedule_btn)
        
        # Scheduled tab
        scheduled_tab = QWidget()
        tab_widget.addTab(scheduled_tab, "Scheduled")
        
        scheduled_layout = QVBoxLayout(scheduled_tab)
        
        self.scheduled_table = QTableWidget()
        self.scheduled_table.setColumnCount(4)
        self.scheduled_table.setHorizontalHeaderLabels(["Sequence", "Scheduled Time", "Status", "Actions"])
        self.scheduled_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        scheduled_layout.addWidget(self.scheduled_table)
        
        # Results tab
        results_tab = QWidget()
        tab_widget.addTab(results_tab, "Results")
        
        results_layout = QVBoxLayout(results_tab)
        
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(3)
        self.results_table.setHorizontalHeaderLabels(["Task", "Result", "Time"])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        results_layout.addWidget(self.results_table)
        
        # Timer for checking scheduled sequences
        self.schedule_timer = QTimer()
        self.schedule_timer.timeout.connect(self.check_scheduled_sequences)
        self.schedule_timer.start(10000)  # Check every 10 seconds
        
        # Load saved sequences
        self.load_sequences()
        self.update_sequence_tree()
    
    def add_sequence(self):
        """Add a new sequence"""
        dialog = QDialog(self)
        dialog.setWindowTitle("New Sequence")
        
        layout = QFormLayout(dialog)
        
        name_edit = QLineEdit()
        layout.addRow("Sequence Name:", name_edit)
        
        button_box = QHBoxLayout()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")
        
        ok_btn.clicked.connect(dialog.accept)
        cancel_btn.clicked.connect(dialog.reject)
        
        button_box.addWidget(ok_btn)
        button_box.addWidget(cancel_btn)
        layout.addRow(button_box)
        
        if dialog.exec_() == QDialog.Accepted:
            name = name_edit.text().strip()
            if name:
                sequence = ExperimentSequence(name)
                self.sequences.append(sequence)
                self.current_sequence = sequence
                self.update_sequence_tree()
                self.update_task_tree()
                self.save_sequences()
    
    def delete_sequence(self):
        """Delete the selected sequence"""
        if not self.current_sequence:
            return
        
        reply = QMessageBox.question(self, "Delete Sequence", 
                                   f"Delete sequence '{self.current_sequence.name}'?",
                                   QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            self.sequences.remove(self.current_sequence)
            self.current_sequence = None if not self.sequences else self.sequences[0]
            self.update_sequence_tree()
            self.update_task_tree()
            self.save_sequences()
    
    def duplicate_sequence(self):
        """Duplicate the selected sequence"""
        if not self.current_sequence:
            return
        
        # Serialize and deserialize to create a copy
        sequence_dict = self.current_sequence.to_dict()
        sequence_dict["name"] += " (Copy)"
        
        instruments = self.get_all_instruments()
        new_sequence = ExperimentSequence.from_dict(sequence_dict, instruments)
        
        self.sequences.append(new_sequence)
        self.current_sequence = new_sequence
        self.update_sequence_tree()
        self.update_task_tree()
        self.save_sequences()
    
    def sequence_selected(self, item, column):
        """Handle selection of a sequence"""
        sequence_name = item.text(0)
        
        for sequence in self.sequences:
            if sequence.name == sequence_name:
                self.current_sequence = sequence
                self.update_task_tree()
                break
    
    def add_task(self):
        """Add a task to the current sequence"""
        if not self.current_sequence:
            QMessageBox.warning(self, "No Sequence", "Please create or select a sequence first.")
            return
        
        dialog = TaskDialog(self.experiment_window, self)
        
        if dialog.exec_() == QDialog.Accepted:
            task = dialog.get_task()
            self.current_sequence.add_task(task)
            self.update_task_tree()
            self.save_sequences()
    
    def delete_task(self):
        """Delete the selected task"""
        if not self.current_sequence:
            return
        
        selected_items = self.task_tree.selectedItems()
        if not selected_items:
            return
        
        # Get the index of the selected task
        task_index = self.task_tree.indexOfTopLevelItem(selected_items[0])
        
        if 0 <= task_index < len(self.current_sequence.tasks):
            self.current_sequence.remove_task(task_index)
            self.update_task_tree()
            self.save_sequences()
    
    def move_task_up(self):
        """Move the selected task up"""
        if not self.current_sequence:
            return
        
        selected_items = self.task_tree.selectedItems()
        if not selected_items:
            return
        
        # Get the index of the selected task
        task_index = self.task_tree.indexOfTopLevelItem(selected_items[0])
        
        if 0 < task_index < len(self.current_sequence.tasks):
            self.current_sequence.move_task_up(task_index)
            self.update_task_tree()
            
            # Keep selection on the moved item
            self.task_tree.setCurrentItem(self.task_tree.topLevelItem(task_index - 1))
            
            self.save_sequences()
    
    def move_task_down(self):
        """Move the selected task down"""
        if not self.current_sequence:
            return
        
        selected_items = self.task_tree.selectedItems()
        if not selected_items:
            return
        
        # Get the index of the selected task
        task_index = self.task_tree.indexOfTopLevelItem(selected_items[0])
        
        if 0 <= task_index < len(self.current_sequence.tasks) - 1:
            self.current_sequence.move_task_down(task_index)
            self.update_task_tree()
            
            # Keep selection on the moved item
            self.task_tree.setCurrentItem(self.task_tree.topLevelItem(task_index + 1))
            
            self.save_sequences()
    
    def run_sequence(self):
        """Run the current sequence"""
        if not self.current_sequence:
            return
        
        if self.executor and self.executor.isRunning():
            # Resume if paused
            if self.executor.paused:
                self.executor.resume()
            return
        
        # Create and start executor
        self.executor = SequenceExecutor(self.current_sequence)
        
        # Connect signals
        self.executor.task_started.connect(self.task_started)
        self.executor.task_completed.connect(self.task_completed)
        self.executor.task_error.connect(self.task_error)
        self.executor.sequence_completed.connect(self.sequence_completed)
        self.executor.sequence_paused.connect(self.sequence_paused)
        self.executor.sequence_stopped.connect(self.sequence_stopped)
        
        # Start execution
        self.executor.start()
        
        # Update UI
        self.update_sequence_tree()
    
    def pause_sequence(self):
        """Pause the running sequence"""
        if self.executor and self.executor.isRunning() and not self.executor.paused:
            self.executor.pause()
    
    def stop_sequence(self):
        """Stop the running sequence"""
        if self.executor and self.executor.isRunning():
            self.executor.stop()
            self.update_sequence_tree()
    
    def task_started(self, task_index):
        """Handler for when a task starts execution"""
        # Update task tree
        self.update_task_tree()
        
        # Highlight current task
        if 0 <= task_index < self.task_tree.topLevelItemCount():
            item = self.task_tree.topLevelItem(task_index)
            self.task_tree.setCurrentItem(item)
            item.setBackground(0, Qt.yellow)
    
    def task_completed(self, task_index, result):
        """Handler for when a task completes execution"""
        # Update task tree
        self.update_task_tree()
        
        # Add to results table
        if self.current_sequence and 0 <= task_index < len(self.current_sequence.tasks):
            task = self.current_sequence.tasks[task_index]
            
            row = self.results_table.rowCount()
            self.results_table.insertRow(row)
            
            self.results_table.setItem(row, 0, QTableWidgetItem(task.name))
            self.results_table.setItem(row, 1, QTableWidgetItem(str(result)))
            self.results_table.setItem(row, 2, QTableWidgetItem(QDateTime.currentDateTime().toString()))
    
    def task_error(self, task_index, error_msg):
        """Handler for when a task encounters an error"""
        # Update task tree
        self.update_task_tree()
        
        # Show error message
        QMessageBox.warning(self, "Task Error", 
                         f"Error in task {task_index + 1}: {error_msg}")
        
        # Highlight error task in red
        if 0 <= task_index < self.task_tree.topLevelItemCount():
            item = self.task_tree.topLevelItem(task_index)
            item.setBackground(0, Qt.red)
    
    def sequence_completed(self):
        """Handler for when a sequence completes execution"""
        QMessageBox.information(self, "Sequence Complete", 
                              f"Sequence '{self.current_sequence.name}' completed successfully.")
        
        # Update UI
        self.update_sequence_tree()
    
    def sequence_paused(self):
        """Handler for when a sequence is paused"""
        # Update UI
        self.update_sequence_tree()
    
    def sequence_stopped(self):
        """Handler for when a sequence is stopped"""
        # Update UI
        self.update_sequence_tree()
    
    def schedule_sequence(self):
        """Schedule the current sequence for later execution"""
        if not self.current_sequence:
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Schedule Sequence: {self.current_sequence.name}")
        
        layout = QFormLayout(dialog)
        
        datetime_edit = QDateTimeEdit(QDateTime.currentDateTime().addSecs(60))
        datetime_edit.setCalendarPopup(True)
        datetime_edit.setMinimumDateTime(QDateTime.currentDateTime())
        layout.addRow("Execution Time:", datetime_edit)
        
        # Add option for recurrence
        recurrence_check = QCheckBox("Recurring?")
        layout.addRow("", recurrence_check)
        
        recurrence_options = QComboBox()
        recurrence_options.addItems(["Daily", "Weekly", "Monthly", "Custom"])
        recurrence_options.setEnabled(False)
        layout.addRow("Recurrence:", recurrence_options)
        
        recurrence_check.toggled.connect(recurrence_options.setEnabled)
        
        button_box = QHBoxLayout()
        ok_btn = QPushButton("Schedule")
        cancel_btn = QPushButton("Cancel")
        
        ok_btn.clicked.connect(dialog.accept)
        cancel_btn.clicked.connect(dialog.reject)
        
        button_box.addWidget(ok_btn)
        button_box.addWidget(cancel_btn)
        layout.addRow(button_box)
        
        if dialog.exec_() == QDialog.Accepted:
            # Set scheduled time
            self.current_sequence.scheduled_time = datetime_edit.dateTime()
            
            # Handle recurrence
            if recurrence_check.isChecked():
                # Store recurrence info in metadata
                self.current_sequence.recurrence_type = recurrence_options.currentText()
                # In a real app, we'd store more detailed recurrence info
            
            # Update UI
            self.update_sequence_tree()
            self.update_scheduled_table()
            
            # Save sequences
            self.save_sequences()
            
            QMessageBox.information(self, "Sequence Scheduled", 
                                 f"Sequence '{self.current_sequence.name}' scheduled for {self.current_sequence.scheduled_time.toString()}")
    
    def check_scheduled_sequences(self):
        """Check for sequences that need to be executed according to schedule"""
        current_time = QDateTime.currentDateTime()
        
        for sequence in self.sequences:
            if (sequence.status == "stopped" and 
                sequence.scheduled_time and 
                sequence.scheduled_time <= current_time):
                
                # Set current sequence and run it
                self.current_sequence = sequence
                
                # Handle recurrence if applicable
                if hasattr(sequence, 'recurrence_type'):
                    # Reschedule based on recurrence type
                    if sequence.recurrence_type == "Daily":
                        sequence.scheduled_time = sequence.scheduled_time.addDays(1)
                    elif sequence.recurrence_type == "Weekly":
                        sequence.scheduled_time = sequence.scheduled_time.addDays(7)
                    elif sequence.recurrence_type == "Monthly":
                        sequence.scheduled_time = sequence.scheduled_time.addMonths(1)
                    else:
                        # Default: clear schedule after running
                        sequence.scheduled_time = None
                else:
                    # Non-recurring: clear schedule
                    sequence.scheduled_time = None
                
                # Run the sequence
                self.run_sequence()
                
                # Update UI
                self.update_sequence_tree()
                self.update_scheduled_table()
                
                # Save changes
                self.save_sequences()
    
    def update_sequence_tree(self):
        """Update the sequence tree display"""
        self.sequence_tree.clear()
        
        for sequence in self.sequences:
            item = QTreeWidgetItem(self.sequence_tree)
            item.setText(0, sequence.name)
            item.setText(1, sequence.status)
            
            if sequence.scheduled_time:
                item.setText(2, sequence.scheduled_time.toString(Qt.DefaultLocaleShortDate))
                
                # Add recurrence info if applicable
                if hasattr(sequence, 'recurrence_type'):
                    item.setText(2, f"{sequence.scheduled_time.toString(Qt.DefaultLocaleShortDate)} ({sequence.recurrence_type})")
            else:
                item.setText(2, "")
            
            # Highlight current sequence
            if sequence == self.current_sequence:
                for i in range(3):
                    item.setBackground(i, Qt.lightGray)
        
        self.update_scheduled_table()
    
    def update_task_tree(self):
        """Update the task tree display"""
        self.task_tree.clear()
        
        if not self.current_sequence:
            return
        
        for i, task in enumerate(self.current_sequence.tasks):
            item = QTreeWidgetItem(self.task_tree)
            item.setText(0, task.name)
            item.setText(1, task.task_type)
            
            if task.target:
                item.setText(2, task.target.instrument_data["name"])
            else:
                item.setText(2, "")
            
            item.setText(3, task.function or "")
            item.setText(4, task.status)
            
            # Set background color based on status
            if task.status == "running":
                item.setBackground(4, Qt.yellow)
            elif task.status == "complete":
                item.setBackground(4, Qt.green)
            elif task.status == "error":
                item.setBackground(4, Qt.red)
    
    def update_scheduled_table(self):
        """Update the scheduled sequences table"""
        self.scheduled_table.clearContents()
        self.scheduled_table.setRowCount(0)
        
        row = 0
        for sequence in self.sequences:
            if sequence.scheduled_time:
                self.scheduled_table.insertRow(row)
                
                self.scheduled_table.setItem(row, 0, QTableWidgetItem(sequence.name))
                
                # Add recurrence info if applicable
                if hasattr(sequence, 'recurrence_type'):
                    schedule_text = f"{sequence.scheduled_time.toString()} ({sequence.recurrence_type})"
                else:
                    schedule_text = sequence.scheduled_time.toString()
                    
                self.scheduled_table.setItem(row, 1, QTableWidgetItem(schedule_text))
                self.scheduled_table.setItem(row, 2, QTableWidgetItem(sequence.status))
                
                # Add cancel button
                cancel_btn = QPushButton("Cancel")
                cancel_btn.clicked.connect(lambda checked, s=sequence: self.cancel_scheduled_sequence(s))
                self.scheduled_table.setCellWidget(row, 3, cancel_btn)
                
                row += 1
    
    def cancel_scheduled_sequence(self, sequence):
        """Cancel a scheduled sequence"""
        sequence.scheduled_time = None
        if hasattr(sequence, 'recurrence_type'):
            delattr(sequence, 'recurrence_type')
        self.update_sequence_tree()
        self.update_scheduled_table()
        self.save_sequences()
    
    def get_all_instruments(self):
        """Get all instruments from the experiment window"""
        return [item for item in self.experiment_window.scene.items() 
              if hasattr(item, 'instrument_data')]
    
    def save_sequences(self):
        """Save sequences to file"""
        try:
            # Create sequences directory if it doesn't exist
            sequences_dir = os.path.join(script_dir, "sequences")
            os.makedirs(sequences_dir, exist_ok=True)
            
            # Save each sequence to its own file
            for sequence in self.sequences:
                file_path = os.path.join(sequences_dir, f"{sequence.name.replace(' ', '_')}.json")
                
                # Add metadata to sequence before saving
                sequence_data = sequence.to_dict()
                sequence_data["metadata"] = {
                    "last_modified": datetime.now().isoformat(),
                    "modified_by": "HamidHaghmoradi",  # Current user
                    "app_version": "2.0.0"
                }
                
                # Add recurrence info if applicable
                if hasattr(sequence, 'recurrence_type'):
                    sequence_data["recurrence_type"] = sequence.recurrence_type
                
                with open(file_path, 'w') as f:
                    json.dump(sequence_data, f, indent=2)
            
            logger.debug(f"Saved {len(self.sequences)} sequences")
        except Exception as e:
            logger.error(f"Error saving sequences: {str(e)}")
            QMessageBox.warning(self, "Save Error", f"Error saving sequences: {str(e)}")
    
    def load_sequences(self):
        """Load sequences from disk"""
        try:
            # Get sequences directory
            sequences_dir = os.path.join(script_dir, "sequences")
            if not os.path.exists(sequences_dir):
                return
            
            # Get all instruments for reference
            instruments = self.get_all_instruments()
            
            # Load each sequence file
            self.sequences = []
            for file_name in os.listdir(sequences_dir):
                if file_name.endswith('.json'):
                    file_path = os.path.join(sequences_dir, file_name)
                    try:
                        with open(file_path, 'r') as f:
                            data = json.load(f)
                            sequence = ExperimentSequence.from_dict(data, instruments)
                            
                            # Load recurrence info if available
                            if "recurrence_type" in data:
                                sequence.recurrence_type = data["recurrence_type"]
                                
                            self.sequences.append(sequence)
                    except Exception as e:
                        logger.error(f"Error loading sequence {file_name}: {str(e)}")
            
            logger.debug(f"Loaded {len(self.sequences)} sequences")
            
            # Set current sequence if we loaded any
            if self.sequences:
                self.current_sequence = self.sequences[0]
        except Exception as e:
            logger.error(f"Error loading sequences: {str(e)}")


class TaskDialog(QDialog):
    """Dialog for creating or editing tasks"""
    
    def __init__(self, experiment_window, parent=None):
        super().__init__(parent)
        self.experiment_window = experiment_window
        
        self.setWindowTitle("Add Task")
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout(self)
        
        # Task name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Task Name:"))
        self.name_edit = QLineEdit()
        name_layout.addWidget(self.name_edit)
        layout.addLayout(name_layout)
        
        # Task type
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Task Type:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["instrument", "delay", "loop_start", "loop_end", "condition"])
        self.type_combo.currentIndexChanged.connect(self.update_form)
        type_layout.addWidget(self.type_combo)
        layout.addLayout(type_layout)
        
        # Create stacked widget for different task forms
        self.form_layout = QFormLayout()
        layout.addLayout(self.form_layout)
        
        # Instrument form widgets
        self.instrument_combo = QComboBox()
        instruments = self.get_instruments()
        for instrument in instruments:
            self.instrument_combo.addItem(instrument.instrument_data["name"])
        
        self.function_combo = QComboBox()
        self.update_functions()
        
        self.instrument_combo.currentIndexChanged.connect(self.update_functions)
        
        # Delay form widgets
        self.delay_spin = QSpinBox()
        self.delay_spin.setMinimum(0)
        self.delay_spin.setMaximum(3600000)  # 1 hour in ms
        self.delay_spin.setValue(0)
        self.delay_spin.setSuffix(" ms")
        
        # Loop form widgets
        self.repeat_spin = QSpinBox()
        self.repeat_spin.setMinimum(1)
        self.repeat_spin.setMaximum(1000)
        self.repeat_spin.setValue(10)
        
        # Condition form widgets
        self.condition_edit = QLineEdit()
        
        # Parameters
        self.parameters_edit = QLineEdit()
        self.parameters_edit.setPlaceholderText("{'param1': value1, 'param2': value2}")
        
        # Update form based on initial type selection
        self.update_form()
        
        # Buttons
        buttons_layout = QHBoxLayout()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")
        
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        
        buttons_layout.addWidget(ok_btn)
        buttons_layout.addWidget(cancel_btn)
        layout.addLayout(buttons_layout)
    
    def update_form(self):
        """Update form based on task type selection"""
        # Clear previous form
        while self.form_layout.rowCount() > 0:
            self.form_layout.removeRow(0)
        
        task_type = self.type_combo.currentText()
        
        # Add task delay
        self.form_layout.addRow("Delay Before Task (ms):", self.delay_spin)
        
        # Type-specific form
        if task_type == "instrument":
            self.form_layout.addRow("Instrument:", self.instrument_combo)
            self.form_layout.addRow("Function:", self.function_combo)
            self.form_layout.addRow("Parameters:", self.parameters_edit)
        
        elif task_type == "delay":
            self.form_layout.addRow("Delay Seconds:", self.parameters_edit)
            self.parameters_edit.setText("{'seconds': 1}")
        
        elif task_type == "loop_start":
            self.form_layout.addRow("Repeat Count:", self.repeat_spin)
        
        elif task_type == "loop_end":
            # Nothing special needed for loop end
            pass
        
        elif task_type == "condition":
            self.form_layout.addRow("Condition:", self.condition_edit)
            self.form_layout.addRow("Else Jump To:", self.parameters_edit)
            self.parameters_edit.setText("{'else_index': 0}")
    
    def update_functions(self):
        """Update function combo based on selected instrument"""
        self.function_combo.clear()
        
        instrument_name = self.instrument_combo.currentText()
        if not instrument_name:
            return
        
        instrument = self.get_instrument_by_name(instrument_name)
        if not instrument:
            return
        
        # Add functions
        for tag, readable_name in instrument.instrument_data.get("functions", []):
            function_name = readable_name.split(" - ")[1] if " - " in readable_name else readable_name
            self.function_combo.addItem(function_name, tag)
    
    def get_instruments(self):
        """Get all instruments from the experiment window"""
        return [item for item in self.experiment_window.scene.items() 
              if hasattr(item, 'instrument_data')]
    
    def get_instrument_by_name(self, name):
        """Get instrument by name"""
        instruments = self.get_instruments()
        for instrument in instruments:
            if instrument.instrument_data["name"] == name:
                return instrument
        return None
    
    def get_task(self):
        """Create a task from the dialog inputs"""
        task_name = self.name_edit.text().strip()
        if not task_name:
            task_name = f"Task_{self.type_combo.currentText()}_{int(time.time())}"
        
        task_type = self.type_combo.currentText()
        
        target = None
        function = None
        parameters = {}
        delay = self.delay_spin.value()
        repeat = self.repeat_spin.value()
        condition = None
        
        if task_type == "instrument":
            instrument_name = self.instrument_combo.currentText()
            target = self.get_instrument_by_name(instrument_name)
            function = self.function_combo.currentText()
            
            # Parse parameters
            try:
                param_text = self.parameters_edit.text().strip()
                if param_text:
                    parameters = eval(param_text)
                    if not isinstance(parameters, dict):
                        parameters = {}
            except:
                parameters = {}
        
        elif task_type == "delay":
            try:
                param_text = self.parameters_edit.text().strip()
                if param_text:
                    parameters = eval(param_text)
                    if not isinstance(parameters, dict):
                        parameters = {"seconds": 1}
            except:
                parameters = {"seconds": 1}
        
        elif task_type == "condition":
            condition = self.condition_edit.text().strip()
            try:
                param_text = self.parameters_edit.text().strip()
                if param_text:
                    parameters = eval(param_text)
                    if not isinstance(parameters, dict):
                        parameters = {}
            except:
                parameters = {}
        
        return ExperimentTask(
            name=task_name,
            task_type=task_type,
            target=target,
            function=function,
            parameters=parameters,
            delay=delay,
            repeat=repeat,
            condition=condition
        )


class ExperimentWindow(QMainWindow):
    """Window for creating and editing experiments"""
    def __init__(self, experiment_name, slot_window):
        super().__init__()
        self.experiment_name = experiment_name
        self.slot_window = slot_window
        self.instrument_positions = []
        self.command_stack = []
        self.redo_stack = []
        self.connecting_mode = False
        self.start_instrument = None
        self.connections = []
        self.zoom_level = 1.0
        self.is_modified = False
        self.data_logger = DataLogger(experiment_name)
        self.logged_instruments = []
        
        # Set up the window
        self.setWindowTitle(f"CANNEX - {experiment_name}")
        self.setGeometry(100, 100, 1200, 800)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Create main content area with splitter
        main_splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(main_splitter)
        
        # Create left panel (sidebar)
        sidebar = QWidget()
        sidebar.setMinimumWidth(200)
        sidebar.setMaximumWidth(300)
        sidebar_layout = QVBoxLayout(sidebar)
        
        # Sidebar tabs
        sidebar_tabs = QTabWidget()
        sidebar_layout.addWidget(sidebar_tabs)
        
        # Instruments tab
        instruments_tab = QWidget()
        instruments_layout = QVBoxLayout(instruments_tab)
        
        instruments_layout.addWidget(QLabel("Instrument Library"))
        
        # Sidebar instrument container (scrollable)
        instruments_scroll = QScrollArea()
        instruments_scroll.setWidgetResizable(True)
        
        # Create container for instrument buttons
        instrument_container = QWidget()
        self.instrument_layout = QVBoxLayout(instrument_container)
        self.instrument_layout.setAlignment(Qt.AlignTop)
        self.instrument_layout.setSpacing(10)
        
        instruments_scroll.setWidget(instrument_container)
        instruments_layout.addWidget(instruments_scroll)
        
        sidebar_tabs.addTab(instruments_tab, "Instruments")
        
        # Sequences tab
        sequences_tab = QWidget()
        sequences_layout = QVBoxLayout(sequences_tab)
        
        # We'll create the scheduler widget later after we have the view
        sidebar_tabs.addTab(sequences_tab, "Sequences")
        
        # Analysis tab
        analysis_tab = QWidget()
        analysis_layout = QVBoxLayout(analysis_tab)
        
        # Data logging controls
        logging_group = QGroupBox("Data Logging")
        logging_layout = QVBoxLayout(logging_group)
        
        # Logging interval
        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("Log Interval:"))
        self.log_interval_spin = QSpinBox()
        self.log_interval_spin.setRange(100, 60000)  # 100ms to 1 minute
        self.log_interval_spin.setSingleStep(100)
        self.log_interval_spin.setValue(1000)
        self.log_interval_spin.setSuffix(" ms")
        self.log_interval_spin.valueChanged.connect(self.update_log_interval)
        interval_layout.addWidget(self.log_interval_spin)
        logging_layout.addLayout(interval_layout)
        
        # Auto-save checkbox
        self.auto_save_check = QCheckBox("Auto-save logs")
        self.auto_save_check.toggled.connect(self.toggle_auto_save)
        logging_layout.addWidget(self.auto_save_check)
        
        # Start/stop logging button
        self.logging_btn = QPushButton("Start Logging")
        self.logging_btn.clicked.connect(self.toggle_logging)
        logging_layout.addWidget(self.logging_btn)
        
        # Export logs button
        export_logs_btn = QPushButton("Export Logs")
        export_logs_btn.clicked.connect(self.export_logs)
        logging_layout.addWidget(export_logs_btn)
        
        analysis_layout.addWidget(logging_group)
        
        # Analysis tools
        analysis_group = QGroupBox("Analysis Tools")
        analysis_tools_layout = QVBoxLayout(analysis_group)
        
        # Statistics button
        stats_btn = QPushButton("Calculate Statistics")
        stats_btn.clicked.connect(self.show_statistics)
        analysis_tools_layout.addWidget(stats_btn)
        
        # Plot button
        plot_btn = QPushButton("Plot Data")
        plot_btn.clicked.connect(self.plot_data)
        analysis_tools_layout.addWidget(plot_btn)
        
        # Analysis panel
        analysis_layout.addWidget(analysis_group)
        
        sidebar_tabs.addTab(analysis_tab, "Analysis")
        
        # Add sidebar to splitter
        main_splitter.addWidget(sidebar)
        
        # Create right panel (canvas)
        canvas_container = QWidget()
        canvas_layout = QVBoxLayout(canvas_container)
        canvas_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create scene and view for the experiment canvas
        self.scene = QGraphicsScene(self)
        self.scene.setSceneRect(0, 0, 5000, 5000)
        
        self.view = CustomGraphicsView(self.scene, self)
        canvas_layout.addWidget(self.view)
        
        # Add canvas to splitter
        main_splitter.addWidget(canvas_container)
        
        # Set initial splitter sizes
        main_splitter.setSizes([200, 800])
        
        # NOW create the toolbar - after self.view is initialized
        self.create_toolbar()
        
        # Create scheduler widget now that we have self.view
        self.scheduler_widget = SchedulerWidget(self)
        sequences_layout.addWidget(self.scheduler_widget)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
        
        # Add zoom indicator to status bar
        self.zoom_label = QLabel("Zoom: 100%")
        self.status_bar.addPermanentWidget(self.zoom_label)
        
        # Add grid status to status bar
        self.grid_label = QLabel("Grid: On")
        self.status_bar.addPermanentWidget(self.grid_label)
        
        # Add snap status to status bar
        self.snap_label = QLabel("Snap: Off")
        self.status_bar.addPermanentWidget(self.snap_label)
        
        # Auto-save timer
        self.auto_save_timer = QTimer()
        self.auto_save_timer.timeout.connect(lambda: self.save_experiment(silent=True))
        self.auto_save_timer.start(60000)  # Save every minute
        
        # Load instruments into sidebar
        self.load_instruments()
        
        # Set up connections handler
        self.view.scene().selectionChanged.connect(self.handle_selection_changed)
    
    def create_toolbar(self):
        """Create the main toolbar"""
        self.toolbar = QToolBar("Main Toolbar")
        self.toolbar.setIconSize(QSize(32, 32))
        self.toolbar.setMovable(False)
        self.addToolBar(self.toolbar)
        
        # File operations
        save_action = self.toolbar.addAction("Save")
        save_action.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        save_action.triggered.connect(self.save_experiment)
        save_action.setToolTip("Save Experiment")
        
        self.toolbar.addSeparator()
        
        # Execution
        run_action = self.toolbar.addAction("Run All")
        run_action.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        run_action.triggered.connect(self.run_all)
        run_action.setToolTip("Run All Instruments")
        
        # Data visualization
        graph_action = self.toolbar.addAction("Graph")
        graph_action.setIcon(self.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        graph_action.triggered.connect(self.show_graph_window)
        graph_action.setToolTip("Show Graph Window")
        
        self.toolbar.addSeparator()
        
        # Edit operations
        undo_action = self.toolbar.addAction("Undo")
        undo_action.setIcon(self.style().standardIcon(QStyle.SP_ArrowBack))
        undo_action.triggered.connect(self.undo)
        undo_action.setToolTip("Undo")
        
        redo_action = self.toolbar.addAction("Redo")
        redo_action.setIcon(self.style().standardIcon(QStyle.SP_ArrowForward))
        redo_action.triggered.connect(self.redo)
        redo_action.setToolTip("Redo")
        
        self.toolbar.addSeparator()
        
        # Connection mode
        connect_action = self.toolbar.addAction("Connect")
        connect_action.setIcon(self.style().standardIcon(QStyle.SP_ArrowRight))
        connect_action.triggered.connect(self.toggle_connecting_mode)
        connect_action.setToolTip("Connect Instruments")
        
        # Grid controls
        grid_action = self.toolbar.addAction("Grid")
        grid_action.setIcon(self.style().standardIcon(QStyle.SP_FileDialogListView))
        grid_action.triggered.connect(self.toggle_grid)
        grid_action.setToolTip("Toggle Grid")
        
        snap_action = self.toolbar.addAction("Snap")
        snap_action.setIcon(self.style().standardIcon(QStyle.SP_DialogApplyButton))
        snap_action.triggered.connect(self.toggle_snap)
        snap_action.setToolTip("Toggle Snap to Grid")
        
        self.toolbar.addSeparator()
        
        # Zoom controls
        zoom_in_action = self.toolbar.addAction("Zoom In")
        zoom_in_action.setIcon(self.style().standardIcon(QStyle.SP_FileDialogInfoView))
        zoom_in_action.triggered.connect(self.zoom_in)
        zoom_in_action.setToolTip("Zoom In")
        
        zoom_out_action = self.toolbar.addAction("Zoom Out")
        zoom_out_action.setIcon(self.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        zoom_out_action.triggered.connect(self.zoom_out)
        zoom_out_action.setToolTip("Zoom Out")
        
        zoom_fit_action = self.toolbar.addAction("Fit")
        zoom_fit_action.setIcon(self.style().standardIcon(QStyle.SP_FileDialogContentsView))
        zoom_fit_action.triggered.connect(self.view.fit_content)
        zoom_fit_action.setToolTip("Fit All Content")
        
        reset_zoom_action = self.toolbar.addAction("100%")
        reset_zoom_action.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        reset_zoom_action.triggered.connect(self.view.reset_zoom)
        reset_zoom_action.setToolTip("Reset Zoom to 100%")
        
        self.toolbar.addSeparator()
        
        # Export
        export_action = self.toolbar.addAction("Export")
        export_action.setIcon(self.style().standardIcon(QStyle.SP_FileLinkIcon))
        export_action.triggered.connect(self.export_experiment)
        export_action.setToolTip("Export Experiment")
    
    def update_zoom_display(self, zoom_factor):
        """Update the zoom display in the status bar"""
        self.zoom_label.setText(f"Zoom: {zoom_factor * 100:.0f}%")
    
    def zoom_in(self):
        """Zoom in the view"""
        self.view.scale(1.25, 1.25)
        self.view.zoom_factor *= 1.25
        self.update_zoom_display(self.view.zoom_factor)
    
    def zoom_out(self):
        """Zoom out the view"""
        self.view.scale(0.8, 0.8)
        self.view.zoom_factor *= 0.8
        self.update_zoom_display(self.view.zoom_factor)
    
    def toggle_grid(self):
        """Toggle the grid visibility"""
        self.view.toggle_grid()
        self.grid_label.setText(f"Grid: {'On' if self.view.show_grid else 'Off'}")
    
    def toggle_snap(self):
        """Toggle snap to grid"""
        is_snap_on = self.view.toggle_snap_to_grid()
        self.snap_label.setText(f"Snap: {'On' if is_snap_on else 'Off'}")
    
    def update_title(self):
        """Update the window title to show modified status"""
        modified_indicator = "*" if self.is_modified else ""
        self.setWindowTitle(f"CANNEX - {self.experiment_name}{modified_indicator}")
    
    def eventFilter(self, obj, event):
        """Handle events for child widgets"""
        if obj == self.view and event.type() == QEvent.Resize:
            self.update_reset_zoom_position()
        return super().eventFilter(obj, event)
    
    def update_reset_zoom_position(self):
        """Update position of reset zoom button to top-right corner"""
        if hasattr(self, 'reset_zoom_btn'):
            self.reset_zoom_btn.move(self.view.width() - 40, 10)
    
    def load_instruments(self):
        """Load instruments from slot window into sidebar"""
        # Clear existing buttons
        for i in reversed(range(self.instrument_layout.count())):
            item = self.instrument_layout.itemAt(i)
            if item.widget():
                item.widget().deleteLater()
        
        # Add instruments from slot window
        from cannex.ui.widgets.draggable_instrument_button import DraggableInstrumentButton
        
        for data in self.slot_window.instrument_data.values():
            # Create pixmap
            pixmap = self.slot_window.create_instrument_icon(data["name"])
            
            # Create button
            button = DraggableInstrumentButton(pixmap, data, self)
            
            # Add to layout
            self.instrument_layout.addWidget(button)
        
        logger.debug(f"Loaded {len(self.slot_window.instrument_data)} instruments into sidebar")
    
    def toggle_connecting_mode(self):
        """Toggle the connecting mode for creating connections between instruments"""
        self.connecting_mode = not self.connecting_mode
        if self.connecting_mode:
            self.view.setCursor(Qt.CrossCursor)
            self.status_bar.showMessage("Connection Mode: Click on two instruments to connect them")
            logger.info("Entered connecting mode")
        else:
            self.view.setCursor(Qt.ArrowCursor)
            self.start_instrument = None
            self.status_bar.showMessage("Ready")
            logger.info("Exited connecting mode")
    
    def add_connection(self, start_item, end_item):
        """Add a connection line between two instruments"""
        # Check if already connected
        for conn in self.connections:
            if (conn[0] == start_item and conn[1] == end_item) or \
               (conn[0] == end_item and conn[1] == start_item):
                logger.warning(f"Instruments {start_item.instrument_data['name']} and {end_item.instrument_data['name']} are already connected")
                QMessageBox.information(self, "Connect", "These instruments are already connected")
                return
        
        # Create connection line
        line = ConnectionLine(start_item, end_item)
        self.scene.addItem(line)
        
        # Add to connections lists
        start_item.connections.append(line)
        end_item.connections.append(line)
        self.connections.append((start_item, end_item, line))
        
        # Add to command stack for undo
        self.command_stack.append(("connect", line, (start_item, end_item)))
        
        # Mark experiment as modified
        self.is_modified = True
        self.update_title()
        
        logger.info(f"Connected {start_item.instrument_data['name']} to {end_item.instrument_data['name']}")
        self.status_bar.showMessage(f"Connected {start_item.instrument_data['name']} to {end_item.instrument_data['name']}")
    
    def handle_selection_changed(self):
        """Handle selection changes in the scene"""
        selected_items = self.scene.selectedItems()
        if selected_items:
            for item in selected_items:
                if isinstance(item, InstrumentIconItem):
                    self.status_bar.showMessage(f"Selected: {item.instrument_data['name']}")
                    break
        else:
            self.status_bar.showMessage("Ready")
    
    def save_experiment(self, silent=False):
        """Save the experiment to disk"""
        try:
            # Create experiment data structure
            experiment_data = {
                "version": "2.0",
                "name": self.experiment_name,
                "created_by": "HamidHaghmoradi",  # Get current user
                "creation_date": QDateTime.currentDateTime().toString(Qt.ISODate),
                "instrument_positions": [
                    {
                        "data": pos["data"]["name"],
                        "pos": [pos["pos"].x(), pos["pos"].y()],
                        "function": pos["function"],
                        "function_tag": None  # Will be filled in during load
                    } for pos in self.instrument_positions
                ],
                "connections": [
                    {
                        "from": conn[0].instrument_data["name"],
                        "to": conn[1].instrument_data["name"],
                        "direction": conn[2].direction,
                        "datatype": conn[2].datatype,
                        "order": conn[2].order
                    } for conn in self.connections
                ]
            }
            
            # Save to file
            experiments_dir = os.path.join(script_dir, "experiments")
            os.makedirs(experiments_dir, exist_ok=True)
            
            file_path = os.path.join(experiments_dir, f"{self.experiment_name}.json")
            with open(file_path, 'w') as f:
                json.dump(experiment_data, f, indent=2)
            
            # Reset modified flag
            self.is_modified = False
            self.update_title()
            
            if not silent:
                logger.info(f"Saved experiment '{self.experiment_name}' with {len(self.instrument_positions)} instruments and {len(self.connections)} connections")
                QMessageBox.information(self, "Save", f"Experiment '{self.experiment_name}' saved successfully")
            
            return True
        except Exception as e:
            if not silent:
                logger.error(f"Failed to save experiment: {str(e)}")
                QMessageBox.critical(self, "Save Error", f"Failed to save experiment: {str(e)}")
            return False
    
    def load_experiment_data(self, data):
        """Load experiment data from saved file"""
        try:
            # Clear existing items
            self.scene.clear()
            self.instrument_positions = []
            self.connections = []
            
            # Load instruments
            instrument_map = {}  # Map names to items
            
            # Add instruments to scene
            for item_data in data.get("instrument_positions", []):
                instrument_name = item_data["data"]
                
                # Find instrument data
                instrument_data = None
                for instr_data in self.slot_window.instrument_data.values():
                    if instr_data["name"] == instrument_name:
                        instrument_data = instr_data
                        break
                
                if not instrument_data:
                    logger.warning(f"Instrument {instrument_name} not found in library, skipping")
                    continue
                
                # Create functions list if not present
                if "functions" not in instrument_data:
                    functions = []
                    for idx, (method_name, method) in enumerate(inspect.getmembers(instrument_data["driver_class"])):
                        if (inspect.ismethoddescriptor(method) or inspect.isfunction(method) or 
                            callable(method)) and not method_name.startswith("__"):
                            tag, readable_name = get_function_name(method_name, instrument_name, idx)
                            functions.append((tag, readable_name))
                    instrument_data["functions"] = functions
                
                # Create pixmap
                pixmap = self.slot_window.create_instrument_icon(instrument_name)
                
                # Create item
                item = InstrumentIconItem(pixmap, instrument_data, self)
                
                # Set position
                pos = QPointF(item_data["pos"][0], item_data["pos"][1])
                item.setPos(pos)
                
                # Set function if available
                function_name = item_data.get("function")
                if function_name:
                    for tag, readable in instrument_data["functions"]:
                        if readable.split(" - ")[1] == function_name:
                            item.set_function(tag, function_name)
                            break
                
                # Add to scene
                self.scene.addItem(item)
                
                # Add to tracking data
                self.instrument_positions.append({
                    "data": instrument_data,
                    "pos": pos,
                    "function": function_name
                })
                
                # Add to map
                instrument_map[instrument_name] = item
            
            # Add connections
            for conn_data in data.get("connections", []):
                from_name = conn_data["from"]
                to_name = conn_data["to"]
                
                if from_name in instrument_map and to_name in instrument_map:
                    start_item = instrument_map[from_name]
                    end_item = instrument_map[to_name]
                    
                    # Create connection
                    line = ConnectionLine(start_item, end_item)
                    
                    # Set properties
                    if "direction" in conn_data:
                        line.direction = conn_data["direction"]
                    if "datatype" in conn_data:
                        line.datatype = conn_data["datatype"]
                    if "order" in conn_data:
                        line.order = conn_data["order"]
                    
                    # Add to scene
                    self.scene.addItem(line)
                    
                    # Add to connections lists
                    start_item.connections.append(line)
                    end_item.connections.append(line)
                    self.connections.append((start_item, end_item, line))
                else:
                    logger.warning(f"Cannot create connection: {from_name} -> {to_name}, instruments not found")
            
            # Reset modification flag
            self.is_modified = False
            self.update_title()
            
            logger.info(f"Loaded experiment '{self.experiment_name}' with {len(self.instrument_positions)} instruments and {len(self.connections)} connections")
            self.status_bar.showMessage(f"Loaded experiment '{self.experiment_name}'")
            return True
        except Exception as e:
            logger.error(f"Failed to load experiment data: {str(e)}")
            QMessageBox.critical(self, "Load Error", f"Failed to load experiment: {str(e)}")
            return False
    
    def toggle_logging(self):
        """Toggle data logging on/off"""
        if self.data_logger.is_logging:
            # Stop logging
            self.data_logger.stop_logging()
            self.logging_btn.setText("Start Logging")
            self.status_bar.showMessage("Data logging stopped")
        else:
            # Start logging with all instruments that have functions
            instruments_to_log = [item for item in self.scene.items() 
                                if isinstance(item, InstrumentIconItem) and 
                                item.selected_function is not None]
            
            if not instruments_to_log:
                QMessageBox.warning(self, "Data Logging", 
                                  "No instruments with functions found. Please assign functions first.")
                return
            
            # Start logging
            self.data_logger.start_logging(instruments_to_log)
            self.logged_instruments = instruments_to_log
            self.logging_btn.setText("Stop Logging")
            self.status_bar.showMessage(f"Data logging started with {len(instruments_to_log)} instruments")
    
    def update_log_interval(self, value):
        """Update the logging interval"""
        self.data_logger.log_interval = value
        if self.data_logger.log_timer:
            self.data_logger.log_timer.stop()
            self.data_logger.log_timer.start(value)
        logger.debug(f"Updated logging interval to {value}ms")
    
    def toggle_auto_save(self, checked):
        """Toggle auto-save for data logging"""
        self.data_logger.auto_save = checked
        if checked and self.data_logger.is_logging:
            # Start auto-save timer
            if not self.data_logger.auto_save_timer:
                self.data_logger.auto_save_timer = QTimer()
                self.data_logger.auto_save_timer.timeout.connect(self.data_logger.save_data)
                self.data_logger.auto_save_timer.start(self.data_logger.auto_save_interval)
        elif self.data_logger.auto_save_timer:
            # Stop auto-save timer
            self.data_logger.auto_save_timer.stop()
            self.data_logger.auto_save_timer = None
    
    def export_logs(self):
        """Export logged data"""
        if not self.data_logger_name:
            {
                "driver_class": TestDriver,
                "functions": functions,
                "added_by": self.user_manager.current_user.username,
                "added_date": datetime.now().isoformat()
            }
                
        # Update all buttons
        self.init_instrument_slots()
        
        # Create test experiments
        for i in range(1, 4):
            exp_name = f"Test Experiment {i}"
            self.experiments[exp_name] = {
                "window": None,
                "active": i % 2 == 0,  # Make every second experiment active
                "created_by": self.user_manager.current_user.username,
                "creation_date": datetime.now().isoformat()
            }
        
        # Update experiment display
        self.update_experiment_tiles()
        
        logger.info("Created test instruments and experiments")
    
    def closeEvent(self, event):
        """Handle window close event"""
        # Check if any experiment windows are open
        open_windows = False
        for exp_data in self.experiments.values():
            if exp_data["window"] is not None:
                open_windows = True
                break
        
        if open_windows:
            QMessageBox.warning(self, "Cannot Close", 
                             "Please close all experiment windows before exiting.")
            event.ignore()
            return
        
        # Confirm exit
        reply = QMessageBox.question(self, "Exit",
                                  "Are you sure you want to exit?",
                                  QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            # Clean up and exit
            self.shutdown_instruments()
            event.accept()
        else:
            event.ignore()
    
    def shutdown_instruments(self):
        """Safely shutdown all instruments"""
        logger.info("Shutting down instruments...")
        # Perform any cleanup needed for instruments
        # Here you would add code to properly close instrument connections
        logger.info("All instruments shut down safely")