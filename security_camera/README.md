# Security and Surveillance Bot

A security bot that detects motion from the laptop camera and sends photos to Telegram.

## Installation

### 1. Install requirements
```bash
pip install opencv-python requests python-dotenv
```

### 2. Set up the Telegram bot
Open the `.env` file and fill in these two fields:
```
TELEGRAM_BOT_TOKEN=7123456789:AAHxxxxxxxxxxxx
TELEGRAM_CHAT_ID=123456789
```

> ⚠️ Never commit the `.env` file to Git! `.gitignore` already prevents this.

### 3. Run
```bash
python security_bot.py
```

Press `Ctrl+C` to stop.

## Settings (config.ini)

You can change technical settings from `config.ini`. Sensitive information is not here, it's in `.env`.

| Setting | Default | Description |
|---------|---------|-------------|
| threshold | 25 | Motion sensitivity (lower = more sensitive) |
| min_contour_area | 5000 | Minimum motion area (filters small movements) |
| cooldown | 30 | Wait time between detections (seconds) |

## File Structure
```
security_bot/
├── security_bot.py    # Main program
├── config.ini         # Technical settings (thresholds, cooldown)
├── .env               # Sensitive information (token, chat_id) — Not committed to Git
├── .gitignore         # Keeps .env and temporary files out of Git
├── captures/          # Captured photos (created automatically)
└── security_log.txt   # Event log (created automatically)
```

## Tips
- If you're getting too many false alarms, increase the `threshold` value (30-40)
- If you want it to detect small movements too, decrease the `min_contour_area` value
- If you leave the laptop lid half-open, the camera will continue working
