# gui/model.py
import json
import os
import configparser
import copy

REQUEST_FILE = "request.json"
CONFIG_FILE = "config.ini"

class ReportModel:
    def __init__(self):
        self._load_config()
        self._load_reports()

    def _load_config(self):
        self.config = configparser.ConfigParser(interpolation=None)
        self.config.read(CONFIG_FILE)

        # PERUBAHAN: Pastikan section [SETTINGS] ada dengan base_url
        if "SETTINGS" not in self.config:
            print("[WARNING] Section [SETTINGS] tidak ditemukan di config.ini")
            self.config["SETTINGS"] = {
                "output_dir": os.getcwd(),
                "base_url": "https://dashboard.ecocare.co.id"  # Default base_url
            }
        elif "base_url" not in self.config["SETTINGS"]:
            # Tambahkan base_url jika belum ada
            self.config["SETTINGS"]["base_url"] = "https://dashboard.ecocare.co.id"
            with open(CONFIG_FILE, "w") as f:
                self.config.write(f)

        self.output_dir = self.config["SETTINGS"].get("output_dir", os.getcwd())
        self.base_url = self.config["SETTINGS"].get("base_url", "https://dashboard.ecocare.co.id")

    def save_output_dir(self, path):
        self.output_dir = path
        self.config["SETTINGS"]["output_dir"] = path
        with open(CONFIG_FILE, "w") as f:
            self.config.write(f)

    def _load_reports(self):
        try:
            with open(REQUEST_FILE, "r") as f:
                self.reports = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"[WARNING] Gagal load request.json: {e}")
            self.reports = {}


    def save_reports(self):
        with open(REQUEST_FILE, "w") as f:
            json.dump(self.reports, f, indent=4)

    def get_report_list(self):
        return list(self.reports.keys())

    def get_report(self, name):
        return self.reports.get(name, None)

    def add_report(self, name, request_url, payload):
        self.reports[name] = {
            "request_url": request_url,
            "payload": payload
        }
        self.save_reports()

    def edit_report(self, old_name, new_name, request_url, payload):
        if old_name != new_name:
            self.reports.pop(old_name, None)
        self.reports[new_name] = {
            "request_url": request_url,
            "payload": payload
        }
        self.save_reports()

    def delete_report(self, name):
        if name in self.reports:
            del self.reports[name]
            self.save_reports()

    def get_all_reports(self):
        return copy.deepcopy(self.reports)
    
    def get_output_dir(self):
        return self.output_dir
    
    def get_base_url(self):
        return self.base_url