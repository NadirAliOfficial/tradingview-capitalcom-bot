"""
TradingView -> Capital.com webhook bridge.

Receives JSON alerts from TradingView and executes trades on Capital.com.

Expected alert payload format (set in TradingView alert_message):
    {"action": "buy",   "symbol": "XAUUSD"}
    {"action": "close", "symbol": "XAUUSD"}
"""

import logging
import os
import requests
from flask import Flask, request, jsonify

import config
from capital_client import CapitalClient

# ------------------------------------------------------------------
# Logging setup
# ------------------------------------------------------------------
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# App + client
# ------------------------------------------------------------------
app = Flask(__name__)
client = CapitalClient()


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def capital_error_message(exc):
    """Extract clean error message from a Capital.com HTTPError."""
    try:
        return exc.response.json().get("errorCode", str(exc))
    except Exception:
        return str(exc)


# ------------------------------------------------------------------
# Webhook endpoint
# ------------------------------------------------------------------

@app.route("/webhook", methods=["POST"])
def webhook():
    # Security check
    secret = request.args.get("secret", "")
    if config.WEBHOOK_SECRET and secret != config.WEBHOOK_SECRET:
        logger.warning("Unauthorized request — wrong secret")
        return jsonify({"error": "Unauthorized"}), 401

    # Parse payload
    data = request.get_json(silent=True)
    if not data:
        logger.warning("Invalid or empty JSON payload")
        return jsonify({"error": "Invalid JSON"}), 400

    action = data.get("action", "").lower()
    tv_symbol = data.get("symbol", "").upper()

    if not action or not tv_symbol:
        logger.warning("Missing 'action' or 'symbol' in payload: %s", data)
        return jsonify({"error": "Missing 'action' or 'symbol'"}), 400

    epic = config.SYMBOL_MAP.get(tv_symbol)
    if not epic:
        logger.error("Unknown symbol '%s' — add it to SYMBOL_MAP in config.py", tv_symbol)
        return jsonify({"error": f"Unknown symbol: {tv_symbol}"}), 400

    logger.info("── Alert received: action=%s  symbol=%s  epic=%s", action, tv_symbol, epic)

    try:
        if action == "buy":
            return handle_buy(epic)
        elif action == "sell":
            return handle_sell(epic)
        elif action == "close":
            return handle_close(epic)
        else:
            logger.warning("Unknown action: %s", action)
            return jsonify({"error": f"Unknown action: {action}"}), 400

    except requests.exceptions.HTTPError as exc:
        msg = capital_error_message(exc)
        logger.error("Capital.com rejected the request: %s", msg)
        return jsonify({"error": msg}), 502

    except requests.exceptions.ConnectionError:
        logger.error("Cannot reach Capital.com — check internet connection")
        return jsonify({"error": "Connection failed"}), 503

    except Exception as exc:
        logger.exception("Unexpected error: %s", exc)
        return jsonify({"error": str(exc)}), 500


# ------------------------------------------------------------------
# Action handlers
# ------------------------------------------------------------------

def handle_buy(epic):
    existing = client.get_position_by_epic(epic)
    if existing:
        deal_id = existing["position"]["dealId"]
        logger.info("BUY skipped — position already open (dealId=%s)", deal_id)
        return jsonify({"status": "skipped", "reason": "position already open", "dealId": deal_id})

    prices = client.get_market_price(epic)
    offer_price = prices["offer"]
    sl_percent = config.STOP_LOSS_PERCENT / 100
    stop_level = round(offer_price * (1 - sl_percent), 2)
    size = client.calculate_size(epic, offer_price)

    result = client.open_position(epic=epic, direction="BUY", size=size, stop_level=stop_level)
    deal_ref = result.get("dealReference", "N/A")
    logger.info("BUY executed — epic=%s  size=%s  price=%s  SL=%s  ref=%s",
                epic, size, offer_price, stop_level, deal_ref)
    return jsonify({"status": "ok", "action": "buy", "epic": epic,
                    "size": size, "price": offer_price, "stopLevel": stop_level,
                    "dealReference": deal_ref})


def handle_sell(epic):
    existing = client.get_position_by_epic(epic)
    if existing:
        deal_id = existing["position"]["dealId"]
        logger.info("SELL skipped — position already open (dealId=%s)", deal_id)
        return jsonify({"status": "skipped", "reason": "position already open", "dealId": deal_id})

    prices = client.get_market_price(epic)
    bid_price = prices["bid"]
    sl_percent = config.STOP_LOSS_PERCENT / 100
    stop_level = round(bid_price * (1 + sl_percent), 2)
    size = client.calculate_size(epic, bid_price)

    result = client.open_position(epic=epic, direction="SELL", size=size, stop_level=stop_level)
    deal_ref = result.get("dealReference", "N/A")
    logger.info("SELL executed — epic=%s  size=%s  price=%s  SL=%s  ref=%s",
                epic, size, bid_price, stop_level, deal_ref)
    return jsonify({"status": "ok", "action": "sell", "epic": epic,
                    "size": size, "price": bid_price, "stopLevel": stop_level,
                    "dealReference": deal_ref})


def handle_close(epic):
    position = client.get_position_by_epic(epic)
    if not position:
        logger.info("CLOSE skipped — no open position for %s", epic)
        return jsonify({"status": "skipped", "reason": "no open position", "epic": epic})

    deal_id = position["position"]["dealId"]
    client.close_position(deal_id)
    logger.info("CLOSE executed — epic=%s  dealId=%s", epic, deal_id)
    return jsonify({"status": "ok", "action": "close", "epic": epic, "dealId": deal_id})


# ------------------------------------------------------------------
# Health check
# ------------------------------------------------------------------

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "running", "demo": config.CAPITAL_DEMO})


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

if __name__ == "__main__":
    config.validate()
    logger.info("Starting webhook server on port %d (demo=%s)", config.PORT, config.CAPITAL_DEMO)
    from waitress import serve
    serve(app, host="0.0.0.0", port=config.PORT)
