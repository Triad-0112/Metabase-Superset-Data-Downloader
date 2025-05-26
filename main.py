from PyQt6.QtWidgets import QApplication
from gui.view import MainWindow
from gui.controller import Controller  # PENTING: Hubungkan controller
import sys

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    
    # Hubungkan UI dengan controller
    controller = Controller(window)
    
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
