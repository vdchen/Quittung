import asyncio
from aiogram import Bot
from app.core.config import settings

TELEGRAM_BOT_TOKEN = settings.TELEGRAM_BOT_TOKEN
TELEGRAM_WEBHOOK_SECRET = settings.TELEGRAM_WEBHOOK_SECRET


async def main():
    if not TELEGRAM_BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN is not set in .env")
        return

    webhook_url = input("Enter your public HTTPS URL (e.g. https://abc.ngrok.io): ").strip().rstrip("/")

    if not webhook_url:
        print("Webhook URL cannot be empty.")
        return

    full_url = f"{webhook_url}/api/v1/telegram/webhook"
    print(f"Setting webhook to: {full_url}")

    bot = Bot(token=TELEGRAM_BOT_TOKEN)

    # Pass the secret token so Telegram signs every incoming update with
    # X-Telegram-Bot-Api-Secret-Token. The endpoint validates this header.
    result = await bot.set_webhook(
        url=full_url,
        secret_token=TELEGRAM_WEBHOOK_SECRET or None,
    )

    if result:
        print("✅ Webhook set successfully!")
        if TELEGRAM_WEBHOOK_SECRET:
            print("🔒 Secret token is active — spoofed requests will be rejected.")
        else:
            print("⚠️  No TELEGRAM_WEBHOOK_SECRET set. Webhook is unauthenticated.")
    else:
        print("❌ Failed to set webhook.")

    await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
