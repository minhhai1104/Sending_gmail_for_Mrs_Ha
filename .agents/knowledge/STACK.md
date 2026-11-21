# Technology Stack & Environment

- **Language**: Python 3.10+ (Đang phát triển trên Python 3.13.3).
- **GUI Framework**: Tkinter + `ttk` (Standard Python Library) — Zero external heavy dependencies.
- **Excel Handling**: `openpyxl` 3.1.5 (Tích hợp sẵn trong thư mục `vendor/`).
- **Email Protocol**: `smtplib` + `ssl` + `email.message.EmailMessage` (Standard Library) — SSL Port 465.
- **Storage**: SQLite 3 (`sqlite3` Standard Library) + CSV export (`csv` Standard Library).
- **Packaging**: PyInstaller (`pyproject.toml` / `.spec` file).
- **Testing**: `pytest` 9.2.0 + `unittest.mock`.
- **Linting & Formatting**: `ruff` + `mypy`.
- **Target OS**: Windows 10/11 (64-bit).
