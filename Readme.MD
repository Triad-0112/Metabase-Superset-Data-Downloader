# Metabase/Superset CSV Downloader

A Python desktop application for automated downloading of reports from Metabase/Superset dashboards with scheduling capabilities.

## 🌟 Features

- **Automated Downloads**: Schedule automatic report downloads at configurable intervals
- **Concurrent Processing**: Download multiple reports simultaneously 
- **Randomized Interval Jitter**: Adds a random delay to scheduled downloads to avoid overloading the server.
- **System Tray Integration**: Run minimized while maintaining functionality
- **Multiple Source Support**: 
  - Metabase CSV endpoints
  - Superset API integration
  - Direct CSV URL downloads
- **Progress Tracking**: Visual feedback for download progress
- **Detailed Logging**: Comprehensive activity logging
- **Locking into one Instance**: Make sure that was only one instance that is allowed to run

## 🔧 Requirements

- Python 3.12+
- PyQt6
- requests
- configparser
- pandas

## 📁 Project Structure

```
LinkDownloader/
├── main.py              # Application entry point
├── config.ini          # Configuration settings
├── request.json        # Report definitions
├── core/
│   ├── __init__.py
│   └── commands.py     # MVC pattern implementations
└── gui/
    ├── __init__.py
    ├── controller.py   # Main application logic
    ├── dialogs.py      # UI dialog windows
    ├── extractor.py    # Download workers
    ├── model.py        # Data model
    └── view.py         # Main window UI
```

## ⚙️ Configuration

### config.ini
```ini
[SETTINGS]
output_dir = D:/Output/Folder
max_workers = 10
base_url = https://dashboard.example.com

[LOGIN]
username = your_username
password = your_password

[INTERVAL]
enabled = True
interval_minutes = 120
minimize_to_tray = True
```
**Note on Jitter**: To distribute server load, the application adds a random "jitter" to the `interval_minutes`. When auto-mode is first started, a short jitter of **1-5 minutes** is added before the first extraction. All subsequent automatic extractions will have a jitter of **1-20 minutes** added to the base interval.

### request.json
Define your reports in JSON format:
```json
{
    "Report Name A": {
        "request_url": "https://www.example.com/master.csv",
        "payload": {}
    },
    "Report Name B": {
        "request_url": "/api/v1/chart/data",
        "payload": {
            "datasource": {"id": 123, "type": "table"},
            "force": false
        }
    }
}
```

## 🚀 Getting Started

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Configure credentials in `config.ini`
4. Add report definitions to `request.json`
5. Run the application:
   ```bash
   python main.py
   ```

## 💻 Usage

1. **Initial Setup**:
   - Configure output directory
   - Set login credentials
   - Add report definitions

2. **Manual Download**:
   - Select reports from the list
   - Click "Start Extraction"
   - Monitor progress in the log window

3. **Automated Mode**:
   - Configure interval settings
   - Enable auto mode
   - The application will add a random delay (jitter) to the configured interval for each run and can be minimized to the system tray to run in the background.

## 🔑 Key Components

- **CommandExecutor**: Handles API operations using Command pattern
- **ExtractorWorker**: Manages concurrent downloads
- **ReportModel**: Handles data and configuration management
- **MainWindow**: Primary user interface
- **Controller**: Core application logic and automation

## 🛠️ Development

### Building from Source
```bash
pyinstaller --name LinkDownloader --windowed main.py
```

### Adding New Reports
1. Open `request.json`
2. Add new entry with URL and payload
3. Restart application to load changes

## 📝 Error Handling

- Network connectivity issues
- Invalid credentials
- API rate limiting
- File system permissions
- Concurrent download limits

## 🤝 Contributing

1. Fork the repository
2. Create feature branch
3. Commit changes
4. Submit pull request

## 📄 License

This project is licensed under the MIT License. See the LICENSE file for details.

## 🔮 Future Enhancements

- Email notifications
- Custom report scheduling
- Data validation
- Export format options
- Dashboard integration

## 📞 Support

For issues and feature requests, please create an issue in the repository.