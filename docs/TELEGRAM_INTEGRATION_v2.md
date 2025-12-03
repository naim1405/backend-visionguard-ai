# Telegram Bot Integration

## Overview

VisionGuard AI integrates with Telegram to send real-time anomaly detection notifications directly to shop managers via Telegram Bot. This provides an additional notification channel alongside the existing WebSocket-based frontend notifications.

**Key Features:**
- ✅ **Automatic Chat ID Detection** - Bot replies with your Chat ID when you message it
- ✅ **Dual Notification System** - WebSocket (frontend) + Telegram (bot)
- ✅ **Non-Breaking Integration** - Existing notifications unchanged
- ✅ **Per-Shop Configuration** - Each shop can connect its own Telegram chat
- ✅ **Outbound-Only** - Works without incoming connections (polling mode)

## Quick Setup

### 1. Backend Configuration

Add to your `.env` file:

```env
TELEGRAM_BOT_TOKEN=8315493205:AAHDfB8fWZQ_N9PMLk2QCchQ0OG6I2PiqPU
TELEGRAM_BOT_USERNAME=@VisionGuardAIBot
```

### 2. Connect Your Shop to Telegram

**Step 1:** Open Telegram and search for `@VisionGuardAIBot`

**Step 2:** Send `/start` or any message to the bot

**Step 3:** The bot will reply with your Chat ID (e.g., `123456789`)

**Step 4:** Go to your shop's edit page in VisionGuard AI

**Step 5:** Click "Connect Telegram" and paste your Chat ID

**Step 6:** Click "Connect" - you'll receive a confirmation message in Telegram

Done! You'll now receive anomaly notifications in both the frontend and Telegram.

## How It Works

### Architecture

The system uses **polling mode** instead of webhooks because you cannot accept inbound connections:

```
User → Telegram → Bot API → Polling (Backend) → Reply with Chat ID
                                ↓
                         Store in Database
                                ↓
Anomaly Detected → Send to WebSocket + Telegram
```

### Polling Service

The backend automatically starts a polling service on startup that:
1. Continuously checks for new messages (long polling, 30s timeout)
2. When a user sends any message, replies with their Chat ID
3. Runs in the background without blocking other operations

### Database Schema

Added `telegram_chat_id` field to `Shop` model:

```python
telegram_chat_id = Column(String(255), nullable=True, index=True)
```

### Notification Flow

When an anomaly is detected:

1. **WebSocket Notification** (always sent, unchanged)
   ```python
   await manager.send_message(shop_id, notification_data)
   ```

2. **Telegram Notification** (sent if connected)
   ```python
   if shop.telegram_chat_id:
       await telegram_service.send_anomaly_notification(...)
   ```

## API Endpoints

### Connect Shop to Telegram

```http
POST /telegram/connect-shop?shop_id={shop_id}&chat_id={chat_id}
```

**Parameters:**
- `shop_id` (string): Shop UUID
- `chat_id` (string): Telegram Chat ID from the bot

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

```http
GET /telegram/polling-instructions
```

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
  ],
  "api_endpoint": "/telegram/connect-shop?shop_id=YOUR_SHOP_ID&chat_id=YOUR_CHAT_ID",
  "note": "The bot automatically replies with your Chat ID when you message it"
}
```

### Disconnect Shop from Telegram

```http
POST /telegram/disconnect-shop/{shop_id}
```

## Frontend Integration

### Shop Edit Page

The shop edit page includes a Telegram connection modal:

```typescript
// State management
const [showTelegramModal, setShowTelegramModal] = useState(false)
const [telegramChatId, setTelegramChatId] = useState('')
const [connectingTelegram, setConnectingTelegram] = useState(false)
const [telegramError, setTelegramError] = useState('')

// Connection handler
const handleConnectTelegram = async () => {
  if (!telegramChatId.trim()) {
    setTelegramError('Please enter your Chat ID')
    return
  }

  setConnectingTelegram(true)
  setTelegramError('')

  try {
    const response = await axios.post(
      `/telegram/connect-shop?shop_id=${shop.id}&chat_id=${telegramChatId}`
    )
    
    if (response.data.success) {
      // Update shop data
      setShowTelegramModal(false)
      // Refresh shop data to show connected status
    }
  } catch (error) {
    setTelegramError('Failed to connect. Please check your Chat ID.')
  } finally {
    setConnectingTelegram(false)
  }
}
```

### Modal UI

The modal provides:
- Clear 3-step instructions
- Input field for Chat ID
- Error handling and validation
- Loading states during connection
- Success confirmation

## Testing

### 1. Test Bot Response

```bash
# Message your bot in Telegram
# You should receive a reply with your Chat ID
```

### 2. Test Connection

```bash
curl -X POST "http://localhost:8000/telegram/connect-shop?shop_id=YOUR_SHOP_ID&chat_id=YOUR_CHAT_ID"
```

### 3. Test Notification

Trigger an anomaly detection and verify you receive notifications in:
- ✅ Frontend (WebSocket)
- ✅ Telegram (Bot message)

## Troubleshooting

### Bot Not Responding

**Problem:** You message the bot but don't get a reply

**Solutions:**
1. Check backend logs for polling errors
2. Verify `TELEGRAM_BOT_TOKEN` is correct in `.env`
3. Restart the backend to reinitialize polling
4. Check that polling service started (look for "✓ Telegram bot polling started" in logs)

### Connection Failed

**Problem:** "Failed to connect" error when clicking Connect

**Solutions:**
1. Verify you've messaged the bot first
2. Double-check the Chat ID (should be numbers only)
3. Make sure you copied the full Chat ID from the bot's reply
4. Check backend logs for API errors

### Not Receiving Notifications

**Problem:** Shop is connected but no Telegram notifications arrive

**Solutions:**
1. Verify `shop.telegram_chat_id` is set in database:
   ```sql
   SELECT id, name, telegram_chat_id FROM shops WHERE id = 'your-shop-id';
   ```
2. Check that anomaly notifications are being sent (check backend logs)
3. Verify Telegram API is accessible (no firewall blocking)
4. Test with manual message: `/telegram/connect-shop` endpoint

## Code Structure

### Backend Files

- `app/models/shop.py` - Shop model with `telegram_chat_id` field
- `app/services/telegram_service.py` - Telegram Bot API client
- `app/api/telegram.py` - Telegram REST endpoints and polling logic
- `app/api/websocket.py` - Extended to send Telegram notifications
- `alembic/versions/*_add_telegram_chat_id.py` - Database migration
- `main.py` - Starts polling on application startup

### Frontend Files

- `types/index.ts` - Shop interface with `telegramChatId`
- `app/shops/[id]/edit/page.tsx` - Telegram connection UI and modal
- `lib/services/shopService.ts` - Shop API calls

## Security Considerations

1. **Bot Token Protection**
   - Never commit `.env` to version control
   - Use environment variables in production
   - Rotate token if compromised

2. **Chat ID Validation**
   - Backend validates Chat ID with Telegram API before saving
   - Uses `getChat` endpoint to verify validity

3. **Shop Access Control**
   - Only authenticated shop managers can connect Telegram
   - JWT tokens required for API calls
   - Shop ownership verified before connection

## Why Polling Instead of Webhooks?

Webhooks require:
- ✅ Public URL accessible from internet
- ✅ HTTPS with valid SSL certificate  
- ✅ Server that accepts inbound connections

Your constraint: **"i will not host my backend, so i cant accept inbound connection"**

Polling mode:
- ✅ Only requires outbound connections
- ✅ Works behind NAT/firewall
- ✅ No SSL certificate needed
- ✅ Simpler deployment

The bot only needs to **send** notifications (outbound), so polling is perfect for this use case.

## Notification Message Format

```markdown
🚨 *Anomaly Detected*

*Shop:* Downtown Store
*Type:* Suspicious Behavior
*Confidence:* 89.5%
*Time:* 2025-12-03 14:32:15

Please review the suspicious activity immediately.
```

## Future Enhancements

Potential improvements (not yet implemented):

- [ ] Rich media notifications (send anomaly frame images)
- [ ] Interactive buttons (acknowledge, dismiss, view details)
- [ ] Multiple chat support (group chats, channels)
- [ ] Notification preferences (severity filters)
- [ ] Daily/weekly summaries
- [ ] Bot commands (/status, /stats, /help)

---

**Integration Complete!** 🎉

Users can now receive anomaly notifications via Telegram without any code changes to the existing notification system.
