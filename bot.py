import asyncio
import os
import tempfile
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import FSInputFile, Message
from PIL import Image, ImageOps
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

bot = Bot(TOKEN)
dp = Dispatcher()
MAX_DOWNLOAD = 20 * 1024 * 1024
STICKER_SIZE = 512


def make_sticker(source: Path, output: Path) -> None:
    with Image.open(source) as im:
        im = ImageOps.exif_transpose(im).convert("RGBA")
        # Telegram static stickers must fit within 512x512 while preserving aspect ratio.
        im.thumbnail((STICKER_SIZE, STICKER_SIZE), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (STICKER_SIZE, STICKER_SIZE), (0, 0, 0, 0))
        x = (STICKER_SIZE - im.width) // 2
        y = (STICKER_SIZE - im.height) // 2
        canvas.alpha_composite(im, (x, y))
        canvas.save(output, "WEBP", lossless=True, method=6)


@dp.message(Command("start"))
async def start(message: Message):
    await message.answer(
        "Image to Sticker\n\n"
        "Send me an image and I will convert it into a Telegram sticker.\n\n"
        "Supported: JPG, JPEG, PNG and WEBP."
    )


@dp.message(Command("help"))
async def help_cmd(message: Message):
    await message.answer(
        "How to use:\n"
        "1. Send me an image as a photo or document.\n"
        "2. I resize it to Telegram sticker dimensions.\n"
        "3. I return a WEBP sticker.\n\n"
        "Use /start to see the basic instructions."
    )


async def convert_image(message: Message, file_id: str, suffix: str):
    if message.from_user is None:
        return
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / f"source{suffix}"
        out = Path(tmp) / "sticker.webp"
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

            make_sticker(src, out)
            if not out.exists() or out.stat().st_size == 0:
                raise RuntimeError("Sticker file was not created")

            # aiogram 3 requires an InputFile object for file uploads.
            await message.answer_sticker(sticker=FSInputFile(out))
        except Exception as exc:
            print(f"Conversion error: {type(exc).__name__}: {exc}")
            await message.answer("I couldn't convert that image. Please try a JPG, PNG, JPEG or WEBP image.")


@dp.message(F.photo)
async def photo_handler(message: Message):
    photo = message.photo[-1]
    await message.answer("Converting your image...")
    await convert_image(message, photo.file_id, ".jpg")


@dp.message(F.document)
async def document_handler(message: Message):
    doc = message.document
    mime = (doc.mime_type or "").lower()
    name = (doc.file_name or "").lower()
    allowed = mime in {"image/jpeg", "image/png", "image/webp"} or name.endswith((".jpg", ".jpeg", ".png", ".webp"))
    if not allowed:
        await message.answer("Please send a JPG, JPEG, PNG or WEBP image.")
        return
    if doc.file_size and doc.file_size > MAX_DOWNLOAD:
        await message.answer("That image is too large. Please send an image under 20 MB.")
        return
    await message.answer("Converting your image...")
    suffix = Path(doc.file_name or "image.jpg").suffix or ".jpg"
    await convert_image(message, doc.file_id, suffix)


@dp.message()
async def fallback(message: Message):
    await message.answer("Send me an image and I’ll turn it into a Telegram sticker.")


async def main():
    print("Image to Sticker bot is running...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
