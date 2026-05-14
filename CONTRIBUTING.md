# Contributing

Thanks for considering a contribution to PaperHunter.

## Development Setup

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:8000` in a browser.

## Before Opening a Pull Request

Run the basic checks:

```bash
python -m py_compile app.py
node --check web/app.js
```

Do not commit:

- downloaded PDFs
- `.cache/`
- virtual environments
- local path or credential files

## Source Integration Rules

New automated sources should use open APIs, open-access feeds, or direct public PDF URLs. Do not add logic that bypasses login, payment, CAPTCHA, rate limits, or access-control mechanisms.

For restricted sources, prefer an external browser entry with keyword transfer instead of automated scraping or downloading.
