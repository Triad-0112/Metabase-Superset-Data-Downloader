import configparser
from PyQt6.QtCore import QObject, pyqtSignal, QRunnable
from core.commands import (
    CommandExecutor,
    FetchCSRFTokenCommand,
    LoginCommand,
    FetchReportCommand,
    SaveReportCommand,
)
import concurrent.futures
import threading
import time

class ExtractorSignals(QObject):
    progress = pyqtSignal(int)  # Emit persen
    message = pyqtSignal(str)   # Emit log/status
    finished = pyqtSignal()     # Emit saat selesai
    report_finished = pyqtSignal(str, bool) # Nama report, status berhasil/gagal

class ReportWorker:
    def __init__(self, executor, name, info, output_dir, signals: ExtractorSignals):
        super().__init__()
        self.executor = executor
        self.name = name
        self.info = info
        self.output_dir = output_dir
        self.signals = signals
        
    def process(self):
        current_thread_id = threading.current_thread().name
        self.signals.message.emit(f"[DEBUG] Memulai proses '{self.name}' di thread: {current_thread_id}")
        try:
            # Tidak perlu update config.ini di sini, cukup gunakan output_dir yang sudah diset
            # Proses fetch dan save report
            self.signals.message.emit(f"⏳ Mengambil data untuk report: '{self.name}'...")
            report_data = self.executor.execute_command(
                FetchReportCommand(), self.name, self.info["request_url"], self.info["payload"]
            )
            self.signals.message.emit(f"✅ Data report '{self.name}' berhasil diambil. Menyimpan ke folder output...")

            # Asumsi SaveReportCommand menangani output_dir secara internal atau melalu executor
            msg = self.executor.execute_command(SaveReportCommand(), self.name, report_data) 
            self.signals.message.emit(f"✅ {msg}") # Pesan sukses dari SaveReportCommand
            return (self.name, True, msg) 
        except Exception as e:
            error_message = f"❌ <font color=\"red\">Error saat ekstrak '{self.name}': {e}</font>"
            self.signals.message.emit(error_message)
            return (self.name, False, str(e))

# Global lock untuk mengakses config.ini
thread_config_lock = threading.Lock()

class ExtractorWorker(QRunnable):
    def __init__(self, reports, output_dir, executor: CommandExecutor):
        super().__init__()
        self.signals = ExtractorSignals()
        self.reports = reports
        self.output_dir = output_dir
        self.executor = executor
        
        # Baca max_workers dari config.ini
        config = configparser.ConfigParser(interpolation=None, strict=False)
        try:
            config_path = 'config.ini' # Asumsi config.ini ada di root project
            config.read(config_path)
            self.max_workers = config.getint('SETTINGS', 'max_workers', fallback=5) # Perbaikan di sini
        except Exception as e:
            self.signals.message.emit(f"<font color=\"red\">[ERROR] Gagal membaca max_workers dari config.ini: {str(e)}. Menggunakan default 5.</font>")
            self.max_workers = 5 # Default jika konfigurasi gagal

    def run(self):
        try:
            self.signals.message.emit("Fetching CSRF token...")
            self.executor.execute_command(FetchCSRFTokenCommand())
            self.signals.message.emit("CSRF token berhasil diambil.")
            self.signals.message.emit("⚡️ Memulai login...")
            username, password = self.read_login_credentials()
            if not username or not password:
                 self.signals.message.emit("<font color=\"red\">[ERROR] Username atau password tidak ditemukan di config.ini. Silakan cek bagian [LOGIN].</font>")
                 self.signals.finished.emit()
                 return

            self.executor.execute_command(LoginCommand(), username, password)
            self.signals.message.emit("Login berhasil!")

            report_workers = []
            for name, info in self.reports.items():
                # Teruskan objek sinyal ExtractorWorker ke setiap ReportWorker
                report_workers.append(ReportWorker(self.executor, name, info, self.output_dir, self.signals))

            total = len(report_workers)
            completed = 0
            
            self.signals.message.emit(f"🚀 Mulai mengekstrak {total} report dengan {min(self.max_workers, total)} threads paralel...")
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit semua tugas sekaligus
                future_to_worker = {executor.submit(worker.process): worker for worker in report_workers}
                
                # Proses hasil selesai
                for future in concurrent.futures.as_completed(future_to_worker):
                    name, success, message = future.result()
                    completed += 1
                    
                    # ReportWorker sekarang memancarkan pesannya sendiri.
                    # ExtractorWorker cukup mengupdate progress dan status report selesai.
                    self.signals.report_finished.emit(name, success) # Memancarkan status selesai report individual

                    # Update progress bar
                    progress = int((completed / total) * 100)
                    self.signals.progress.emit(progress)
            
            self.signals.message.emit(f"🎉 Semua {total} report selesai diekstrak.")
            
        except Exception as e:
            self.signals.message.emit(f"💥 <font color=\"red\">ERROR: {e}</font>") # Pesan kesalahan global dalam warna merah
        finally:
            self.signals.finished.emit()
            
    def read_login_credentials(self):
        config = configparser.ConfigParser(interpolation=None, strict=False)
        
        try:
            config_path = 'config.ini' # Diasumsikan config.ini ada di root project
            config.read(config_path)
            
            if "LOGIN" in config:
                username = config.get("LOGIN", "username", fallback="")
                password = config.get("LOGIN", "password", fallback="")
                return username, password
            else:
                return "", ""
                
        except Exception as e:
            self.signals.message.emit(f"[ERROR] Gagal membaca kredensial login dari config.ini: {str(e)}")
            return "", ""
