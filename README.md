# 🎲 Telegram Games Bot

A student Python project featuring a Ukrainian-language Telegram bot with dice games, points, a one-time promo code and optional random photos.

## Features

- Reply keyboard menus and entertainment links
- Telegram dice rolls with points based on the result
- Maximum three dice rolls per user in a rolling 60-second window
- SQLite points that persist between restarts
- One-time `промік` code awarding 20 points per user
- Optional random JPG/PNG photos; `2.jpg` awards 10 bonus points
- Friendly handling of unknown messages and missing photos

Football is a placeholder, not a playable game. External entertainment links are retained from the original project and their availability has not been verified.

## Requirements

- Python 3.10 or newer
- A Telegram bot token from [BotFather](https://t.me/BotFather)
- Internet access for Telegram

## Setup on Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:TELEGRAM_BOT_TOKEN = "YOUR_NEW_BOT_TOKEN"
.\.venv\Scripts\python.exe main.py
```

## Setup on macOS / Linux

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN="YOUR_NEW_BOT_TOKEN"
.venv/bin/python main.py
```

The program reads the environment variable directly; it does not load `.env` files.
Open the bot in Telegram and send `/start`. Keep the process running to receive messages; press Ctrl+C to stop. Run only one polling instance per token.

## Data and Photos

`users.db` is created automatically next to `main.py`. Existing user data and credentials are not distributed with this project. Do not commit a live database or token.

Add optional photos to `photos/`; see its README. Dice rate limits are held in memory and reset when the process restarts. Points and promo redemptions remain in SQLite. The photo bonus has no cooldown, matching the original behaviour. Points have no monetary value.

## Tests

```bash
python -m unittest discover -s tests -v
```

Tests exercise database persistence, promo redemption, rate limits and message handlers with Telegram requests mocked. They do not send real Telegram messages. A live test with your own token is still required.

## Project Files

- `main.py` — bot handlers, points storage and dice limits
- `requirements.txt` — pinned dependency
- `photos/` — optional local images
- `tests/` — offline regression tests
- `.gitignore` — excludes local credentials, databases and development files
