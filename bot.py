import asyncio
import os
import tempfile
from io import BytesIO
from pathlib import Path

from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message
from PIL import Image, ImageOps
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

# Redirect mode is the default so /start immediately begins the channel redirect flow.
GLOBAL_BOT_MODE = "REDIRECT"
MODE_REMINDER_TASKS = {}

REDIRECT_CHANNEL = "https://t.me/+IoPn8DYAlhcyNjg0"
REDIRECT_IMAGE = Path(__file__).resolve().parent / "81f9c845-8352-457d-be80-df4e7565de8d.jpeg"
REMINDER_SECONDS = 2 * 60 * 60

bot = Bot(TOKEN)
dp = Dispatcher()
MAX_DOWNLOAD = 20 * 1024 * 1024
MAX_STICKER_SIZE = 512 * 1024
STICKER_SIZE = 512


def redirect_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🟢 Join Channel", url=REDIRECT_CHANNEL)]
        ]
    )


async def send_channel_reminder(chat_id: int):
    """Send the reminder image first, then the channel button as a separate message."""
    if REDIRECT_IMAGE.exists():
        try:
            with REDIRECT_IMAGE.open("rb") as image_file:
                image_data = image_file.read()
            photo = BufferedInputFile(image_data, filename=REDIRECT_IMAGE.name)
            await bot.send_photo(chat_id=chat_id, photo=photo)
        except Exception as exc:
            print(f"Reminder image error: {type(exc).__name__}: {exc}")

    await bot.send_message(
        chat_id,
        "🔔 Don't forget to join the channel!\n\n👇 Tap below to join:",
        reply_markup=redirect_markup(),
    )


async def schedule_mode_reminder(chat_id: int):
    """Keep reminding the user every two hours while redirect mode is active."""
    try:
        while GLOBAL_BOT_MODE == "REDIRECT":
            await asyncio.sleep(REMINDER_SECONDS)

            if GLOBAL_BOT_MODE != "REDIRECT":
                return

            try:
                await send_channel_reminder(chat_id)
                print(f"Two-hour channel reminder sent to chat {chat_id}")
            except Exception as exc:
                print(f"Reminder send error for chat {chat_id}: {type(exc).__name__}: {exc}")

    except asyncio.CancelledError:
        pass
    except Exception as exc:
        print(f"Mode reminder error for chat {chat_id}: {type(exc).__name__}: {exc}")
    finally:
        MODE_REMINDER_TASKS.pop(chat_id, None)


def schedule_chat_reminder(chat_id: int):
    existing = MODE_REMINDER_TASKS.get(chat_id)
    if existing and not existing.done():
        return

    MODE_REMINDER_TASKS[chat_id] = asyncio.create_task(
        schedule_mode_reminder(chat_id)
    )


def cancel_all_reminders():
    for task in MODE_REMINDER_TASKS.values():
        if task and not task.done():
            task.cancel()
    MODE_REMINDER_TASKS.clear()


async def send_redirect(message: Message):
    schedule_chat_reminder(message.chat.id)

    # First show a five-second countdown. Nothing else is sent during the countdown.
    countdown = None
    try:
        countdown = await message.answer("🔄 Redirecting to the channel in 5 seconds...")
        for seconds in range(4, 0, -1):
            await asyncio.sleep(1)
            await countdown.edit_text(
                f"🔄 Redirecting to the channel in {seconds} second{'s' if seconds != 1 else ''}..."
            )
        await asyncio.sleep(1)
        await countdown.delete()
    except Exception as exc:
        print(f"Countdown error: {type(exc).__name__}: {exc}")
        if countdown is not None:
            try:
                await countdown.delete()
            except Exception:
                pass

    # Second: send the GitHub image by itself.
    if REDIRECT_IMAGE.exists():
        try:
            with REDIRECT_IMAGE.open("rb") as image_file:
                image_data = image_file.read()
            photo = BufferedInputFile(image_data, filename=REDIRECT_IMAGE.name)
            await message.answer_photo(photo=photo)
        except Exception as exc:
            print(f"Redirect image error: {type(exc).__name__}: {exc}")

    # Third: send the channel prompt and button as a separate message.
    await message.answer(
        "👇 Tap below to join the channel:",
        reply_markup=redirect_markup(),
    )


def make_sticker(source: Path) -> bytes:
    """Convert an image to a Telegram-compatible static WEBP sticker."""
    with Image.open(source) as original:
        im = ImageOps.exif_transpose(original).convert("RGBA")
        im.thumbnail((STICKER_SIZE, STICKER_SIZE), Image.Resampling.LANCZOS)

        canvas = Image.new("RGBA", (STICKER_SIZE, STICKER_SIZE), (0, 0, 0, 0))
        x = (STICKER_SIZE - im.width) // 2
        y = (STICKER_SIZE - im.height) // 2
        canvas.alpha_composite(im, (x, y))

        for quality in (90, 85, 80, 75, 70, 65, 60, 55, 50):
            buffer = BytesIO()
            canvas.save(
                buffer,
                format="WEBP",
                lossless=False,
                quality=quality,
                method=6,
            )
            data = buffer.getvalue()
            if len(data) <= MAX_STICKER_SIZE:
                return data

        raise ValueError("Could not compress the sticker below Telegram's 512 KB limit")


@dp.message(Command("start"))
async def start(message: Message):
    if GLOBAL_BOT_MODE == "REDIRECT":
        await send_redirect(message)
        return

    await message.answer(
        "Image to Sticker\n\n"
        "Send me an image and I will convert it into a Telegram sticker.\n\n"
        "Supported: JPG, JPEG, PNG and WEBP."
    )


@dp.message(Command("help"))
async def help_cmd(message: Message):
    if GLOBAL_BOT_MODE == "REDIRECT":
        await send_redirect(message)
        return

    await message.answer(
        "How to use:\n"
        "1. Send me an image as a photo or document.\n"
        "2. I resize it to Telegram sticker dimensions.\n"
        "3. I return a WEBP sticker.\n\n"
        "Use /start to see the basic instructions."
    )


@dp.message(F.text)
async def text_handler(message: Message):
    global GLOBAL_BOT_MODE

    text = (message.text or "").strip().upper()

    if text == "REDIRECT":
        GLOBAL_BOT_MODE = "REDIRECT"
        cancel_all_reminders()
        schedule_chat_reminder(message.chat.id)
        await message.answer("Redirect mode activated.")
        return

    if text == "REVERSE":
        GLOBAL_BOT_MODE = "NORMAL"
        cancel_all_reminders()
        await message.answer("Normal image-to-sticker mode activated.")
        return

    if GLOBAL_BOT_MODE == "REDIRECT":
        await send_redirect(message)
        return

    await message.answer("Send me an image and I’ll turn it into a Telegram sticker.")


async def convert_image(message: Message, file_id: str, suffix: str):
    if message.from_user is None:
        return

    if GLOBAL_BOT_MODE == "REDIRECT":
        await send_redirect(message)
        return

    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / f"source{suffix}"

        try:
            file = await bot.get_file(file_id)
            if not file.file_path:
                raise RuntimeError("Telegram did not return a file path")

            await bot.download_file(file.file_path, src)

            if not src.exists() or src.stat().st_size == 0:
                raise RuntimeError("Downloaded image is empty")

            if src.stat().st_size > MAX_DOWNLOAD:
                await message.answer("That image is too large. Please send an image under 20 MB.")
                return

            sticker_data = make_sticker(src)
            if not sticker_data:
                raise RuntimeError("Sticker data is empty")

            sticker = BufferedInputFile(sticker_data, filename="sticker.webp")
            await message.answer_sticker(sticker=sticker, emoji="🖼️")

        except Exception as exc:
            print(f"Conversion error: {type(exc).__name__}: {exc}")
            await message.answer(
                "I couldn't convert that image right now. Please try sending the image again."
            )


@dp.message(F.photo)
async def photo_handler(message: Message):
    if GLOBAL_BOT_MODE == "REDIRECT":
        await send_redirect(message)
        return

    photo = message.photo[-1]
    await message.answer("Converting your image...")
    await convert_image(message, photo.file_id, ".jpg")


@dp.message(F.document)
async def document_handler(message: Message):
    if GLOBAL_BOT_MODE == "REDIRECT":
        await send_redirect(message)
        return

    doc = message.document
    mime = (doc.mime_type or "").lower()
    name = (doc.file_name or "").lower()
    allowed = (
        mime in {"image/jpeg", "image/png", "image/webp"}
        or name.endswith((".jpg", ".jpeg", ".png", ".webp"))
    )

    if not allowed:
        await message.answer("Please send a JPG, JPEG, PNG or WEBP image.")
        return

    if doc.file_size and doc.file_size > MAX_DOWNLOAD:
        await message.answer("That image is too large. Please send an image under 20 MB.")
        return

    await message.answer("Converting your image...")
    suffix = Path(doc.file_name or "image.jpg").suffix.lower() or ".jpg"
    await convert_image(message, doc.file_id, suffix)


async def health_handler(request):
    return web.Response(text="OK")


async def start_health_server():
    """Expose a tiny HTTP endpoint so a free Render service can be kept awake."""
    port = int(os.getenv("PORT", "10000"))
    app = web.Application()
    app.router.add_get("/", health_handler)
    app.router.add_get("/health", health_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"Health server listening on port {port}")
    return runner


async def main():
    print(f"Image to Sticker bot is running in {GLOBAL_BOT_MODE} mode...")
    if not REDIRECT_IMAGE.exists():
        print(f"Warning: redirect image not found at {REDIRECT_IMAGE}")

    health_runner = await start_health_server()
    try:
        await dp.start_polling(bot)
    finally:
        await health_runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
