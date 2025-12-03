"""
Telegram Bot Service
Handles Telegram bot operations including webhook handling and message sending
"""

import logging
import httpx
from typing import Optional, Dict, Any, List
from app.config import TELEGRAM_API_BASE_URL, TELEGRAM_BOT_TOKEN

# Configure logging
logger = logging.getLogger(__name__)


class TelegramService:
    """Service for interacting with Telegram Bot API"""
    
    def __init__(self):
        self.api_base_url = TELEGRAM_API_BASE_URL
        self.bot_token = TELEGRAM_BOT_TOKEN
    
    async def send_message(
        self,
        chat_id: str,
        text: str,
        parse_mode: Optional[str] = None
    ) -> bool:
        """
        Send a text message to a Telegram chat
        
        Args:
            chat_id: Telegram chat ID to send message to
            text: Message text to send
            parse_mode: Optional parse mode (Markdown, HTML, etc.)
            
        Returns:
            bool: True if message sent successfully, False otherwise
        """
        try:
            url = f"{self.api_base_url}/sendMessage"
            
            payload = {
                "chat_id": chat_id,
                "text": text
            }
            
            if parse_mode:
                payload["parse_mode"] = parse_mode
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=payload)
                
                if response.status_code == 200:
                    logger.info(f"[Telegram] Message sent successfully to chat {chat_id}")
                    return True
                else:
                    logger.error(
                        f"[Telegram] Failed to send message to chat {chat_id}. "
                        f"Status: {response.status_code}, Response: {response.text}"
                    )
                    return False
                    
        except httpx.TimeoutException:
            logger.error(f"[Telegram] Timeout sending message to chat {chat_id}")
            return False
        except Exception as e:
            logger.error(f"[Telegram] Error sending message to chat {chat_id}: {e}")
            return False
    
    async def send_anomaly_notification(
        self,
        chat_id: str,
        shop_name: str,
        detection_type: str,
        confidence: float,
        timestamp: str
    ) -> bool:
        """
        Send an anomaly detection notification to Telegram
        
        Args:
            chat_id: Telegram chat ID
            shop_name: Name of the shop where anomaly was detected
            detection_type: Type of anomaly detected
            confidence: Confidence score of detection
            timestamp: Timestamp of detection
            
        Returns:
            bool: True if sent successfully, False otherwise
        """
        message = (
            f"🚨 *Anomaly Detected*\n\n"
            f"*Shop:* {shop_name}\n"
            f"*Type:* {detection_type}\n"
            f"*Confidence:* {confidence:.1%}\n"
            f"*Time:* {timestamp}\n\n"
            f"Please review the suspicious activity immediately."
        )
        
        return await self.send_message(chat_id, message, parse_mode="Markdown")
    
    async def send_notification(
        self,
        chat_id: str,
        title: str,
        message: str,
        priority: str = "medium"
    ) -> bool:
        """
        Send a general notification to Telegram
        
        Args:
            chat_id: Telegram chat ID
            title: Notification title
            message: Notification message
            priority: Priority level (low, medium, high, critical)
            
        Returns:
            bool: True if sent successfully, False otherwise
        """
        # Map priority to emoji
        priority_emoji = {
            "low": "ℹ️",
            "medium": "⚠️",
            "high": "🔔",
            "critical": "🚨"
        }
        
        emoji = priority_emoji.get(priority.lower(), "📢")
        
        formatted_message = f"{emoji} *{title}*\n\n{message}"
        
        return await self.send_message(chat_id, formatted_message, parse_mode="Markdown")
    
    async def set_webhook(self, webhook_url: str) -> bool:
        """
        Set the webhook URL for the bot
        
        Args:
            webhook_url: URL where Telegram will send updates
            
        Returns:
            bool: True if webhook set successfully, False otherwise
        """
        try:
            url = f"{self.api_base_url}/setWebhook"
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json={"url": webhook_url})
                
                if response.status_code == 200:
                    logger.info(f"[Telegram] Webhook set successfully to {webhook_url}")
                    return True
                else:
                    logger.error(
                        f"[Telegram] Failed to set webhook. "
                        f"Status: {response.status_code}, Response: {response.text}"
                    )
                    return False
                    
        except Exception as e:
            logger.error(f"[Telegram] Error setting webhook: {e}")
            return False
    
    async def delete_webhook(self) -> bool:
        """
        Delete the current webhook
        
        Returns:
            bool: True if webhook deleted successfully, False otherwise
        """
        try:
            url = f"{self.api_base_url}/deleteWebhook"
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url)
                
                if response.status_code == 200:
                    logger.info("[Telegram] Webhook deleted successfully")
                    return True
                else:
                    logger.error(
                        f"[Telegram] Failed to delete webhook. "
                        f"Status: {response.status_code}, Response: {response.text}"
                    )
                    return False
                    
        except Exception as e:
            logger.error(f"[Telegram] Error deleting webhook: {e}")
            return False
    
    async def get_webhook_info(self) -> Optional[Dict[str, Any]]:
        """
        Get current webhook information
        
        Returns:
            Dict with webhook info or None if request failed
        """
        try:
            url = f"{self.api_base_url}/getWebhookInfo"
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get("result")
                else:
                    logger.error(
                        f"[Telegram] Failed to get webhook info. "
                        f"Status: {response.status_code}"
                    )
                    return None
                    
        except Exception as e:
            logger.error(f"[Telegram] Error getting webhook info: {e}")
            return None
    
    async def get_updates(self, offset: Optional[int] = None, timeout: int = 30) -> Optional[List[Dict[str, Any]]]:
        """
        Get updates using long polling (for environments without webhook support)
        
        Args:
            offset: Identifier of the first update to be returned
            timeout: Timeout in seconds for long polling
            
        Returns:
            List of updates or None if request failed
        """
        try:
            url = f"{self.api_base_url}/getUpdates"
            
            params = {"timeout": timeout}
            if offset is not None:
                params["offset"] = offset
            
            async with httpx.AsyncClient(timeout=timeout + 10.0) as client:
                response = await client.get(url, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get("result", [])
                else:
                    logger.error(
                        f"[Telegram] Failed to get updates. "
                        f"Status: {response.status_code}"
                    )
                    return None
                    
        except Exception as e:
            logger.error(f"[Telegram] Error getting updates: {e}")
            return None
    
    async def get_chat_info(self, chat_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a chat
        
        Args:
            chat_id: Telegram chat ID
            
        Returns:
            Dict with chat info or None if request failed
        """
        try:
            url = f"{self.api_base_url}/getChat"
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json={"chat_id": chat_id})
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get("result")
                else:
                    logger.error(
                        f"[Telegram] Failed to get chat info. "
                        f"Status: {response.status_code}"
                    )
                    return None
                    
        except Exception as e:
            logger.error(f"[Telegram] Error getting chat info: {e}")
            return None
    
    async def reply_with_chat_id(self, chat_id: str) -> bool:
        """
        Send a message to the user with their chat ID
        
        Args:
            chat_id: The Telegram chat ID to send the message to
            
        Returns:
            bool: True if successful, False otherwise
        """
        message = (
            f"✅ *Your Chat ID*\n\n"
            f"`{chat_id}`\n\n"
            f"Copy this ID and paste it in VisionGuard AI to receive anomaly notifications."
        )
        
        return await self.send_message(chat_id, message, parse_mode="Markdown")


# Singleton instance
_telegram_service: Optional[TelegramService] = None


def get_telegram_service() -> TelegramService:
    """
    Get or create the Telegram service singleton
    
    Returns:
        TelegramService instance
    """
    global _telegram_service
    if _telegram_service is None:
        _telegram_service = TelegramService()
    return _telegram_service
