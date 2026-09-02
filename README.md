# Image to Sticker Telegram Bot

A simple Telegram utility bot that converts JPG, JPEG, PNG and WEBP images into Telegram-compatible static WEBP stickers.

## Features

- Convert Telegram photos to stickers
- Convert image documents to stickers
- Preserve transparency for PNG/WEBP inputs
- EXIF orientation correction
- Automatic resize to fit 512x512
- Temporary-file cleanup
- Basic file validation and 20 MB input limit

## Setup

1. Create the bot with Telegram's BotFather and copy the token.
2. Install Python 3.10+.
3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Set `BOT_TOKEN` in a `.env` file or your deployment environment.
5. Start the bot:

```bash
python bot.py
```

## Usage

Send an image to the bot. It will return a WEBP sticker.

Commands:

- `/start` — introduction and instructions
- `/help` — usage instructions

## Notes

This version creates standard static WEBP stickers. Creating and maintaining named Telegram sticker packs can be added as a later feature. Never commit your real bot token to GitHub.
