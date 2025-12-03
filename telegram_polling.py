#!/usr/bin/env python3
"""
Standalone Telegram Bot Polling Script
Run this to make the bot respond with Chat IDs when users message it
"""

import asyncio
import httpx
import logging
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get bot token from environment
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
API_BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

last_update_id = 0


async def send_message(chat_id: str, text: str, parse_mode: str = None):
    """Send a message to a Telegram chat"""
    try:
        payload = {
            "chat_id": chat_id,
            "text": text
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{API_BASE_URL}/sendMessage",
                json=payload
            )
            
            if response.status_code == 200:
                logger.info(f"✓ Sent message to chat {chat_id}")
                return True
            else:
                logger.error(f"✗ Failed to send message: {response.text}")
                return False
                
    except Exception as e:
        logger.error(f"✗ Error sending message: {e}")
        return False


async def get_updates(offset: int = None, timeout: int = 30):
    """Get updates from Telegram using long polling"""
    try:
        params = {
            "timeout": timeout,
            "allowed_updates": ["message"]
        }
        if offset:
            params["offset"] = offset
        
        async with httpx.AsyncClient(timeout=timeout + 10.0) as client:
            response = await client.get(
                f"{API_BASE_URL}/getUpdates",
                params=params
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    return data.get("result", [])
            
            return []
            
    except Exception as e:
        logger.error(f"✗ Polling error: {e}")
        return []


async def reply_with_chat_id(chat_id: str, username: str = None):
    """Reply to user with their chat ID"""
    greeting = f"👋 Hello"
    if username:
        greeting += f" @{username}"
    greeting += "!"
    
    message = (
        f"{greeting}\n\n"
        f"✅ *Your Chat ID*\n\n"
        f"`{chat_id}`\n\n"
        f"📋 Copy this ID and paste it in *VisionGuard AI* to receive anomaly notifications.\n\n"
        f"💡 *How to copy:*\n"
        f"• Tap and hold on the ID above\n"
        f"• Select 'Copy'\n"
        f"• Paste it in the VisionGuard AI connection form"
    )
    
    await send_message(chat_id, message, parse_mode="Markdown")


async def main():
    """Main polling loop"""
    global last_update_id
    
    if not BOT_TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN not found in .env file")
        return
    
    logger.info("=" * 70)
    logger.info("🤖 VisionGuard AI Telegram Bot - Polling Mode")
    logger.info("=" * 70)
    logger.info(f"✓ Bot token loaded")
    logger.info(f"✓ Starting polling...")
    logger.info(f"✓ Bot will reply with Chat ID to any message received")
    logger.info(f"💡 Press Ctrl+C to stop")
    logger.info("=" * 70)
    
    try:
        while True:
            # Get updates
            updates = await get_updates(
                offset=last_update_id + 1 if last_update_id > 0 else None,
                timeout=30
            )
            
            if updates:
                logger.info(f"📨 Received {len(updates)} update(s)")
                
                for update in updates:
                    try:
                        update_id = update.get("update_id", 0)
                        message = update.get("message", {})
                        
                        if not message:
                            continue
                        
                        chat = message.get("chat", {})
                        chat_id = str(chat.get("id", ""))
                        username = chat.get("username", "")
                        first_name = chat.get("first_name", "")
                        text = message.get("text", "")
                        
                        # Update last processed ID
                        if update_id > last_update_id:
                            last_update_id = update_id
                        
                        if not chat_id:
                            continue
                        
                        # Log the message
                        user_display = username or first_name or chat_id
                        logger.info(f"📩 Message from {user_display}: {text}")
                        
                        # Reply with chat ID
                        await reply_with_chat_id(chat_id, username)
                        logger.info(f"✅ Sent Chat ID to {user_display}")
                    
                    except Exception as e:
                        logger.error(f"❌ Error processing update: {e}")
            
            # Small delay between polling cycles
            await asyncio.sleep(1)
    
    except KeyboardInterrupt:
        logger.info("\n" + "=" * 70)
        logger.info("🛑 Stopping bot...")
        logger.info("=" * 70)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
