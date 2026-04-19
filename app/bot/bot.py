import logging
import asyncio
import os
import httpx
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command

# 1. Configuration - Use consistent naming
API_URL = os.getenv("API_URL", "http://quittung_api:8000/receipts")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN is not set in environment variables")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "Welcome to Quittung! 🧾\n\n"
        "Send me a photo of a receipt, and I'll extract the data.\n"
        "Use /export to get your Excel report."
    )

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    # Get the highest resolution photo
    photo = message.photo[-1]
    file_info = await bot.get_file(photo.file_id)
    # Corrected interpolation
    file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"

    # Increase timeout for high-res images and slow processing
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # Download from Telegram
            telegram_resp = await client.get(file_url)
            telegram_resp.raise_for_status()
            
            # Forward to our FastAPI
            files = {'file': ('receipt.jpg', telegram_resp.content, 'image/jpeg')}
            api_resp = await client.post(f"{API_URL}/upload", files=files)
            
            if api_resp.status_code == 202:
                await message.answer("✅ Receipt received! I'm processing it now.")
            else:
                await message.answer(f"❌ API Error: {api_resp.status_code}")
                
        except Exception as e:
            logging.error(f"Failed to process photo: {e}")
            await message.answer("❌ Failed to reach the processing server.")

@dp.message(Command("export"))
async def cmd_export(message: types.Message):
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            # Note: query param chat_id is used by the worker for the callback
            params = {"chat_id": message.chat.id}
            resp = await client.post(f"{API_URL}/export", params=params)
            
            if resp.status_code == 202:
                await message.answer("📊 Generating your Excel report... Stay tuned!")
            else:
                await message.answer("❌ Failed to initiate export.")
        except Exception as e:
            logging.error(f"Export trigger failed: {e}")
            await message.answer("❌ Processing server is unreachable.")

async def main():
    logging.basicConfig(level=logging.INFO)
    # Start polling (The "Listener" mode)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())