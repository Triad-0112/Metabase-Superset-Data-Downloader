from PyQt6.QtWidgets import (
    QMessageBox, QFileDialog, QSystemTrayIcon, QMenu
)
from PyQt6.QtCore import QThreadPool, QTimer, QDateTime
from PyQt6.QtGui import QIcon, QAction
import json
import configparser
import os
import random
from gui.model import ReportModel, CONFIG_FILE
from gui.dialogs import AddEditReportDialog, EditConfigDialog, IntervalSettingsDialog
from gui.extractor import ExtractorWorker
from core.commands import CommandExecutor, LoginCommand, FetchCSRFTokenCommand

class Controller:
    def __init__(self, view):
        self.view = view
        self.model = ReportModel()
        self.threadpool = QThreadPool()
        self.executor = CommandExecutor() 
        
        # Auto interval components
        self.interval_timer = QTimer()
        self.interval_timer.timeout.connect(self.auto_extract)
        self.is_auto_mode = False
        self.next_auto_run = None
        
        # System tray setup
        self.setup_system_tray()
        
        self._connect_signals()
        self.refresh_report_list()
        self.load_interval_settings()

    def setup_system_tray(self):
        """Setup system tray icon and menu"""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.view.log_box.append("⚠️ System tray tidak tersedia di sistem ini.")
            return
            
        self.tray_icon = QSystemTrayIcon(self.view)
        
        # Create tray menu
        tray_menu = QMenu()
        
        show_action = QAction("Tampilkan", self.view)
        show_action.triggered.connect(self.show_window)
        tray_menu.addAction(show_action)
        
        hide_action = QAction("Sembunyikan", self.view)
        hide_action.triggered.connect(self.hide_window)
        tray_menu.addAction(hide_action)
        
        tray_menu.addSeparator()
        
        extract_action = QAction("Ekstraksi Manual", self.view)
        extract_action.triggered.connect(self.start_extraction)
        tray_menu.addAction(extract_action)
        
        tray_menu.addSeparator()
        
        quit_action = QAction("Keluar", self.view)
        quit_action.triggered.connect(self.quit_application)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        
        # Set icon (you might want to use a proper icon file)
        # For now, using default icon
        try:
            self.tray_icon.setIcon(self.view.style().standardIcon(self.view.style().StandardPixmap.SP_ComputerIcon))
        except:
            pass
            
        self.tray_icon.show()
        
        # Tray icon click handler
        self.tray_icon.activated.connect(self.tray_icon_activated)

    def tray_icon_activated(self, reason):
        """Handle tray icon clicks"""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_window()

    def show_window(self):
        """Show main window"""
        self.view.show()
        self.view.raise_()
        self.view.activateWindow()

    def hide_window(self):
        """Hide main window to tray"""
        self.view.hide()
        if hasattr(self, 'tray_icon'):
            self.tray_icon.showMessage(
                "CSV Downloader",
                "Aplikasi berjalan di background. Klik kanan pada icon tray untuk mengakses menu.",
                QSystemTrayIcon.MessageIcon.Information,
                3000
            )

    def quit_application(self):
        """Completely quit the application"""
        if self.is_auto_mode:
            reply = QMessageBox.question(
                self.view,
                "Konfirmasi",
                "Auto interval sedang aktif. Yakin ingin keluar?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return
                
        self.stop_auto_interval()
        if hasattr(self, 'tray_icon'):
            self.tray_icon.hide()
        self.view.close()

    def _connect_signals(self):
        self.view.btn_add.clicked.connect(self.add_report)
        self.view.btn_edit.clicked.connect(self.edit_report)
        self.view.btn_delete.clicked.connect(self.delete_report)
        self.view.btn_set_output.clicked.connect(self.set_output_folder)
        self.view.btn_extract.clicked.connect(self.handle_extract_button)
        self.view.btn_stop_auto.clicked.connect(self.stop_auto_interval)
        self.view.btn_edit_config.clicked.connect(self.edit_config)
        self.view.btn_concurrency_settings.clicked.connect(self.edit_concurrency_settings)
        self.view.btn_interval_settings.clicked.connect(self.edit_interval_settings)
        
        # Handle window close event for tray
        self.view.closeEvent = self.close_event

    def close_event(self, event):
        """Handle window close event"""
        if hasattr(self, 'tray_icon') and self.tray_icon.isVisible():
            event.ignore()
            self.hide_window()
        else:
            self.quit_application()

    def load_interval_settings(self):
        """Load interval settings from config"""
        config = configparser.ConfigParser(interpolation=None)
        config.read(CONFIG_FILE)
        
        if "INTERVAL" in config:
            enabled = config["INTERVAL"].getboolean("enabled", False)
            if enabled:
                interval_minutes = config["INTERVAL"].getint("interval_minutes", 120)
                minimize_to_tray = config["INTERVAL"].getboolean("minimize_to_tray", False)
                
                self.start_auto_interval(interval_minutes, minimize_to_tray)

    def edit_interval_settings(self):
        """Open interval settings dialog"""
        dialog = IntervalSettingsDialog(CONFIG_FILE, parent=self.view)
        if dialog.exec():
            self.view.log_box.append("⚙️ Pengaturan interval berhasil diperbarui.")
            self.load_interval_settings()  # Reload settings

    def start_auto_interval(self, interval_minutes, minimize_to_tray=False):
        """Start auto interval extraction with an initial jitter."""
        if self.is_auto_mode:
            self.view.log_box.append("⚠️ Auto interval sudah aktif.")
            return
            
        self.is_auto_mode = True
        
        # ==================== HIGHLIGHT START ====================
        # This block adds a random delay of 1-5 minutes before the *first* extraction runs.
        initial_jitter_minutes = random.randint(1, 5)
        self.view.log_box.append(f" Jitter awal ditambahkan: {initial_jitter_minutes} menit.")
        
        # The timer is set to trigger the first auto_extract() after this initial delay.
        self.interval_timer.start(initial_jitter_minutes * 60 * 1000)
        # ===================== HIGHLIGHT END =====================

        # Update UI
        self.view.set_auto_mode(True)
        self.view.update_status("Auto Interval Aktif", f"Interval dasar: {interval_minutes} menit")
        
        # Calculate the run time for the FIRST extraction
        self.calculate_next_run(initial_jitter_minutes)
        
        self.view.log_box.append(f"🔄 Auto interval aktif! Ekstraksi pertama akan dijalankan dalam ~{initial_jitter_minutes} menit.")
        
        # Minimize to tray if requested
        if minimize_to_tray and hasattr(self, 'tray_icon'):
            self.hide_window()
            
        # The first extraction is no longer started immediately. It will start after the initial jitter.

    def stop_auto_interval(self):
        """Stop auto interval extraction"""
        if not self.is_auto_mode:
            return
            
        self.is_auto_mode = False
        self.interval_timer.stop()
        self.next_auto_run = None
        
        # Update UI
        self.view.set_auto_mode(False)
        self.view.update_status("Manual Mode")
        
        self.view.log_box.append("⏹️ Auto interval dihentikan.")

    def calculate_next_run(self, interval_minutes):
        """Calculate and display next auto run time"""
        if self.is_auto_mode:
            self.next_auto_run = QDateTime.currentDateTime().addSecs(interval_minutes * 60)
            next_run_text = f"Ekstraksi berikutnya: {self.next_auto_run.toString('dd/MM/yyyy hh:mm:ss')}"
            self.view.update_status("Auto Interval Aktif", next_run_text)
            
            # Update timer untuk countdown
            self.countdown_timer = QTimer()
            self.countdown_timer.timeout.connect(self.update_countdown)
            self.countdown_timer.start(1000)  # Update every second

    def update_countdown(self):
        """Update countdown display"""
        if not self.is_auto_mode or not self.next_auto_run:
            if hasattr(self, 'countdown_timer'):
                self.countdown_timer.stop()
            return
            
        current_time = QDateTime.currentDateTime()
        if current_time >= self.next_auto_run:
            if hasattr(self, 'countdown_timer'):
                self.countdown_timer.stop()
            return
            
        seconds_left = current_time.secsTo(self.next_auto_run)
        hours = seconds_left // 3600
        minutes = (seconds_left % 3600) // 60
        seconds = seconds_left % 60
        
        countdown_text = f"Ekstraksi berikutnya dalam: {hours:02d}:{minutes:02d}:{seconds:02d}"
        self.view.update_status("Auto Interval Aktif", countdown_text)

    def auto_extract(self):
        """Perform automatic extraction and schedule the next one."""
        self.view.log_box.append(f"🤖 [AUTO] Memulai ekstraksi otomatis - {QDateTime.currentDateTime().toString('dd/MM/yyyy hh:mm:ss')}")
        
        # ==================== HIGHLIGHT START ====================
        # This block calculates the interval for the *next* extraction,
        # adding a new random jitter each time.
        config = configparser.ConfigParser(interpolation=None)
        config.read(CONFIG_FILE)
        base_interval_minutes = config["INTERVAL"].getint("interval_minutes", 120)
        
        random_delay_minutes = random.randint(1, 20)
        next_interval_minutes = base_interval_minutes + random_delay_minutes
        
        self.view.log_box.append(f" Jitter berikutnya: {random_delay_minutes} menit. Interval selanjutnya diatur ke ~{next_interval_minutes} menit.")

        # Stop the old timer and start a new one with the new randomized interval.
        self.interval_timer.stop()
        self.interval_timer.start(next_interval_minutes * 60 * 1000)
        
        # Calculate and display the next run time in the UI.
        self.calculate_next_run(next_interval_minutes)
        # ===================== HIGHLIGHT END =====================
        
        # Start the actual extraction process
        self.start_extraction()

    def handle_extract_button(self):
        """Handle extract button click - can be manual or start auto"""
        config = configparser.ConfigParser(interpolation=None)
        config.read(CONFIG_FILE)
        
        # Check if interval is enabled
        if "INTERVAL" in config and config["INTERVAL"].getboolean("enabled", False):
            if not self.is_auto_mode:
                # Start auto interval
                interval_minutes = config["INTERVAL"].getint("interval_minutes", 120)
                minimize_to_tray = config["INTERVAL"].getboolean("minimize_to_tray", False)
                self.start_auto_interval(interval_minutes, minimize_to_tray)
            else:
                # Manual extraction while auto is running
                self.start_extraction()
        else:
            # Regular manual extraction
            self.start_extraction()

    def edit_concurrency_settings(self):
        # Import di sini untuk menghindari circular import
        from gui.dialogs import ConcurrencySettingsDialog
        dialog = ConcurrencySettingsDialog(CONFIG_FILE, parent=self.view)
        if dialog.exec():
            self.view.log_box.append("⚙️ Pengaturan concurrency berhasil diperbarui.")
            self.model._load_config()  # reload config biar update di model

    def edit_config(self):
        dialog = EditConfigDialog(CONFIG_FILE, parent=self.view)
        if dialog.exec():
            self.view.log_box.append("⚙️ Config.ini berhasil diperbarui.")
            self.model._load_config()  # reload config biar update di model

    def refresh_report_list(self):
        self.view.list_reports.clear()
        for name in self.model.get_report_list():
            self.view.list_reports.addItem(name)

    def get_selected_report_name(self):
        selected_items = self.view.list_reports.selectedItems()
        return selected_items[0].text() if selected_items else None

    def add_report(self):
        print("[DEBUG] Tombol Add Report diklik.")
        self.view.log_box.append("[DEBUG] Tombol Add Report diklik.")

        try:
            dialog = AddEditReportDialog(self.view)
            result = dialog.exec()
            print(f"[DEBUG] Dialog result: {result}")
            self.view.log_box.append(f"[DEBUG] Dialog result: {result}")

            if result:
                name, url, payload = dialog.get_data()
                print(f"[DEBUG] Data diambil: {name=}, {url=}, {type(payload)=}")
                self.view.log_box.append(f"[DEBUG] Data diambil: {name}, {url}")

                if name and url and payload is not None:
                    self.model.add_report(name, url, payload)
                    self.refresh_report_list()
                    self.view.log_box.append(f"[+] Report '{name}' ditambahkan.")
                else:
                    self.view.log_box.append("[DEBUG] Data tidak valid atau dibatalkan.")
            else:
                self.view.log_box.append("[DEBUG] Dialog dibatalkan oleh user.")
        except Exception as e:
            error_msg = f"[ERROR] Gagal tambah report: {e}"
            print(error_msg)
            QMessageBox.critical(self.view, "Exception", error_msg)
            self.view.log_box.append(error_msg)

    def edit_report(self):
        selected = self.get_selected_report_name()
        if not selected:
            QMessageBox.information(self.view, "Pilih Report", "Silakan pilih report yang ingin diedit.")
            return

        old_data = self.model.get_report(selected)
        dialog = AddEditReportDialog(
            self.view,
            report_name=selected,
            request_url=old_data["request_url"],
            payload=json.dumps(old_data["payload"], indent=2)
        )

        if dialog.exec():
            new_name, new_url, new_payload = dialog.get_data()
            if new_name and new_url and new_payload is not None:
                self.model.edit_report(selected, new_name, new_url, new_payload)
                self.refresh_report_list()
                self.view.log_box.append(f"[~] Report '{selected}' diedit.")

    def delete_report(self):
        selected = self.get_selected_report_name()
        if not selected:
            QMessageBox.information(self.view, "Pilih Report", "Silakan pilih report yang ingin dihapus.")
            return

        confirm = QMessageBox.question(self.view, "Hapus Report", f"Yakin ingin menghapus '{selected}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if confirm == QMessageBox.StandardButton.Yes:
            self.model.delete_report(selected)
            self.refresh_report_list()
            self.view.log_box.append(f"[-] Report '{selected}' dihapus.")

    def set_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self.view, "Pilih Folder Output", self.model.output_dir)
        if folder:
            self.model.save_output_dir(folder)
            self.view.log_box.append(f"[📁] Folder output diatur ke: {folder}")

    def start_extraction(self):
        # DEBUG: Cek lokasi config.ini
        config_path = os.path.abspath("config.ini")
        self.view.log_box.append(f"[DEBUG] Mencari config.ini di: {config_path}")
        
        if not os.path.exists(config_path):
            self.view.log_box.append(f"[ERROR] File config.ini tidak ditemukan!")
            return
            
        username, password = self.get_login_credentials()
        self.view.log_box.append(f"[DEBUG] Username: {'Ditemukan' if username else 'Kosong'}, Password: {'Ditemukan' if password else 'Kosong'}")
        
        if not username or not password:
            self.view.log_box.append("⚠️ Username atau password belum disetel di config.ini")
            return
            
        reports = self.model.get_all_reports()
        if not reports:
            self.view.log_box.append("⚠️ Tidak ada report untuk diekstrak.")
            return

        # Don't clear log if auto mode is active
        if not self.is_auto_mode:
            self.view.log_box.clear()
        self.view.progress_bar.setValue(0)
        self.view.btn_extract.setEnabled(False)

        # Membaca jumlah concurrent worker dari config.ini
        config = configparser.ConfigParser(interpolation=None)
        config.read("config.ini")
        max_workers = 5  # Default 5 worker
        if "SETTINGS" in config and "max_workers" in config["SETTINGS"]:
            try:
                max_workers = int(config["SETTINGS"]["max_workers"])
            except ValueError:
                # Fallback ke default jika nilai bukan angka
                max_workers = 5

        worker = ExtractorWorker(reports, self.model.get_output_dir(), self.executor)
        worker.signals.progress.connect(self.view.progress_bar.setValue)
        worker.signals.message.connect(self.view.log_box.append)
        worker.signals.finished.connect(self._on_extraction_finished)

        self.threadpool.start(worker)

    def extraction_finished(self):
        self.view.log_box.append("Ekstraksi selesai.")
        self.view.btn_extract.setEnabled(True)

    def _on_extraction_finished(self):
        self.view.btn_extract.setEnabled(True)
        if self.is_auto_mode:
            self.view.log_box.append("✅ Proses ekstraksi otomatis selesai.")
        else:
            self.view.log_box.append("✅ Proses ekstraksi selesai.")

    def perform_login(self):
        # Ambil username & password dari config
        username, password = self.get_login_credentials()
        if not username or not password:
            self.view.log_box.append("⚠️ Username atau password belum disetel di config.ini")
            return False

        # Ambil CSRF token dulu
        try:
            csrf_cmd = FetchCSRFTokenCommand()
            csrf_token = self.executor.execute_command(csrf_cmd)
            self.executor.csrf_token = csrf_token
            self.view.log_box.append("✅ CSRF token berhasil didapatkan")

            # Login pakai username & password
            # PERUBAHAN: Tidak perlu memeriksa return value dengan `success` karena
            # LoginCommand langsung mengembalikan boolean hasil dari status_code == 200
            login_cmd = LoginCommand()
            if self.executor.execute_command(login_cmd, username, password):
                self.view.log_box.append("🔐 Login berhasil")
                return True
            else:
                self.view.log_box.append("❌ Login gagal, cek username/password")
                return False

        except Exception as e:
            self.view.log_box.append(f"❌ Error saat login: {e}")
            return False
    
    def get_login_credentials(self):
        # DEBUG: Print configurasi yang ada
        self.view.log_box.append("[DEBUG] Memuat kredensial login...")
        
        # Menggunakan strict=False untuk menghindari interpolation issues
        config = configparser.ConfigParser(interpolation=None, strict=False)
        
        try:
            # Secara eksplisit menyebutkan config file dengan absolute path
            config_path = os.path.abspath("config.ini")
            with open(config_path, 'r') as f:
                config.read_file(f)
                
            # Debug sections yang tersedia
            sections = config.sections()
            self.view.log_box.append(f"[DEBUG] Config sections: {sections}")
            
            # Coba baca dari section LOGIN (case sensitive)
            if "LOGIN" in sections:
                username = config.get("LOGIN", "username", fallback="")
                password = config.get("LOGIN", "password", fallback="")
                return username, password
            else:
                # Jika tidak ditemukan, coba baca dengan case insensitive
                for section in sections:
                    if section.upper() == "LOGIN":
                        username = config.get(section, "username", fallback="")
                        password = config.get(section, "password", fallback="")
                        return username, password
                
                self.view.log_box.append("[ERROR] Section LOGIN tidak ditemukan di config.ini")
                return "", ""
                
        except Exception as e:
            self.view.log_box.append(f"[ERROR] Gagal membaca config.ini: {str(e)}")
            return "", ""


