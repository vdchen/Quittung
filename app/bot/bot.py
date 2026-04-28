import logging
import asyncio
import os
import httpx
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command

# Configuration
API_URL = os.getenv("API_URL", "http://quittung_api:8000/receipts")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN is not set in environment variables")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

async def forward_file_to_api(
        message: types.Message, 
        file_id: str, 
        file_name: str, 
        mime_type: str, 
        success_msg: str,
        http_client: httpx.AsyncClient
):
    
    """
    Core logic for downloading files from Telegram and forwarding to the FastAPI backend.
    """

    file_info = await bot.get_file(file_id)
    file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            telegram_resp = await http_client.get(file_url)
            telegram_resp.raise_for_status()

            files = {'file': (file_name, telegram_resp.content, mime_type)}
            data = {'chat_id': str(message.chat.id)}
        
            api_resp = await http_client.post(f"{API_URL}/receipts/upload", files=files, data=data)
        
            if api_resp.status_code == 202:
                await message.answer(success_msg)
            else:
                logging.error(f"API Error {api_resp.status_code}: {api_resp.text}")
                await message.answer(f"❌ API Error: Received status code {api_resp.status_code}")
                
        except httpx.HTTPError as e:
            logging.error(f"Network error while forwarding {file_name}: {e}")
            await message.answer("❌ Failed to communicate with the processing server.")
        except Exception as e:
            logging.error(f"Unexpected error processing {file_name}: {e}")
            await message.answer("❌ An unexpected internal error occurred.")

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "Welcome to Quittung! 🧾\n\n"
        "Send me a photo or PDF of a receipt, and I'll extract the data.\n"
        "Use /export to get your Excel report."
    )

@dp.message(F.photo)
async def handle_photo(message: types.Message, http_client: httpx.AsyncClient):
    # Telegram sends an array of photos; [-1] is the highest resolution
    await forward_file_to_api(
        message=message,
        file_id=message.photo[-1].file_id,
        file_name="receipt.jpg",
        mime_type="image/jpeg",
        success_msg="✅ Photo receipt received! I'm processing it now.",
        http_client=http_client
    )

@dp.message(F.document)
async def handle_document(message: types.Message, http_client: httpx.AsyncClient):
    document = message.document
    if document.mime_type != "application/pdf":
        await message.answer("❌ Please send a valid image or PDF receipt.")
        return

    await forward_file_to_api(
        message=message,
        file_id=document.file_id,
        file_name=document.file_name or "receipt.pdf",
        mime_type="application/pdf",
        success_msg="📄 PDF receipt received! I'm analyzing the data now.",
        http_client=http_client
    )

@dp.message(Command("export"))
async def cmd_export(message: types.Message, http_client: httpx.AsyncClient):
    try:
        resp = await http_client.post(f"{API_URL}/exports/export", params={"chat_id": message.chat.id})
        if resp.status_code == 202:
            await message.answer("📊 Generating your Excel report... Stay tuned!")
        else:
            logging.error(f"Export failed with status {resp.status_code}: {resp.text}")
            await message.answer("❌ Failed to initiate export.")
    except httpx.HTTPError as e:
        logging.error(f"Export network trigger failed: {e}")
        await message.answer("❌ Processing server is unreachable.")


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)

    async with httpx.AsyncClient(timeout=30.0, limits=limits) as http_client:
        # aiogram takes any kwargs here and injects them into handlers 
        await dp.start_polling(bot, http_client=http_client)

if __name__ == "__main__":
    asyncio.run(main())