"""Experiment sequencing functionality."""
import time
import json
import os
from datetime import datetime
from PyQt5.QtCore import QThread, QDateTime, Qt, pyqtSignal

from cannex.config.settings import sequence_dir, logger
from cannex.utils.exceptions import LabVIEWError

class ExperimentTask:
    """Represents a single task in an experiment sequence"""
    
    def __init__(self, name, task_type, target=None, function=None, parameters=None, 
                 delay=0, repeat=1, condition=None):
        self.name = name
        self.task_type = task_type  # "instrument", "delay", "loop_start", "loop_end", "condition"
        self.target = target  # Instrument object or None
        self.function = function  # Function name or None
        self.parameters = parameters or {}  # Parameters for function
        self.delay = delay  # Delay in ms before this task
        self.repeat = repeat  # Number of times to repeat (for loop_start)
        self.condition = condition  # Condition expression (for conditional branching)
        self.result = None  # Result of execution
        self.status = "pending"  # "pending", "running", "complete", "error"
    
    def to_dict(self):
        """Convert task to dictionary for serialization"""
        return {
            "name": self.name,
            "task_type": self.task_type,
            "target": self.target.instrument_data["name"] if self.target else None,
            "function": self.function,
            "parameters": self.parameters,
            "delay": self.delay,
            "repeat": self.repeat,
            "condition": self.condition
        }
    
    @classmethod
    def from_dict(cls, data, instruments):
        """Create task from dictionary, with instrument lookup"""
        # Find target instrument if specified
        target = None
        if data.get("target"):
            for instrument in instruments:
                if instrument.instrument_data["name"] == data["target"]:
                    target = instrument
                    break
        
        return cls(
            name=data["name"],
            task_type=data["task_type"],
            target=target,
            function=data.get("function"),
            parameters=data.get("parameters", {}),
            delay=data.get("delay", 0),
            repeat=data.get("repeat", 1),
            condition=data.get("condition")
        )


class ExperimentSequence:
    """Represents a sequence of tasks in an experiment"""
    
    def __init__(self, name):
        self.name = name
        self.tasks = []
        self.scheduled_time = None  # For scheduled execution
        self.current_task = 0  # Index of current task
        self.status = "stopped"  # "stopped", "running", "paused", "complete"
        self.loop_stack = []  # Stack of (start_index, current_iteration, max_iterations)
        self.results = {}  # Dictionary to store results
    
    def add_task(self, task):
        """Add a task to the sequence"""
        self.tasks.append(task)
    
    def remove_task(self, index):
        """Remove a task from the sequence"""
        if 0 <= index < len(self.tasks):
            self.tasks.pop(index)
    
    def move_task_up(self, index):
        """Move a task up in the sequence"""
        if 0 < index < len(self.tasks):
            self.tasks[index], self.tasks[index-1] = self.tasks[index-1], self.tasks[index]
    
    def move_task_down(self, index):
        """Move a task down in the sequence"""
        if 0 <= index < len(self.tasks) - 1:
            self.tasks[index], self.tasks[index+1] = self.tasks[index+1], self.tasks[index]
    
    def to_dict(self):
        """Convert sequence to dictionary for serialization"""
        return {
            "name": self.name,
            "tasks": [task.to_dict() for task in self.tasks],
            "scheduled_time": self.scheduled_time.toString(Qt.ISODate) if self.scheduled_time else None
        }
    
    @classmethod
    def from_dict(cls, data, instruments):
        """Create sequence from dictionary, with instrument lookup"""
        sequence = cls(data["name"])
        
        for task_data in data.get("tasks", []):
            task = ExperimentTask.from_dict(task_data, instruments)
            sequence.add_task(task)
        
        if data.get("scheduled_time"):
            sequence.scheduled_time = QDateTime.fromString(data["scheduled_time"], Qt.ISODate)
        
        return sequence
    
    def reset(self):
        """Reset sequence for execution"""
        self.current_task = 0
        self.status = "stopped"
        self.loop_stack = []
        self.results = {}
        
        # Reset all tasks
        for task in self.tasks:
            task.status = "pending"
            task.result = None

class SequenceExecutor(QThread):
    """Thread for executing experiment sequences"""
    
    task_started = pyqtSignal(int)  # Emits index of started task
    task_completed = pyqtSignal(int, object)  # Emits index and result of completed task
    task_error = pyqtSignal(int, str)  # Emits index and error message
    sequence_completed = pyqtSignal()  # Emits when sequence completes
    sequence_paused = pyqtSignal()  # Emits when sequence is paused
    sequence_stopped = pyqtSignal()  # Emits when sequence is stopped
    
    def __init__(self, sequence):
        super().__init__()
        self.sequence = sequence
        self.paused = False
        self.stopped = False
    
    def run(self):
        """Execute the sequence"""
        sequence = self.sequence
        sequence.reset()
        sequence.status = "running"
        
        while sequence.current_task < len(sequence.tasks) and not self.stopped:
            # Check if paused
            while self.paused and not self.stopped:
                sequence.status = "paused"
                self.sequence_paused.emit()
                time.sleep(0.1)
            
            if self.stopped:
                break
            
            sequence.status = "running"
            
            # Get current task
            task_index = sequence.current_task
            task = sequence.tasks[task_index]
            
            # Handle delay
            if task.delay > 0:
                time.sleep(task.delay / 1000.0)
            
            # Execute task based on type
            task.status = "running"
            self.task_started.emit(task_index)
            
            try:
                if task.task_type == "instrument":
                    # Execute instrument function
                    if task.target and task.function:
                        # Set parameters
                        original_params = task.target.parameters.copy()
                        task.target.parameters = task.parameters
                        
                        # Run function
                        result = task.target.run_function()
                        
                        # Restore parameters
                        task.target.parameters = original_params
                        
                        task.result = result
                        sequence.results[task.name] = result
                    else:
                        raise ValueError("Invalid instrument or function")
                
                elif task.task_type == "delay":
                    # Just a delay
                    time.sleep(task.parameters.get("seconds", 1))
                    task.result = f"Delayed {task.parameters.get('seconds', 1)} seconds"
                
                elif task.task_type == "loop_start":
                    # Start of a loop
                    sequence.loop_stack.append((task_index, 0, task.repeat))
                    task.result = f"Loop started ({task.repeat} iterations)"
                
                elif task.task_type == "loop_end":
                    # End of a loop
                    if sequence.loop_stack:
                        start_index, current_iter, max_iter = sequence.loop_stack[-1]
                        current_iter += 1
                        
                        if current_iter < max_iter:
                            # Jump back to start of loop
                            sequence.loop_stack[-1] = (start_index, current_iter, max_iter)
                            sequence.current_task = start_index
                            task.result = f"Loop iteration {current_iter+1}/{max_iter}"
                            self.task_completed.emit(task_index, task.result)
                            continue
                        else:
                            # Loop complete
                            sequence.loop_stack.pop()
                            task.result = "Loop complete"
                    else:
                        task.result = "Warning: Loop end without matching start"
                
                elif task.task_type == "condition":
                    # Conditional branching
                    condition = task.condition
                    result = False
                    
                    # Simple condition evaluation
                    if condition and "==" in condition:
                        parts = condition.split("==")
                        if len(parts) == 2:
                            left, right = parts
                            left = left.strip()
                            right = right.strip()
                            
                            # Check if left is a reference to a result
                            if left in sequence.results:
                                left_value = sequence.results[left]
                                
                                # Try to convert right to appropriate type
                                try:
                                    if isinstance(left_value, int):
                                        right_value = int(right)
                                    elif isinstance(left_value, float):
                                        right_value = float(right)
                                    else:
                                        right_value = right
                                    
                                    result = (left_value == right_value)
                                except:
                                    result = False
                    
                    task.result = f"Condition evaluated to {result}"
                    
                    if not result and task_index + 1 < len(sequence.tasks) and task.parameters.get("else_index"):
                        # Jump to else branch
                        jump_index = int(task.parameters.get("else_index"))
                        if 0 <= jump_index < len(sequence.tasks):
                            sequence.current_task = jump_index
                            self.task_completed.emit(task_index, task.result)
                            continue
                else:
                    task.result = f"Unknown task type: {task.task_type}"
                
                task.status = "complete"
                self.task_completed.emit(task_index, task.result)
            
            except Exception as e:
                task.status = "error"
                error_msg = str(e)
                task.result = f"Error: {error_msg}"
                self.task_error.emit(task_index, error_msg)
                
                # Stop execution on error unless configured to continue
                if not task.parameters.get("continue_on_error", False):
                    sequence.status = "stopped"
                    self.stopped = True
                    break
            
            # Move to next task
            sequence.current_task += 1
        
        if sequence.current_task >= len(sequence.tasks) and not self.stopped:
            sequence.status = "complete"
            self.sequence_completed.emit()
        else:
            sequence.status = "stopped"
            self.sequence_stopped.emit()
    
    def pause(self):
        """Pause execution"""
        self.paused = True
    
    def resume(self):
        """Resume execution"""
        self.paused = False
    
    def stop(self):
        """Stop execution"""
        self.stopped = True

class SequenceManager:
    """Manages experiment sequences"""
    
    def __init__(self):
        self.sequences = []
        self.executors = {}  # Map sequence names to executors
    
    def load_sequences(self, instruments):
        """Load sequences from disk"""
        try:
            # Create sequences directory if it doesn't exist
            os.makedirs(sequence_dir, exist_ok=True)
            
            # Load each sequence file
            sequences = []
            for file_name in os.listdir(sequence_dir):
                if file_name.endswith('.json'):
                    file_path = os.path.join(sequence_dir, file_name)
                    try:
                        with open(file_path, 'r') as f:
                            data = json.load(f)
                            sequence = ExperimentSequence.from_dict(data, instruments)
                            
                            # Load recurrence info if available
                            if "recurrence_type" in data:
                                sequence.recurrence_type = data["recurrence_type"]
                                
                            sequences.append(sequence)
                    except Exception as e:
                        logger.error(f"Error loading sequence {file_name}: {str(e)}")
            
            self.sequences = sequences
            logger.debug(f"Loaded {len(sequences)} sequences")
            return sequences
        except Exception as e:
            logger.error(f"Error loading sequences: {str(e)}")
            return []
    
    def save_sequences(self):
        """Save sequences to disk"""
        try:
            # Create sequences directory if it doesn't exist
            os.makedirs(sequence_dir, exist_ok=True)
            
            # Save each sequence to its own file
            for sequence in self.sequences:
                file_path = os.path.join(sequence_dir, f"{sequence.name.replace(' ', '_')}.json")
                
                # Add metadata to sequence before saving
                sequence_data = sequence.to_dict()
                sequence_data["metadata"] = {
                    "last_modified": datetime.now().isoformat(),
                    "modified_by": "HamidHaghmoradi",  # Current user
                    "app_version": "2.0.0"  # App version
                }
                
                # Add recurrence info if applicable
                if hasattr(sequence, 'recurrence_type'):
                    sequence_data["recurrence_type"] = sequence.recurrence_type
                
                with open(file_path, 'w') as f:
                    json.dump(sequence_data, f, indent=2)
            
            logger.debug(f"Saved {len(self.sequences)} sequences")
            return True
        except Exception as e:
            logger.error(f"Error saving sequences: {str(e)}")
            return False
    
    def run_sequence(self, sequence):
        """Run a sequence"""
        # Stop any existing executor for this sequence
        if sequence.name in self.executors:
            self.stop_sequence(sequence)
        
        # Create and start executor
        executor = SequenceExecutor(sequence)
        self.executors[sequence.name] = executor
        executor.start()
        
        return True
    
    def pause_sequence(self, sequence):
        """Pause a running sequence"""
        if sequence.name in self.executors:
            executor = self.executors[sequence.name]
            if executor.isRunning() and not executor.paused:
                executor.pause()
                return True
        return False
    
    def resume_sequence(self, sequence):
        """Resume a paused sequence"""
        if sequence.name in self.executors:
            executor = self.executors[sequence.name]
            if executor.isRunning() and executor.paused:
                executor.resume()
                return True
        return False
    
    def stop_sequence(self, sequence):
        """Stop a running sequence"""
        if sequence.name in self.executors:
            executor = self.executors[sequence.name]
            if executor.isRunning():
                executor.stop()
                executor.wait()  # Wait for thread to finish
                del self.executors[sequence.name]
                return True
        return False
    
    def add_sequence(self, sequence):
        """Add a sequence to the manager"""
        # Check for duplicate names
        for existing in self.sequences:
            if existing.name == sequence.name:
                return False
        
        self.sequences.append(sequence)
        return True
    
    def remove_sequence(self, sequence):
        """Remove a sequence from the manager"""
        # Stop if running
        self.stop_sequence(sequence)
        
        # Remove from list
        if sequence in self.sequences:
            self.sequences.remove(sequence)
            return True
        return False
    
    def check_scheduled_sequences(self):
        """Check for sequences that need to run based on schedule"""
        current_time = QDateTime.currentDateTime()
        
        for sequence in self.sequences:
            if (sequence.status == "stopped" and 
                sequence.scheduled_time and 
                sequence.scheduled_time <= current_time):
                
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
                self.run_sequence(sequence)