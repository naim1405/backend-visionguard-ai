# Telegram Bot Integration

## Overview

VisionGuard AI integrates with Telegram to send real-time anomaly detection notifications directly to shop managers via Telegram Bot. This provides an additional notification channel alongside the existing WebSocket-based frontend notifications.

## Features

- ✅ **Automatic Chat ID Reply** - Bot automatically replies with your Chat ID when you message it
- ✅ **Dual Notification System** - Notifications sent to both frontend (WebSocket) and Telegram
- ✅ **Per-Shop Configuration** - Each shop can independently connect to Telegram
- ✅ **Polling Mode** - Works without webhooks (no inbound connections needed)
- ✅ **Auto-Start** - Polling starts automatically when backend launches
- ✅ **Non-Breaking** - Existing notification system works unchanged for shops without Telegram

## Quick Setup

### 1. Backend Configuration

Add to your `.env` file:

```env
TELEGRAM_BOT_TOKEN=8315493205:AAHDfB8fWZQ_N9PMLk2QCchQ0OG6I2PiqPU
TELEGRAM_BOT_USERNAME=VisionGuardAIBot
```

### 2. Start Backend

```bash
cd backend-visionguard-ai
python main.py
```

Look for this log message:
```
✓ Telegram bot polling started
```

### 3. Get Your Chat ID

**Step 1:** Open Telegram and search for `@VisionGuardAIBot`

**Step 2:** Send `/start` or any message to the bot

**Step 3:** Bot will immediately reply with your Chat ID:
```
👋 Hello @username!

✅ Your Chat ID

123456789

📋 Copy this ID and paste it in VisionGuard AI to receive anomaly notifications.
```

### 4. Connect Your Shop

**Step 1:** Go to your shop's edit page in VisionGuard AI

**Step 2:** Click "Connect Telegram" button

**Step 3:** Paste your Chat ID in the modal

**Step 4:** Click "Connect"

**Step 5:** You'll receive a confirmation message in Telegram

Done! You'll now receive anomaly notifications in both the frontend and Telegram.

## Architecture

### Polling Mode (Active)

The system uses **polling mode** because you cannot accept inbound connections (no webhooks):

```
User → Telegram App → Message → Telegram API
                                      ↓
Backend ← Poll (every 30s) ← Telegram API
    ↓
Reply with Chat ID → Telegram API → User
```

**Polling Service:**
- Starts automatically when backend launches (in `main.py` lifespan)
- Continuously polls Telegram API every 30 seconds (long polling)
- When user sends ANY message, bot replies with their Chat ID
- Runs in background without blocking other operations
- Stops gracefully on shutdown

### Backend Components

1. **Database Schema** (`app/models/shop.py`)
   - Added `telegram_chat_id` field to `Shop` model
   - Nullable field, indexed for performance

2. **Telegram Service** (`app/services/telegram_service.py`)
   - `TelegramService` class for interacting with Telegram Bot API
   - Methods:
     - `send_message()`: Send text messages
     - `send_notification()`: Send formatted notifications
     - `send_anomaly_notification()`: Send anomaly alerts
     - `reply_with_chat_id()`: Reply to users with their Chat ID
     - `get_updates()`: Poll for new messages (long polling)
     - `get_chat_info()`: Validate chat ID exists

3. **Telegram API Router** (`app/api/telegram.py`)
   - `/telegram/connect-shop`: Manually connect shop with Chat ID
   - `/telegram/disconnect-shop/{shop_id}`: Disconnect shop from Telegram
   - `/telegram/polling-instructions`: Get setup instructions
   - `/telegram/start-polling`: Manually start polling (optional)
   - `poll_telegram_updates()`: Background task that polls for messages

4. **Main Application** (`main.py`)
   - Automatically starts polling on startup (in `lifespan` function)
   - Sets `polling_active = True` to enable polling loop
   - Stops polling gracefully on shutdown

4. **WebSocket Integration** (`app/api/websocket.py`)
   - Extended `WebSocketManager.send_message()` to also send Telegram notifications
   - New `_send_telegram_notification()` method
   - Automatically checks if shop has Telegram configured
   - Non-blocking: Frontend notifications always sent, Telegram is additional

5. **Configuration** (`app/config.py`)
   - `TELEGRAM_BOT_TOKEN`: Bot authentication token
   - `TELEGRAM_BOT_USERNAME`: Bot username
   - `TELEGRAM_API_BASE_URL`: API endpoint URL

6. **Shop API Updates** (`app/api/shops.py`)
   - Added `telegram_chat_id` to `ShopResponse` schema
   - Included in shop response builder

### Frontend Components

1. **Type Definitions** (`types/index.ts`)
   - Added `telegramChatId` field to `Shop` interface

2. **Shop Edit Page** (`app/shops/[id]/edit/page.tsx`)
   - New Telegram connection modal
   - Shows connection status (Connected/Not Connected)
   - "Connect Telegram" button opens modal
   - Modal with instructions and Chat ID input field
   - Visual indicators for active connections

## Bot Configuration

### Bot Details

- **Bot Username**: `@VisionGuardAIBot`
- **Bot Token**: `8315493205:AAHDfB8fWZQ_N9PMLk2QCchQ0OG6I2PiqPU`

### Environment Variables

Add to `.env` file:

```env
TELEGRAM_BOT_TOKEN=8315493205:AAHDfB8fWZQ_N9PMLk2QCchQ0OG6I2PiqPU
TELEGRAM_BOT_USERNAME=VisionGuardAIBot
```

## Usage Flow

### 1. Getting Chat ID from Bot

1. User opens Telegram
2. Searches for `@VisionGuardAIBot`
3. Sends `/start` or any message
4. Bot replies immediately with formatted Chat ID message
5. User copies the Chat ID

### 2. Connecting Shop to Telegram

1. Shop owner opens "Manage Shop" page in VisionGuard AI
2. Clicks "Connect Telegram" button
3. Modal opens with 3-step instructions
4. User pastes their Chat ID from Telegram
5. Clicks "Connect" button
6. Backend validates Chat ID with Telegram API
7. Backend saves `chat_id` to shop's `telegram_chat_id` field
8. Bot sends confirmation message to user in Telegram
9. Frontend shows "Connected" status

### 3. Receiving Notifications

When an anomaly is detected:

1. System creates anomaly record in database
2. `WebSocketManager.send_message()` is called with notification
3. Notification is sent to frontend via WebSocket
4. System checks if shop has `telegram_chat_id`
5. If yes, formats and sends notification to Telegram
6. Telegram notification includes:
   - Alert emoji based on priority
   - Notification title
   - Message content
   - Shop context

### 4. Disconnecting

Shop owner can disconnect by:
- Using the disconnect API endpoint: `POST /telegram/disconnect-shop/{shop_id}`
- This clears the `telegram_chat_id` field
- Future notifications will not be sent to Telegram

## API Endpoints

### Connect Shop to Telegram (Manual)

```
POST /telegram/connect-shop?shop_id={shop_id}&chat_id={chat_id}
```

Manually connect a shop using a Chat ID obtained from the bot.

**Parameters:**
- `shop_id` (string): Shop UUID
- `chat_id` (string): Telegram Chat ID from bot

**Response:**
```json
{
  "success": true,
  "message": "Shop 'My Shop' connected to Telegram",
  "shop_id": "abc123...",
  "shop_name": "My Shop",
  "chat_id": "123456789"
}
```

### Get Polling Instructions

```
GET /telegram/polling-instructions
```

Returns setup instructions and bot details.

**Response:**
```json
{
  "mode": "polling",
  "bot_username": "@VisionGuardAIBot",
  "instructions": [
    "1. Open Telegram and search for @VisionGuardAIBot",
    "2. Send /start or any message to the bot",
    "3. The bot will reply with your Chat ID",
    "4. Copy your Chat ID and paste it in the shop edit page",
    "5. Click 'Connect' to link your shop to Telegram notifications"
  ]
}
```

### Start Polling (Manual)

```
POST /telegram/start-polling
```

Manually start the polling service (normally starts automatically on backend launch).

### Disconnect Shop

```
POST /telegram/disconnect-shop/{shop_id}
```

Remove Telegram connection from a shop.

## Notification Format

Telegram notifications are formatted with Markdown:

```
🚨 *Alert Title*

Message content goes here.

Priority indicators:
ℹ️ - Low priority
⚠️ - Medium priority
🔔 - High priority
🚨 - Critical priority
```

## Security Considerations

1. **Validation**: Shop ID from Telegram is validated before updating database
2. **Authorization**: Only valid Telegram chat IDs from bot interactions are stored
3. **Error Handling**: Failed Telegram sends don't affect frontend notifications
4. **Logging**: All Telegram operations are logged for audit

## Testing

### 1. Test Bot Response

1. Open Telegram
2. Search for `@VisionGuardAIBot`
3. Send `/start` or "hello"
4. Bot should reply within 1-2 seconds with your Chat ID

### 2. Test Manual Connection

```bash
# Replace with your actual shop ID and chat ID
curl -X POST "http://localhost:8000/telegram/connect-shop?shop_id=YOUR_SHOP_ID&chat_id=YOUR_CHAT_ID"
```

### 3. Test Notification Flow

1. Connect a shop to Telegram
2. Trigger an anomaly alert (e.g., Owl Eye detection in live feed)
3. Verify notification appears in:
   - ✅ Frontend (WebSocket notification)
   - ✅ Telegram (Bot message)

### 4. Check Polling Status

Look for these log messages in backend:
```
✓ Telegram bot polling started
[Telegram Polling] Started polling for updates
[Telegram Polling] polling_active = True
```

When you send a message:
```
[Telegram Polling] Received 1 update(s)
[Telegram Polling] Received message from chat 123456789: /start
[Telegram Polling] Sent Chat ID to 123456789
```

## Troubleshooting

### Bot Not Responding

**Problem:** You message the bot but don't get a reply

**Solutions:**
1. Check backend logs for `✓ Telegram bot polling started`
2. Look for polling errors: `grep "Telegram Polling" logs`
3. Verify `TELEGRAM_BOT_TOKEN` is correct in `.env`
4. Restart backend: `python main.py`
5. Check internet connectivity (bot needs to reach `api.telegram.org`)

**Alternative:** Run standalone polling script:
```bash
cd backend-visionguard-ai
python telegram_polling.py
```

### Connection Failed

**Problem:** "Failed to connect" error when clicking Connect in frontend

**Solutions:**
1. Verify you've messaged the bot first (get your Chat ID)
2. Double-check Chat ID is correct (numbers only, no spaces)
3. Make sure you copied the full ID from bot's reply
4. Check backend logs for validation errors
5. Test the API directly:
   ```bash
   curl "http://localhost:8000/telegram/connect-shop?shop_id=SHOP_ID&chat_id=CHAT_ID"
   ```

### Not Receiving Notifications

**Problem:** Shop is connected but no Telegram notifications arrive

**Solutions:**
1. Verify `telegram_chat_id` is set in database:
   ```sql
   SELECT id, name, telegram_chat_id FROM shops WHERE id = 'your-shop-id';
   ```
2. Check backend logs when anomaly is detected
3. Look for errors: `grep "Telegram" logs`
4. Verify anomaly detection is working (check frontend notifications)
5. Test by triggering manual notification

### Polling Not Starting

**Problem:** Backend starts but no polling log messages

**Solutions:**
1. Check for import errors in logs
2. Verify `app/api/telegram.py` has no syntax errors
3. Check if `httpx` is installed: `pip install httpx`
4. Look for exception in startup: `grep "Failed to start Telegram polling" logs`
5. Try manual start: `curl -X POST http://localhost:8000/telegram/start-polling`

## Database Migration

The migration adds the `telegram_chat_id` column:

```sql
ALTER TABLE shops ADD COLUMN telegram_chat_id VARCHAR(255);
CREATE INDEX ix_shops_telegram_chat_id ON shops (telegram_chat_id);
```

Run migration:

```bash
cd backend-visionguard-ai
alembic upgrade head
```

## Future Enhancements

Potential improvements:

1. **Telegram Bot Commands**:
   - `/status` - Get shop status
   - `/mute` - Temporarily disable notifications
   - `/unmute` - Re-enable notifications

2. **Rich Notifications**:
   - Send images with anomaly alerts
   - Inline buttons for quick actions
   - Location sharing for shop address

3. **Multi-Language Support**:
   - Detect user language
   - Send notifications in user's language

4. **Notification Preferences**:
   - Configure which alert types to receive
   - Set quiet hours
   - Custom alert thresholds

5. **Group Chat Support**:
   - Allow shops to connect to Telegram groups
   - Multiple users receive notifications

## References

- [Telegram Bot API Documentation](https://core.telegram.org/bots/api)
- [Telegram Deep Linking](https://core.telegram.org/bots/features#deep-linking)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
