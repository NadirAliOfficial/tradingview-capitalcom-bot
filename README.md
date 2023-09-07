# TradingView → Capital.com Webhook Bot

Receives webhook alerts from TradingView and automatically executes trades on the Capital.com demo (or live) account.

---

## How it works

```
TradingView Alert
      │
      ▼  (HTTP POST JSON)
Webhook Server (this bot, running on your laptop)
      │
      ▼  (Capital.com REST API)
Capital.com Demo Account
```

1. Your Pine Script strategy fires an alert with a JSON payload.
2. The webhook server receives it and decides to open or close a position.
3. The order is sent to Capital.com via their REST API.

---

## Requirements

- Python 3.10+
- TradingView Premium (webhooks require at least Pro plan)
- Capital.com account with API access enabled
- [ngrok](https://ngrok.com/download) (to expose your laptop to the internet)

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure credentials

```bash
cp .env.example .env
```

Edit `.env` and fill in:

| Variable | Description |
|---|---|
| `CAPITAL_API_KEY` | Your Capital.com API key (Settings → API integrations) |
| `CAPITAL_IDENTIFIER` | Your Capital.com login email |
| `CAPITAL_PASSWORD` | Your Capital.com password |
| `CAPITAL_DEMO` | `true` for demo, `false` for live |
| `WEBHOOK_SECRET` | Any random string (e.g. `my-secret-2024`) |
| `POSITION_SIZE_PERCENT` | % of account equity per trade (default: 70) |
| `STOP_LOSS_PERCENT` | Stop loss % below entry price (default: 0.45) |

### 3. Enable Capital.com API access

1. Log in to Capital.com
2. Go to **Settings → API Integrations**
3. Create a new API key and copy it into your `.env`

### 4. Start the bot

```bash
python app.py
```

You should see:
```
Starting webhook server on port 5000 (demo=True)
```

### 5. Expose your laptop with ngrok

Download and install ngrok from https://ngrok.com/download, then run:

```bash
ngrok http 5000
```

ngrok will give you a public URL like:
```
https://abc123.ngrok-free.app
```

Your webhook URL will be:
```
https://abc123.ngrok-free.app/webhook?secret=YOUR_WEBHOOK_SECRET
```

> **Important:** Every time you restart ngrok, the URL changes. You will need to update the TradingView alert each time — unless you have a paid ngrok plan with a fixed domain.

---

## TradingView Alert Setup

### Step 1: Add alert in TradingView

1. Open your chart with the Gold RSI strategy loaded.
2. Click the **Alerts** clock icon → **Create Alert**.
3. Set **Condition** to your strategy name.
4. Set **Trigger** to **Once Per Bar Close** (recommended for 1-minute chart).

### Step 2: Configure the webhook

Under **Notifications**:
- Enable **Webhook URL**
- Enter your full webhook URL:
  ```
  https://abc123.ngrok-free.app/webhook?secret=YOUR_WEBHOOK_SECRET
  ```

### Step 3: Set the message body

The alert message must match the `alert_message` fields already in your Pine Script.
Your script already sends the correct JSON — leave the **Message** field as:
```
{{strategy.order.alert_message}}
```

This tells TradingView to use the `alert_message` you defined in `strategy.entry`, `strategy.exit`, and `strategy.close`.

---

## Pine Script Alert Messages (already in your script)

| Event | JSON sent to webhook |
|---|---|
| Buy signal | `{"action":"buy","symbol":"XAUUSD"}` |
| Stop loss hit | `{"action":"close","symbol":"XAUUSD"}` |
| Time-based close | `{"action":"close","symbol":"XAUUSD"}` |

---

## Symbol Mapping

TradingView uses `XAUUSD` for gold; Capital.com uses `GOLD`. The mapping is defined in `config.py` under `SYMBOL_MAP`. To add new instruments:

```python
SYMBOL_MAP = {
    "XAUUSD": "GOLD",
    "EURUSD": "EURUSD",
    # Add more here
}
```

---

## Switching from Demo to Live

1. Open `.env`
2. Change `CAPITAL_DEMO=true` to `CAPITAL_DEMO=false`
3. Restart the bot

No other changes needed.

---

## Logs

All activity is logged to `logs/bot.log` and printed to the terminal. Check this file if a trade is not executing as expected.

---

## Health Check

To verify the bot is running:

```bash
curl http://localhost:5000/health
```

Expected response:
```json
{"demo": true, "status": "running"}
```

---

## Daily Workflow

1. Start the bot: `python app.py`
2. Start ngrok: `ngrok http 5000`
3. Update the TradingView alert URL if ngrok URL changed
4. Keep both terminal windows open during trading hours (08:00–22:30 CET)
5. Stop both when done for the day

---

## File Structure

```
tradingview-capitalcom-bot/
├── app.py              # Webhook server (main entry point)
├── capital_client.py   # Capital.com API client
├── config.py           # Configuration loader
├── requirements.txt    # Python dependencies
├── .env.example        # Template for credentials
├── .env                # Your actual credentials (never commit this)
├── .gitignore
├── README.md
└── logs/
    └── bot.log         # Runtime logs
```
<!-- updated: 2023-09-07-r01 -->
