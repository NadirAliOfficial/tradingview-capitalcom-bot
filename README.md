# TradingView → Capital.com Webhook Bot

Receives TradingView webhook alerts and automatically executes trades on Capital.com (demo or live account).

![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=flat&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-000000?style=flat&logo=flask&logoColor=white)

## How It Works

1. TradingView sends a webhook `POST` to your server when an alert fires
2. Flask app receives and parses the JSON payload
3. Capital.com API places the order (market buy/sell)

## Webhook Payload Format

Configure your TradingView alert message as:

```json
{
  "action": "buy",
  "symbol": "EURUSD",
  "size": 1
}
```

| Field    | Values              | Description              |
|----------|---------------------|--------------------------|
| `action` | `"buy"` / `"sell"`  | Trade direction          |
| `symbol` | e.g. `"EURUSD"`     | Capital.com market name  |
| `size`   | number              | Position size (lots)     |

## Setup

```bash
pip install flask requests python-dotenv
```

Create `.env`:

```env
CAPITAL_API_KEY=your_api_key
CAPITAL_PASSWORD=your_password
CAPITAL_IDENTIFIER=your_email
DEMO=true
```

Run the server:

```bash
python app.py
```

Point your TradingView webhook to `http://your-server:5000/webhook`.

## Files

| File                | Purpose                          |
|---------------------|----------------------------------|
| `app.py`            | Flask webhook server             |
| `capital_client.py` | Capital.com REST API wrapper     |
| `config.py`         | Environment config loader        |
| `generate_guide.py` | Generates a trading setup guide  |

## License

MIT


