import os
from dotenv import load_dotenv

load_dotenv()

CAPITAL_API_KEY = os.getenv("CAPITAL_API_KEY", "")
CAPITAL_IDENTIFIER = os.getenv("CAPITAL_IDENTIFIER", "")
CAPITAL_PASSWORD = os.getenv("CAPITAL_PASSWORD", "")
CAPITAL_DEMO = os.getenv("CAPITAL_DEMO", "true").lower() == "true"

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
PORT = int(os.getenv("PORT", 5000))

POSITION_SIZE_PERCENT = float(os.getenv("POSITION_SIZE_PERCENT", "70"))
STOP_LOSS_PERCENT = float(os.getenv("STOP_LOSS_PERCENT", "0.45"))

# Base URLs
DEMO_BASE_URL = "https://demo-api-capital.backend.gbst.com/api/v1"
LIVE_BASE_URL = "https://api-capital.backend.gbst.com/api/v1"
BASE_URL = DEMO_BASE_URL if CAPITAL_DEMO else LIVE_BASE_URL

# TradingView symbol -> Capital.com epic mapping
SYMBOL_MAP = {
    "XAUUSD": "GOLD",
    "GOLD": "GOLD",
    "EURUSD": "EURUSD",
    "GBPUSD": "GBPUSD",
    "USDJPY": "USDJPY",
    "BTCUSD": "BITCOIN",
    "ETHUSD": "ETHEREUM",
    "US500": "US500",
    "NAS100": "NDAQ",
}


def validate():
    missing = []
    if not CAPITAL_API_KEY:
        missing.append("CAPITAL_API_KEY")
    if not CAPITAL_IDENTIFIER:
        missing.append("CAPITAL_IDENTIFIER")
    if not CAPITAL_PASSWORD:
        missing.append("CAPITAL_PASSWORD")
    if not WEBHOOK_SECRET:
        missing.append("WEBHOOK_SECRET")
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}. "
            "Please copy .env.example to .env and fill in your credentials."
        )
