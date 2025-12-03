"""
Telegram Bot Webhook Endpoint
Handles incoming updates from Telegram Bot API
"""

import logging
import asyncio
from typing import Dict, Any
from uuid import UUID
from fastapi import APIRouter, HTTPException, Request, Depends, Query, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Shop
from app.services.telegram_service import get_telegram_service

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/telegram", tags=["Telegram Bot"])

# Store the last processed update ID to avoid processing duplicates
last_update_id = 0
polling_active = False


class TelegramUpdate(BaseModel):
    """Telegram update model (simplified)"""
    update_id: int
    message: Dict[str, Any] = Field(default_factory=dict)


@router.post(
    "/webhook",
    summary="Telegram Bot Webhook",
    description="Receives updates from Telegram Bot API"
)
async def telegram_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Handle incoming Telegram webhook updates
    
    Processes /start commands with shop_id payload to connect shops to Telegram chats
    """
    try:
        # Parse update data
        update_data = await request.json()
        logger.info(f"[Telegram Webhook] Received update: {update_data}")
        
        # Check if it's a message update
        if "message" not in update_data:
            logger.info("[Telegram Webhook] Update doesn't contain a message")
            return {"ok": True}
        
        message = update_data["message"]
        
        # Extract chat and user info
        chat = message.get("chat", {})
        chat_id = chat.get("id")
        
        if not chat_id:
            logger.warning("[Telegram Webhook] No chat_id in message")
            return {"ok": True}
        
        # Check if it's a /start command
        text = message.get("text", "")
        
        if not text.startswith("/start"):
            logger.info(f"[Telegram Webhook] Not a /start command: {text}")
            return {"ok": True}
        
        # Extract shop_id from /start payload
        # Format: /start <shop_id>
        parts = text.split()
        
        if len(parts) < 2:
            # No payload, send welcome message
            telegram_service = get_telegram_service()
            await telegram_service.send_message(
                str(chat_id),
                "👋 Welcome to VisionGuard AI Bot!\n\n"
                "To connect your shop to Telegram notifications, please use the 'Connect Telegram' "
                "button in your shop management page."
            )
            return {"ok": True}
        
        shop_id_str = parts[1]
        
        # Validate and get shop
        try:
            shop_id = UUID(shop_id_str)
        except ValueError:
            logger.error(f"[Telegram Webhook] Invalid shop_id format: {shop_id_str}")
            telegram_service = get_telegram_service()
            await telegram_service.send_message(
                str(chat_id),
                "❌ Invalid shop ID. Please use the correct link from your shop management page."
            )
            return {"ok": True}
        
        shop = db.query(Shop).filter(Shop.id == shop_id).first()
        
        if not shop:
            logger.error(f"[Telegram Webhook] Shop not found: {shop_id}")
            telegram_service = get_telegram_service()
            await telegram_service.send_message(
                str(chat_id),
                "❌ Shop not found. Please check the link and try again."
            )
            return {"ok": True}
        
        # Update shop with telegram_chat_id
        shop.telegram_chat_id = str(chat_id)
        db.commit()
        
        logger.info(
            f"[Telegram Webhook] Connected shop '{shop.name}' (ID: {shop_id}) "
            f"to Telegram chat {chat_id}"
        )
        
        # Send confirmation message
        telegram_service = get_telegram_service()
        await telegram_service.send_message(
            str(chat_id),
            f"✅ Successfully connected!\n\n"
            f"Your shop *{shop.name}* is now connected to Telegram notifications.\n\n"
            f"You will receive alerts here when suspicious activity is detected.",
            parse_mode="Markdown"
        )
        
        return {"ok": True}
        
    except Exception as e:
        logger.error(f"[Telegram Webhook] Error processing update: {e}")
        return {"ok": False, "error": str(e)}


@router.get(
    "/webhook-info",
    summary="Get Webhook Info",
    description="Get current webhook configuration"
)
async def get_webhook_info():
    """Get current webhook information"""
    telegram_service = get_telegram_service()
    info = await telegram_service.get_webhook_info()
    return {"webhook_info": info}


@router.post(
    "/set-webhook",
    summary="Set Webhook URL",
    description="Configure webhook URL for the bot"
)
async def set_webhook(webhook_url: str):
    """
    Set the webhook URL for the Telegram bot
    
    Args:
        webhook_url: Full URL where Telegram will send updates
    """
    telegram_service = get_telegram_service()
    success = await telegram_service.set_webhook(webhook_url)
    
    if success:
        return {"success": True, "message": f"Webhook set to {webhook_url}"}
    else:
        raise HTTPException(status_code=500, detail="Failed to set webhook")


@router.post(
    "/delete-webhook",
    summary="Delete Webhook",
    description="Remove webhook configuration"
)
async def delete_webhook():
    """Delete the current webhook"""
    telegram_service = get_telegram_service()
    success = await telegram_service.delete_webhook()
    
    if success:
        return {"success": True, "message": "Webhook deleted"}
    else:
        raise HTTPException(status_code=500, detail="Failed to delete webhook")


@router.post(
    "/disconnect-shop/{shop_id}",
    summary="Disconnect Shop from Telegram",
    description="Remove Telegram connection from a shop"
)
async def disconnect_shop_telegram(
    shop_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Disconnect a shop from Telegram notifications
    
    Args:
        shop_id: Shop UUID
    """
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    
    if not shop.telegram_chat_id:
        raise HTTPException(status_code=400, detail="Shop is not connected to Telegram")
    
    # Clear telegram_chat_id
    shop.telegram_chat_id = None
    db.commit()
    
    logger.info(f"[Telegram] Disconnected shop '{shop.name}' (ID: {shop_id}) from Telegram")
    
    return {
        "success": True,
        "message": f"Shop '{shop.name}' disconnected from Telegram"
    }


@router.post(
    "/connect-shop",
    summary="Manually Connect Shop to Telegram",
    description="Connect a shop to Telegram using a chat ID (for polling mode)"
)
async def connect_shop_telegram(
    shop_id: str = Query(..., description="Shop ID to connect"),
    chat_id: str = Query(..., description="Telegram chat ID"),
    db: Session = Depends(get_db)
):
    """
    Manually connect a shop to Telegram chat
    Used when webhook is not available (polling mode)
    
    Args:
        shop_id: Shop UUID
        chat_id: Telegram chat ID from the user
    """
    try:
        shop_uuid = UUID(shop_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid shop ID format")
    
    shop = db.query(Shop).filter(Shop.id == shop_uuid).first()
    
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    
    # Verify the chat ID is valid by trying to get chat info
    telegram_service = get_telegram_service()
    chat_info = await telegram_service.get_chat_info(chat_id)
    
    if not chat_info:
        raise HTTPException(
            status_code=400, 
            detail="Invalid chat ID or bot is not a member of this chat"
        )
    
    # Update shop with telegram_chat_id
    shop.telegram_chat_id = chat_id
    db.commit()
    
    logger.info(
        f"[Telegram] Manually connected shop '{shop.name}' (ID: {shop_id}) "
        f"to Telegram chat {chat_id}"
    )
    
    # Send confirmation message
    await telegram_service.send_message(
        chat_id,
        f"✅ Successfully connected!\n\n"
        f"Your shop *{shop.name}* is now connected to Telegram notifications.\n\n"
        f"You will receive alerts here when suspicious activity is detected.",
        parse_mode="Markdown"
    )
    
    return {
        "success": True,
        "message": f"Shop '{shop.name}' connected to Telegram",
        "shop_id": str(shop.id),
        "shop_name": shop.name,
        "chat_id": chat_id
    }


@router.get(
    "/polling-instructions",
    summary="Get Polling Mode Setup Instructions",
    description="Instructions for setting up Telegram without webhooks"
)
async def get_polling_instructions():
    """
    Get instructions for manual Telegram setup using polling mode
    """
    from app.config import TELEGRAM_BOT_USERNAME
    
    return {
        "mode": "polling",
        "bot_username": TELEGRAM_BOT_USERNAME,
        "instructions": [
            "1. Open Telegram and search for @" + TELEGRAM_BOT_USERNAME,
            "2. Send /start or any message to the bot",
            "3. The bot will reply with your Chat ID",
            "4. Copy your Chat ID and paste it in the shop edit page",
            "5. Click 'Connect' to link your shop to Telegram notifications"
        ],
        "api_endpoint": "/telegram/connect-shop?shop_id=YOUR_SHOP_ID&chat_id=YOUR_CHAT_ID",
        "note": "The bot automatically replies with your Chat ID when you message it"
    }


@router.post(
    "/start-polling",
    summary="Start Telegram Bot Polling",
    description="Start the background task to poll for Telegram updates"
)
async def start_polling(background_tasks: BackgroundTasks):
    """
    Start the Telegram bot polling service
    This will continuously check for new messages and reply with chat IDs
    """
    global polling_active
    
    if polling_active:
        return {
            "status": "already_running",
            "message": "Polling is already active"
        }
    
    polling_active = True
    background_tasks.add_task(poll_telegram_updates)
    
    return {
        "status": "started",
        "message": "Bot polling started. Users will receive their Chat ID when they message the bot."
    }


async def poll_telegram_updates():
    """
    Background task that continuously polls Telegram for updates
    and replies to users with their chat ID
    """
    global last_update_id, polling_active
    telegram_service = get_telegram_service()
    
    logger.info("[Telegram Polling] Started polling for updates")
    logger.info(f"[Telegram Polling] polling_active = {polling_active}")
    
    while polling_active:
        try:
            # Get updates with offset to avoid duplicate processing
            updates = await telegram_service.get_updates(
                offset=last_update_id + 1 if last_update_id > 0 else None,
                timeout=30
            )
            
            if updates:
                logger.info(f"[Telegram Polling] Received {len(updates)} update(s)")
                
                for update in updates:
                    try:
                        update_id = update.get("update_id", 0)
                        message = update.get("message", {})
                        chat = message.get("chat", {})
                        chat_id = str(chat.get("id", ""))
                        text = message.get("text", "")
                        
                        # Update the last processed update ID
                        if update_id > last_update_id:
                            last_update_id = update_id
                        
                        # Reply to any message with the user's chat ID
                        if chat_id and text:
                            logger.info(f"[Telegram Polling] Received message from chat {chat_id}: {text}")
                            await telegram_service.reply_with_chat_id(chat_id)
                            logger.info(f"[Telegram Polling] Sent Chat ID to {chat_id}")
                    
                    except Exception as e:
                        logger.error(f"[Telegram Polling] Error processing update: {str(e)}")
            
            # Small delay between polling cycles
            await asyncio.sleep(1)
            
        except Exception as e:
            logger.error(f"[Telegram Polling] Polling error: {str(e)}")
            await asyncio.sleep(5)  # Wait longer on error
    
    logger.info("[Telegram Polling] Stopped polling")
