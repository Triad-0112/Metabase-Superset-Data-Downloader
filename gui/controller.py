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
from gui.dialogs import AddEditReportDialog, EditConfigDialog, IntervalSettingsDialog, ServerSettingsDialog
from gui.extractor import ExtractorWorker
from core.commands import CommandExecutor, LoginCommand, FetchCSRFTokenCommand

class Controller:
    def __init__(self, view):
        self.view = view
        self.model = ReportModel()
        self.threadpool = QThreadPool()
        self.executor = CommandExecutor() 
        
        # Komponen auto interval
        self.interval_timer = QTimer()
        self.interval_timer.timeout.connect(self.auto_extract_and_reschedule)
        self.is_auto_mode = False
        self.next_run_time = None # Variabel baru untuk menyimpan waktu eksekusi berikutnya
        
        # Timer baru untuk status server, memeriksa setiap detik
        self.server_status_timer = QTimer()
        self.server_status_timer.timeout.connect(self.update_status_display)
        self.server_status_timer.start(1000)
        
        # Pengaturan system tray
        self.setup_system_tray()
        
        self._connect_signals()
        self.refresh_report_list()
        self.load_interval_settings()
        self.update_status_display() # Panggilan awal

    def _get_server_busy_minutes(self):
        """Membaca durasi sibuk server dari config.ini, dengan nilai fallback."""
        config = configparser.ConfigParser(interpolation=None)
        config.read(CONFIG_FILE)
        return config.getint("SERVER", "busy_minutes", fallback=35)

    def update_status_display(self):
        """
        Satu fungsi terpusat untuk memperbarui baris status kedua setiap detik.
        Memprioritaskan status sibuk server, kemudian hitungan mundur, lalu status default.
        """
        current_dt = QDateTime.currentDateTime()
        hour = current_dt.time().hour()
        minute = current_dt.time().minute()
        server_busy_minutes = self._get_server_busy_minutes()
        
        status_text_line_2 = ""
        is_busy_schedule = (hour % 2 == 0)

        # Prioritas 1: Tampilkan jika server sedang sibuk.
        if is_busy_schedule and (0 <= minute < server_busy_minutes):
            seconds_left = (server_busy_minutes - 1 - minute) * 60 + (59 - current_dt.time().second())
            minutes_left = seconds_left // 60
            seconds_rem = seconds_left % 60
            status_text_line_2 = f"Server Sibuk. Buka dalam: {minutes_left:02d}:{seconds_rem:02d}"
        # Prioritas 2: Tampilkan hitungan mundur jika mode auto aktif.
        elif self.is_auto_mode and self.next_run_time:
            seconds_to_next = current_dt.secsTo(self.next_run_time)
            if seconds_to_next > 0:
                hours = seconds_to_next // 3600
                minutes = (seconds_to_next % 3600) // 60
                seconds = seconds_to_next % 60
                status_text_line_2 = f"Ekstraksi berikutnya dalam: {hours:02d}:{minutes:02d}:{seconds:02d}"
            else:
                status_text_line_2 = "Memulai ekstraksi..."
        # Prioritas 3: Tampilkan status default.
        else:
            status_text_line_2 = "Status Server: Siap untuk ekstraksi."
            
        # Perbarui UI
        main_status = self.view.status_label.text().split('\n')[0]
        if not self.is_auto_mode:
             main_status = "Status: Manual Mode"

        self.view.update_status(main_status, status_text_line_2)

    def setup_system_tray(self):
        """Setup system tray icon and menu"""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.view.log_box.append("⚠️ System tray tidak tersedia di sistem ini.")
            return
            
        self.tray_icon = QSystemTrayIcon(self.view)
        
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
        
        try:
            self.tray_icon.setIcon(self.view.style().standardIcon(self.view.style().StandardPixmap.SP_ComputerIcon))
        except:
            pass
            
        self.tray_icon.show()
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
                self.view, "Konfirmasi", "Auto interval sedang aktif. Yakin ingin keluar?",
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
        self.view.btn_server_settings.clicked.connect(self.edit_server_settings)
        self.view.closeEvent = self.close_event

    def edit_server_settings(self):
        """Membuka dialog baru untuk mengedit pengaturan server."""
        dialog = ServerSettingsDialog(CONFIG_FILE, parent=self.view)
        if dialog.exec():
            self.view.log_box.append("⚙️ Pengaturan waktu proses server berhasil diperbarui.")
            self.update_status_display()

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
        
        if "INTERVAL" in config and config["INTERVAL"].getboolean("enabled", False):
            interval_minutes = config["INTERVAL"].getint("interval_minutes", 120)
            minimize_to_tray = config["INTERVAL"].getboolean("minimize_to_tray", False)
            self.start_auto_interval(interval_minutes, minimize_to_tray)

    def edit_interval_settings(self):
        """Open interval settings dialog"""
        dialog = IntervalSettingsDialog(CONFIG_FILE, parent=self.view)
        if dialog.exec():
            self.view.log_box.append("⚙️ Pengaturan interval berhasil diperbarui.")
            self.load_interval_settings()

    def start_auto_interval(self, interval_minutes, minimize_to_tray=False):
        """Memulai ekstraksi auto interval dengan jeda acak awal satu kali."""
        if self.is_auto_mode:
            self.view.log_box.append("⚠️ Auto interval sudah aktif.")
            return
            
        self.is_auto_mode = True
        self.view.set_auto_mode(True)
        self.view.update_status("Status: Auto Interval Aktif")
        
        initial_jitter_minutes = random.randint(1, 10)
        self.view.log_box.append(f"🔄 Auto interval aktif! Ekstraksi pertama akan dimulai setelah jeda awal ~{initial_jitter_minutes} menit.")
        
        # Atur waktu eksekusi pertama
        self.next_run_time = QDateTime.currentDateTime().addSecs(initial_jitter_minutes * 60)
        
        # Gunakan QTimer untuk memanggil ekstraksi pertama
        QTimer.singleShot(initial_jitter_minutes * 60 * 1000, self.auto_extract_and_reschedule)

        if minimize_to_tray and hasattr(self, 'tray_icon'):
            self.hide_window()

    def stop_auto_interval(self):
        """Stop auto interval extraction"""
        if not self.is_auto_mode:
            return
            
        self.is_auto_mode = False
        self.interval_timer.stop()
        self.next_run_time = None
        
        self.view.set_auto_mode(False)
        self.update_status_display()
        self.view.log_box.append("⏹️ Auto interval dihentikan.")

    def auto_extract_and_reschedule(self):
        """Menjalankan ekstraksi dan kemudian menjadwalkan ulang timer utama."""
        if not self.is_auto_mode:
            return

        # 1. Jalankan ekstraksi saat ini
        self.check_server_and_extract()
        
        # 2. Jadwalkan ulang timer utama untuk siklus berikutnya
        config = configparser.ConfigParser(interpolation=None)
        config.read(CONFIG_FILE)
        interval_minutes = config["INTERVAL"].getint("interval_minutes", 120)
        
        self.interval_timer.start(interval_minutes * 60 * 1000)
        
        # 3. Hitung dan simpan waktu eksekusi berikutnya untuk ditampilkan
        self.next_run_time = QDateTime.currentDateTime().addSecs(interval_minutes * 60)
        self.view.log_box.append(f"Ekstraksi berikutnya dijadwalkan dalam {interval_minutes} menit.")

    def check_server_and_extract(self):
        """Memicu ekstraksi, tetapi memeriksa dulu apakah server sibuk."""
        current_dt = QDateTime.currentDateTime()
        hour = current_dt.time().hour()
        minute = current_dt.time().minute()
        server_busy_minutes = self._get_server_busy_minutes()

        is_busy_schedule = (hour % 2 == 0)

        if is_busy_schedule and (0 <= minute < server_busy_minutes):
            seconds_to_wait = (server_busy_minutes - minute) * 60 - current_dt.time().second()
            self.view.log_box.append(f"⏰ Server sedang memproses data. Ekstraksi ditunda selama ~{seconds_to_wait // 60 + 1} menit.")
            QTimer.singleShot(seconds_to_wait * 1000, self.start_extraction)
        else:
            self.view.log_box.append(f"🤖 [AUTO] Memulai ekstraksi otomatis - {current_dt.toString('dd/MM/yyyy hh:mm:ss')}")
            self.start_extraction()

    def handle_extract_button(self):
        """Handle extract button click"""
        config = configparser.ConfigParser(interpolation=None)
        config.read(CONFIG_FILE)
        
        if "INTERVAL" in config and config["INTERVAL"].getboolean("enabled", False):
            if not self.is_auto_mode:
                interval_minutes = config["INTERVAL"].getint("interval_minutes", 120)
                minimize_to_tray = config["INTERVAL"].getboolean("minimize_to_tray", False)
                self.start_auto_interval(interval_minutes, minimize_to_tray)
            else:
                self.start_extraction()
        else:
            self.start_extraction()

    def edit_concurrency_settings(self):
        from gui.dialogs import ConcurrencySettingsDialog
        dialog = ConcurrencySettingsDialog(CONFIG_FILE, parent=self.view)
        if dialog.exec():
            self.view.log_box.append("⚙️ Pengaturan concurrency berhasil diperbarui.")
            self.model._load_config()

    def edit_config(self):
        dialog = EditConfigDialog(CONFIG_FILE, parent=self.view)
        if dialog.exec():
            self.view.log_box.append("⚙️ Config.ini berhasil diperbarui.")
            self.model._load_config()

    def refresh_report_list(self):
        self.view.list_reports.clear()
        for name in self.model.get_report_list():
            self.view.list_reports.addItem(name)

    def get_selected_report_name(self):
        selected_items = self.view.list_reports.selectedItems()
        return selected_items[0].text() if selected_items else None

    def add_report(self):
        dialog = AddEditReportDialog(self.view)
        if dialog.exec():
            name, url, payload = dialog.get_data()
            if name and url and payload is not None:
                self.model.add_report(name, url, payload)
                self.refresh_report_list()
                self.view.log_box.append(f"[+] Report '{name}' ditambahkan.")

    def edit_report(self):
        selected = self.get_selected_report_name()
        if not selected:
            QMessageBox.information(self.view, "Pilih Report", "Silakan pilih report yang ingin diedit.")
            return

        old_data = self.model.get_report(selected)
        dialog = AddEditReportDialog(
            self.view, report_name=selected, request_url=old_data["request_url"],
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

        confirm = QMessageBox.question(self.view, "Hapus Report", f"Yakin ingin menghapus '{selected}'?", 
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
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
        if not os.path.exists("config.ini"):
            self.view.log_box.append("[ERROR] File config.ini tidak ditemukan!")
            return
            
        username, password = self.get_login_credentials()
        if not username or not password:
            self.view.log_box.append("⚠️ Username atau password belum disetel di config.ini")
            return
            
        reports = self.model.get_all_reports()
        if not reports:
            self.view.log_box.append("⚠️ Tidak ada report untuk diekstrak.")
            return

        if not self.is_auto_mode:
            self.view.log_box.clear()
        self.view.progress_bar.setValue(0)
        self.view.btn_extract.setEnabled(False)

        worker = ExtractorWorker(reports, self.model.get_output_dir(), self.executor)
        worker.signals.progress.connect(self.view.progress_bar.setValue)
        worker.signals.message.connect(self.view.log_box.append)
        worker.signals.finished.connect(self._on_extraction_finished)

        self.threadpool.start(worker)

    def _on_extraction_finished(self):
        self.view.btn_extract.setEnabled(True)
        self.view.log_box.append("✅ Proses ekstraksi selesai.")

    def get_login_credentials(self):
        config = configparser.ConfigParser(interpolation=None, strict=False)
        try:
            config_path = os.path.abspath("config.ini")
            with open(config_path, 'r') as f:
                config.read_file(f)
            
            sections = config.sections()
            if "LOGIN" in sections:
                return config.get("LOGIN", "username", fallback=""), config.get("LOGIN", "password", fallback="")
            else:
                for section in sections:
                    if section.upper() == "LOGIN":
                        return config.get(section, "username", fallback=""), config.get(section, "password", fallback="")
                return "", ""
        except Exception as e:
            self.view.log_box.append(f"[ERROR] Gagal membaca config.ini: {str(e)}")
            return "", ""

