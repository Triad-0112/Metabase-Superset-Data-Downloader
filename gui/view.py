from PyQt6.QtWidgets import *
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Metabase / Superset CSV Downloader - Auto Interval")
        self.setMinimumSize(800, 650)
        
        # Elements
        self.list_reports = QListWidget()
        self.btn_add = QPushButton("Add Link")
        self.btn_edit = QPushButton("Edit Link")
        self.btn_delete = QPushButton("Delete Link")
        self.btn_extract = QPushButton("Mulai Ekstraksi")
        self.btn_stop_auto = QPushButton("Stop Auto Interval")
        self.btn_set_output = QPushButton("Pilih Folder Output")
        self.btn_edit_config = QPushButton("Edit Config")
        self.btn_concurrency_settings = QPushButton("⚙️ Concurrent Settings")
        self.btn_interval_settings = QPushButton("⏰ Interval Settings")
        self.btn_server_settings = QPushButton("⚙️ Waktu Proses Server")
        self.progress_bar = QProgressBar()
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        
        # Status labels for auto interval
        self.status_label = QLabel("Status: Manual Mode")
        self.status_label.setStyleSheet("font-weight: bold; color: #333;")
        self.next_run_label = QLabel("")
        self.next_run_label.setStyleSheet("color: #666; font-size: 10px;")

        # Initially hide stop button
        self.btn_stop_auto.setVisible(False)
        self.btn_stop_auto.setStyleSheet("background-color: #ff6b6b; color: white;")

        # Layout
        layout = QVBoxLayout()
        
        # Status section
        status_layout = QVBoxLayout()
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.next_run_label)
        layout.addLayout(status_layout)
        
        layout.addWidget(QLabel("Daftar Link"))
        layout.addWidget(self.list_reports)

        hlayout = QHBoxLayout()
        hlayout.addWidget(self.btn_edit_config)
        hlayout.addWidget(self.btn_add)
        hlayout.addWidget(self.btn_edit)
        hlayout.addWidget(self.btn_delete)
        layout.addLayout(hlayout)

        hlayout2 = QHBoxLayout()
        hlayout2.addWidget(self.btn_set_output)
        hlayout2.addWidget(self.btn_concurrency_settings)
        hlayout2.addWidget(self.btn_interval_settings)
        hlayout2.addWidget(self.btn_server_settings)
        layout.addLayout(hlayout2)
        
        # Extract buttons layout
        extract_layout = QHBoxLayout()
        extract_layout.addWidget(self.btn_extract)
        extract_layout.addWidget(self.btn_stop_auto)
        layout.addLayout(extract_layout)
        
        layout.addWidget(self.progress_bar)
        layout.addWidget(QLabel("Log"))
        layout.addWidget(self.log_box)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def update_status(self, status_text, next_run_text=""):
        """Update status labels"""
        if not status_text.strip().startswith("Status:"):
            self.status_label.setText(f"Status: {status_text}")
        else:
            self.status_label.setText(status_text)
            
        self.next_run_label.setText(next_run_text)

    def set_auto_mode(self, enabled):
        """Toggle between auto and manual mode UI"""
        if enabled:
            self.btn_extract.setText("Ekstraksi Manual")
            self.btn_stop_auto.setVisible(True)
            self.status_label.setStyleSheet("font-weight: bold; color: #28a745;")  # Green
        else:
            self.btn_extract.setText("Mulai Ekstraksi")
            self.btn_stop_auto.setVisible(False)
            self.status_label.setStyleSheet("font-weight: bold; color: #333;")  # Default
