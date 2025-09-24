from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLineEdit, QTextEdit, QLabel, QPushButton, QMessageBox, QHBoxLayout,
    QComboBox, QCheckBox, QSpinBox
)
import json
import configparser

class AddEditReportDialog(QDialog):
    def __init__(self, parent=None, report_name="", request_url="", payload="{}"):
        super().__init__(parent)
        self.setWindowTitle("Tambah / Edit Report")
        self.setMinimumSize(400, 300)

        self.report_name_input = QLineEdit(report_name)
        self.request_url_input = QLineEdit(request_url)
        self.payload_input = QTextEdit(payload)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Report Name:"))
        layout.addWidget(self.report_name_input)

        layout.addWidget(QLabel("Request URL:"))
        layout.addWidget(self.request_url_input)

        layout.addWidget(QLabel("Payload (JSON):"))
        layout.addWidget(self.payload_input)

        self.btn_ok = QPushButton("Simpan")
        self.btn_ok.clicked.connect(self.accept)
        layout.addWidget(self.btn_ok)

        self.setLayout(layout)

    def get_data(self):
        name = self.report_name_input.text().strip()
        url = self.request_url_input.text().strip()
        payload_str = self.payload_input.toPlainText().strip()
        try:
            payload = json.loads(payload_str)
            return name, url, payload
        except json.JSONDecodeError:
            QMessageBox.warning(self, "Error", "Payload harus berupa JSON yang valid!")
            return None, None, None

class EditConfigDialog(QDialog):
    def __init__(self, config_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Config.ini")
        self.setMinimumSize(400, 200)
        self.config_path = config_path
        self.config = configparser.ConfigParser(interpolation=None)

        self.layout = QVBoxLayout()

        self.label_username = QLabel("Username:")
        self.input_username = QLineEdit()
        self.label_password = QLabel("Password:")
        self.input_password = QLineEdit()
        self.input_password.setEchoMode(QLineEdit.EchoMode.Password)

        self.btn_save = QPushButton("Simpan")
        self.btn_save.clicked.connect(self.save_config)

        self.layout.addWidget(self.label_username)
        self.layout.addWidget(self.input_username)
        self.layout.addWidget(self.label_password)
        self.layout.addWidget(self.input_password)
        self.layout.addWidget(self.btn_save)

        self.setLayout(self.layout)

        self.load_config()

    def load_config(self):
        self.config.read(self.config_path)
        if "LOGIN" in self.config:
            self.input_username.setText(self.config["LOGIN"].get("username", ""))
            self.input_password.setText(self.config["LOGIN"].get("password", ""))
        else:
            # Kalau section LOGIN tidak ada, buat kosong saja
            self.input_username.setText("")
            self.input_password.setText("")

    def save_config(self):
        if "LOGIN" not in self.config:
            self.config["LOGIN"] = {}
        self.config["LOGIN"]["username"] = self.input_username.text()
        self.config["LOGIN"]["password"] = self.input_password.text()

        try:
            with open(self.config_path, "w") as f:
                self.config.write(f)
            QMessageBox.information(self, "Sukses", "Config berhasil disimpan!")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Gagal simpan config: {e}")
            
class ConcurrencySettingsDialog(QDialog):
    def __init__(self, config_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pengaturan Concurrent Extraction")
        self.setMinimumSize(300, 150)
        self.config_path = config_path
        self.config = configparser.ConfigParser(interpolation=None)

        self.layout = QVBoxLayout()

        # Jumlah max concurrent worker
        self.label_max_workers = QLabel("Jumlah Maksimal Worker (1-10):")
        self.input_max_workers = QLineEdit()
        self.input_max_workers.setPlaceholderText("Default: 5")
        
        # Validasi input angka 1-10 saja
        self.input_max_workers.textChanged.connect(self.validate_input)

        self.btn_save = QPushButton("Simpan")
        self.btn_save.clicked.connect(self.save_config)

        self.layout.addWidget(self.label_max_workers)
        self.layout.addWidget(self.input_max_workers)
        self.layout.addWidget(self.btn_save)

        self.setLayout(self.layout)

        self.load_config()
        
    def validate_input(self, text):
        # Validasi hanya angka 1-10
        if text:
            try:
                value = int(text)
                if value < 1 or value > 10:
                    self.input_max_workers.setStyleSheet("background-color: #ffcccc;")
                    self.btn_save.setEnabled(False)
                else:
                    self.input_max_workers.setStyleSheet("")
                    self.btn_save.setEnabled(True)
            except ValueError:
                self.input_max_workers.setStyleSheet("background-color: #ffcccc;")
                self.btn_save.setEnabled(False)
        else:
            # Kosong = OK (akan menggunakan default)
            self.input_max_workers.setStyleSheet("")
            self.btn_save.setEnabled(True)

    def load_config(self):
        self.config.read(self.config_path)
        if "SETTINGS" in self.config and "max_workers" in self.config["SETTINGS"]:
            self.input_max_workers.setText(self.config["SETTINGS"]["max_workers"])
        else:
            self.input_max_workers.setText("5")  # Default

    def save_config(self):
        if "SETTINGS" not in self.config:
            self.config["SETTINGS"] = {}
            
        # Jika input kosong, gunakan default
        max_workers = self.input_max_workers.text().strip() or "5"
        
        try:
            # Validasi untuk memastikan nilai antara 1-10
            value = int(max_workers)
            if value < 1:
                max_workers = "1"
            elif value > 10:
                max_workers = "10"
            else:
                max_workers = str(value)
        except ValueError:
            max_workers = "5"  # Default jika bukan angka
        
        self.config["SETTINGS"]["max_workers"] = max_workers

        try:
            with open(self.config_path, "w") as f:
                self.config.write(f)
            QMessageBox.information(self, "Sukses", "Pengaturan concurrency berhasil disimpan!")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Gagal simpan config: {e}")

class IntervalSettingsDialog(QDialog):
    def __init__(self, config_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pengaturan Auto Interval Extraction")
        self.setMinimumSize(400, 300)
        self.config_path = config_path
        self.config = configparser.ConfigParser(interpolation=None)

        self.layout = QVBoxLayout()

        # Enable/Disable auto interval
        self.checkbox_enable = QCheckBox("Aktifkan Auto Interval Extraction")
        self.checkbox_enable.toggled.connect(self.toggle_controls)

        # Interval value
        self.label_interval = QLabel("Interval (dalam menit):")
        self.input_interval = QSpinBox()
        self.input_interval.setMinimum(1)
        self.input_interval.setMaximum(1440)  # Max 24 jam
        self.input_interval.setValue(120)  # Default 2 jam

        # Preset buttons untuk kemudahan
        self.label_presets = QLabel("Preset Interval:")
        preset_layout = QHBoxLayout()
        
        self.btn_30min = QPushButton("30 Menit")
        self.btn_1hour = QPushButton("1 Jam")
        self.btn_2hour = QPushButton("2 Jam")
        self.btn_6hour = QPushButton("6 Jam")
        self.btn_12hour = QPushButton("12 Jam")
        self.btn_24hour = QPushButton("24 Jam")
        
        self.btn_30min.clicked.connect(lambda: self.input_interval.setValue(30))
        self.btn_1hour.clicked.connect(lambda: self.input_interval.setValue(60))
        self.btn_2hour.clicked.connect(lambda: self.input_interval.setValue(120))
        self.btn_6hour.clicked.connect(lambda: self.input_interval.setValue(360))
        self.btn_12hour.clicked.connect(lambda: self.input_interval.setValue(720))
        self.btn_24hour.clicked.connect(lambda: self.input_interval.setValue(1440))
        
        preset_layout.addWidget(self.btn_30min)
        preset_layout.addWidget(self.btn_1hour)
        preset_layout.addWidget(self.btn_2hour)
        preset_layout.addWidget(self.btn_6hour)
        preset_layout.addWidget(self.btn_12hour)
        preset_layout.addWidget(self.btn_24hour)

        # Minimize to tray option
        self.checkbox_minimize = QCheckBox("Minimize ke System Tray saat auto interval aktif")

        # Info label
        self.label_info = QLabel(
            "Info: Ketika auto interval aktif, aplikasi akan menjalankan ekstraksi secara otomatis "
            "setiap interval yang ditentukan. Aplikasi dapat diminimize ke system tray untuk "
            "berjalan di background."
        )
        self.label_info.setWordWrap(True)
        self.label_info.setStyleSheet("color: #666; font-size: 10px; padding: 10px;")

        # Save button
        self.btn_save = QPushButton("Simpan")
        self.btn_save.clicked.connect(self.save_config)

        # Layout setup
        self.layout.addWidget(self.checkbox_enable)
        self.layout.addWidget(self.label_interval)
        self.layout.addWidget(self.input_interval)
        self.layout.addWidget(self.label_presets)
        self.layout.addLayout(preset_layout)
        self.layout.addWidget(self.checkbox_minimize)
        self.layout.addWidget(self.label_info)
        self.layout.addWidget(self.btn_save)

        self.setLayout(self.layout)

        self.load_config()
        self.toggle_controls()

    def toggle_controls(self):
        enabled = self.checkbox_enable.isChecked()
        self.label_interval.setEnabled(enabled)
        self.input_interval.setEnabled(enabled)
        self.label_presets.setEnabled(enabled)
        self.btn_30min.setEnabled(enabled)
        self.btn_1hour.setEnabled(enabled)
        self.btn_2hour.setEnabled(enabled)
        self.btn_6hour.setEnabled(enabled)
        self.btn_12hour.setEnabled(enabled)
        self.btn_24hour.setEnabled(enabled)
        self.checkbox_minimize.setEnabled(enabled)

    def load_config(self):
        self.config.read(self.config_path)
        if "INTERVAL" in self.config:
            enabled = self.config["INTERVAL"].getboolean("enabled", False)
            interval = self.config["INTERVAL"].getint("interval_minutes", 120)
            minimize = self.config["INTERVAL"].getboolean("minimize_to_tray", False)
            
            self.checkbox_enable.setChecked(enabled)
            self.input_interval.setValue(interval)
            self.checkbox_minimize.setChecked(minimize)
        else:
            self.checkbox_enable.setChecked(False)
            self.input_interval.setValue(120)
            self.checkbox_minimize.setChecked(False)

    def save_config(self):
        if "INTERVAL" not in self.config:
            self.config["INTERVAL"] = {}
            
        self.config["INTERVAL"]["enabled"] = str(self.checkbox_enable.isChecked())
        self.config["INTERVAL"]["interval_minutes"] = str(self.input_interval.value())
        self.config["INTERVAL"]["minimize_to_tray"] = str(self.checkbox_minimize.isChecked())

        try:
            with open(self.config_path, "w") as f:
                self.config.write(f)
            QMessageBox.information(self, "Sukses", "Pengaturan interval berhasil disimpan!")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Gagal simpan config: {e}")

class ServerSettingsDialog(QDialog):
    """A new dialog to configure server settings."""
    def __init__(self, config_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pengaturan Waktu Proses Server")
        self.setMinimumSize(350, 200)
        self.config_path = config_path
        self.config = configparser.ConfigParser(interpolation=None)

        self.layout = QVBoxLayout()

        # Server busy duration setting
        self.label_busy_minutes = QLabel("Durasi Proses Server (menit):\n(Waktu di awal setiap jam saat ekstraksi akan ditunda)")
        self.input_busy_minutes = QSpinBox()
        self.input_busy_minutes.setMinimum(0)
        self.input_busy_minutes.setMaximum(59)
        self.input_busy_minutes.setValue(35)  # Default

        # Save button
        self.btn_save = QPushButton("Simpan")
        self.btn_save.clicked.connect(self.save_config)

        # Layout setup
        self.layout.addWidget(self.label_busy_minutes)
        self.layout.addWidget(self.input_busy_minutes)
        self.layout.addWidget(self.btn_save)

        self.setLayout(self.layout)

        self.load_config()

    def load_config(self):
        """Load the busy_minutes value from the [SERVER] section in config.ini."""
        self.config.read(self.config_path)
        if "SERVER" in self.config:
            busy_minutes = self.config["SERVER"].getint("busy_minutes", 35)
            self.input_busy_minutes.setValue(busy_minutes)
        else:
            self.input_busy_minutes.setValue(35)

    def save_config(self):
        """Save the busy_minutes value to the [SERVER] section in config.ini."""
        if "SERVER" not in self.config:
            self.config["SERVER"] = {}
            
        self.config["SERVER"]["busy_minutes"] = str(self.input_busy_minutes.value())

        try:
            with open(self.config_path, "w") as f:
                self.config.write(f)
            QMessageBox.information(self, "Sukses", "Pengaturan server berhasil disimpan!")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Gagal menyimpan config: {e}")

