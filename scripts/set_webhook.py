import asyncio
import logging
from aiogram import Bot
from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = settings.TELEGRAM_BOT_TOKEN
TELEGRAM_WEBHOOK_SECRET = settings.TELEGRAM_WEBHOOK_SECRET


async def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set in .env")
        return

    webhook_url = input("Enter your public HTTPS URL (e.g. https://abc.ngrok.io): ").strip().rstrip("/")

    if not webhook_url:
        logger.warning("Webhook URL cannot be empty.")
        return

    full_url = f"{webhook_url}/api/v1/telegram/webhook"
    logger.info(f"Setting webhook to: {full_url}")

    bot = Bot(token=TELEGRAM_BOT_TOKEN)

    # Pass the secret token so Telegram signs every incoming update with
    # X-Telegram-Bot-Api-Secret-Token. The endpoint validates this header.
    result = await bot.set_webhook(
        url=full_url,
        secret_token=TELEGRAM_WEBHOOK_SECRET or None,
    )

    if result:
        logger.info("✅ Webhook set successfully!")
        if TELEGRAM_WEBHOOK_SECRET:
            logger.info("🔒 Secret token is active — spoofed requests will be rejected.")
        else:
            logger.warning("⚠️  No TELEGRAM_WEBHOOK_SECRET set. Webhook is unauthenticated.")
    else:
        logger.error("❌ Failed to set webhook.")

    await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
