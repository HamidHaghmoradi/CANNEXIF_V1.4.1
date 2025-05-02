"""Dialog for selecting a driver class when multiple classes are found."""
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QComboBox, QDialogButtonBox

class ClassSelectionDialog(QDialog):
    """Dialog to select a driver class when multiple classes are found"""
    def __init__(self, classes, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Driver Class")
        layout = QVBoxLayout(self)
        
        # Instructions
        layout.addWidget(QLabel("Multiple classes found. Please select the driver class:"))
        
        # Class dropdown
        self.class_combo = QComboBox()
        self.class_combo.addItems([cls.__name__ for cls in classes])
        layout.addWidget(self.class_combo)
        
        # Buttons
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
    
    def selected_class(self):
        """Get the selected class name"""
        return self.class_combo.currentText()