# core/commands.py
import requests
import pandas as pd
import configparser
import os
import json

# --- Command Base Class ---
class Command:
    def execute(self, executor, *args, **kwargs):
        raise NotImplementedError("Command harus implementasikan metode execute()")

# --- Command Executor ---
class CommandExecutor:
    def __init__(self):
        self.session = requests.Session()
        self.csrf_token = None
        
        # Load config untuk BASE_URL jika diperlukan
        config = configparser.ConfigParser(interpolation=None)
        config.read('config.ini')
        if 'SETTINGS' in config and 'base_url' in config['SETTINGS']:
            self.base_url = config['SETTINGS']['base_url']
        else:
            self.base_url = "https://dashboard.ecocare.co.id"

    def execute_command(self, command: Command, *args, **kwargs):
        return command.execute(self, *args, **kwargs)

# --- Concrete Commands ---
class FetchCSRFTokenCommand(Command):
    def execute(self, executor: CommandExecutor):
        # Perubahan: Menggunakan base_url dari executor dan get 'result' bukan 'csrf_token'
        url = f"{executor.base_url}/api/v1/security/csrf_token/"
        response = executor.session.get(url)
        response.raise_for_status()
        data = response.json()

        # Simpan token ke executor agar reusable
        executor.csrf_token = data.get("result")  # PERUBAHAN: mendapatkan 'result' bukan 'csrf_token'

        # Set header default ke session (jika API butuh secara global)
        executor.session.headers.update({
            "X-CSRFToken": executor.csrf_token
        })

        return executor.csrf_token

class LoginCommand(Command):
    def execute(self, executor: CommandExecutor, username=None, password=None):
        if username is None or password is None:
            raise ValueError("Username atau password harus diberikan saat execute!")

        # Validasi token ada
        if not executor.csrf_token:
            raise RuntimeError("CSRF Token belum diambil. Jalankan FetchCSRFTokenCommand terlebih dahulu.")

        # PERUBAHAN: Gunakan application/x-www-form-urlencoded dan /login/ endpoint
        payload = {
            "csrf_token": executor.csrf_token,
            "username": username,
            "password": password
        }
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded", 
            "X-CSRFToken": executor.csrf_token
        }

        login_url = f"{executor.base_url}/login/"
        response = executor.session.post(login_url, data=payload, headers=headers)
        response.raise_for_status()
        
        # PERUBAHAN: Return status code check
        return response.status_code == 200

class FetchReportCommand(Command):
    def execute(self, executor: CommandExecutor, name, url, payload):
        # PERUBAHAN: Gunakan base_url jika URL tidak lengkap
        if not url.startswith(("http://", "https://")):
            complete_url = f"{executor.base_url}{url}"
        else:
            complete_url = url
        
        # Deteksi jika URL langsung ke file CSV (tanpa perlu CSRF dan payload)
        is_direct_csv = complete_url.lower().endswith('.csv')
        
        if is_direct_csv:
            # Untuk file CSV langsung, gunakan GET request biasa tanpa header khusus
            response = executor.session.get(complete_url)
            response.raise_for_status()
            
            # Simpan data CSV mentah
            return {
                "is_raw_csv": True,
                "csv_content": response.text,
                "result": []  # Placeholder untuk format output yang konsisten
            }
        else:
            # Untuk API call regular yang membutuhkan CSRF dan payload JSON
            headers = {
                "Content-Type": "application/json",
                "X-CSRFToken": executor.csrf_token
            }
            
            response = executor.session.post(complete_url, json=payload, headers=headers)
            response.raise_for_status()
            
            # Kembalikan response JSON normal
            return response.json()

class SaveReportCommand(Command):
    def execute(self, executor: CommandExecutor, name, data):
        # Baca output_dir dari config.ini
        config = configparser.ConfigParser(interpolation=None)
        config.read('config.ini')
        
        if 'SETTINGS' in config and 'output_dir' in config['SETTINGS']:
            output_dir = config['SETTINGS']['output_dir']
        else:
            # Fallback ke direktori "output" di lokasi saat ini
            output_dir = "output"
        
        # Membuat direktori output jika belum ada
        os.makedirs(output_dir, exist_ok=True)
        
        # Kasus khusus: file CSV mentah
        if isinstance(data, dict) and data.get("is_raw_csv", False):
            csv_content = data.get("csv_content", "")
            path = os.path.join(output_dir, f"{name}.csv")
            
            with open(path, "w", encoding="utf-8") as f:
                f.write(csv_content)
                
            return f"Report CSV '{name}' berhasil disimpan ke {path}"
        
        # Memproses JSON ke CSV menggunakan pandas
        try:
            # Mencoba mendapatkan data dari format yang diharapkan
            if "result" in data and isinstance(data["result"], list) and len(data["result"]) > 0:
                if "data" in data["result"][0]:
                    df = pd.DataFrame(data["result"][0]["data"])
                    path = os.path.join(output_dir, f"{name}.csv")
                    df.to_csv(path, index=False)
                    return f"Report '{name}' berhasil disimpan ke {path} sebagai CSV"
            
            # Simpan juga sebagai JSON untuk backup
            path_json = os.path.join(output_dir, f"{name}.json")
            with open(path_json, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            return f"Report '{name}' berhasil disimpan ke {path_json} sebagai JSON"
            
        except Exception as e:
            # Fallback ke JSON jika ada error dalam pemrosesan
            path = os.path.join(output_dir, f"{name}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return f"Report '{name}' berhasil disimpan ke {path} dengan format JSON (error: {str(e)})"