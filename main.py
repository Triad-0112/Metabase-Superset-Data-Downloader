import sys
import os
import tempfile
from PyQt6.QtWidgets import QApplication, QMessageBox

if sys.platform == 'win32':
    import msvcrt
else:
    import fcntl

from gui.view import MainWindow
from gui.controller import Controller

lock_file_handle = None

def acquire_lock():
    """
    Acquires a lock using a lock file. This is more reliable than a socket,
    especially after being packaged with PyInstaller.
    
    Returns:
        bool: True if the lock was acquired, False otherwise.
    """
    global lock_file_handle
    
    lock_file_path = os.path.join(tempfile.gettempdir(), 'linkdownloader.lock')

    try:
        lock_file_handle = open(lock_file_path, 'w')

        if sys.platform == 'win32':
            fd = lock_file_handle.fileno()
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        else:
            fcntl.flock(lock_file_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            
        return True
    except (IOError, OSError) as e:
        print(f"Another instance is already running. Lock could not be acquired: {e}")
        if lock_file_handle:
            lock_file_handle.close()
        lock_file_handle = None
        return False

def main():
    """
    The main function to start the application.
    """
    if not acquire_lock():
        error_dialog = QMessageBox()
        error_dialog.setIcon(QMessageBox.Icon.Critical)
        error_dialog.setText("Application Already Running")
        error_dialog.setInformativeText(
            "Another instance of the Metabase/Superset CSV Downloader is already running."
        )
        error_dialog.setWindowTitle("Error - Already Running")
        error_dialog.exec()
        sys.exit(1)

    app = QApplication(sys.argv)
    
    try:
        view = MainWindow()
        controller = Controller(view)
        view.show()
        sys.exit(app.exec())
    except Exception as e:
        print(f"An unexpected error occurred during startup: {e}")
        QMessageBox.critical(
            None, 
            "Application Startup Error", 
            f"A critical error occurred and the application must close:\n{e}"
        )
        sys.exit(1)

if __name__ == "__main__":
    main()

