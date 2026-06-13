"""
Capital.com REST API client.
Handles session management, position opening/closing, and account info.
"""

import logging
import time
import requests
import config

logger = logging.getLogger(__name__)


class CapitalClient:
    def __init__(self):
        self.session_cst = None
        self.session_token = None
        self.session_expiry = 0  # epoch seconds

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def _auth_headers(self):
        return {
            "X-CAP-API-KEY": config.CAPITAL_API_KEY,
            "CST": self.session_cst,
            "X-SECURITY-TOKEN": self.session_token,
            "Content-Type": "application/json",
        }

    def _base_headers(self):
        return {
            "X-CAP-API-KEY": config.CAPITAL_API_KEY,
            "Content-Type": "application/json",
        }

    def create_session(self):
        """Create a new Capital.com session and store CST + security token."""
        url = f"{config.BASE_URL}/session"
        payload = {
            "identifier": config.CAPITAL_IDENTIFIER,
            "password": config.CAPITAL_PASSWORD,
        }
        response = requests.post(url, json=payload, headers=self._base_headers(), timeout=10)
        response.raise_for_status()

        self.session_cst = response.headers.get("CST")
        self.session_token = response.headers.get("X-SECURITY-TOKEN")
        # Sessions are valid for 10 minutes of inactivity; refresh every 9 min
        self.session_expiry = time.time() + 9 * 60
        logger.info("Capital.com session created (demo=%s)", config.CAPITAL_DEMO)

    def _ensure_session(self):
        """Create or refresh session if expired."""
        if not self.session_cst or time.time() >= self.session_expiry:
            self.create_session()

    # ------------------------------------------------------------------
    # Account
    # ------------------------------------------------------------------

    def get_account_balance(self):
        """Return available balance in account currency."""
        self._ensure_session()
        url = f"{config.BASE_URL}/accounts"
        response = requests.get(url, headers=self._auth_headers(), timeout=10)
        response.raise_for_status()
        accounts = response.json().get("accounts", [])
        if not accounts:
            raise RuntimeError("No accounts found on Capital.com")
        balance = accounts[0]["balance"]["available"]
        logger.debug("Account balance: %s", balance)
        return float(balance)

    # ------------------------------------------------------------------
    # Market info
    # ------------------------------------------------------------------

    def get_market_price(self, epic):
        """Return the current bid/offer price for an epic."""
        self._ensure_session()
        url = f"{config.BASE_URL}/markets/{epic}"
        response = requests.get(url, headers=self._auth_headers(), timeout=10)
        response.raise_for_status()
        snapshot = response.json()["snapshot"]
        return {
            "bid": float(snapshot["bid"]),
            "offer": float(snapshot["offer"]),
            "mid": (float(snapshot["bid"]) + float(snapshot["offer"])) / 2,
        }

    def get_market_info(self, epic):
        """Return dealingRules and instrument info for an epic."""
        self._ensure_session()
        url = f"{config.BASE_URL}/markets/{epic}"
        response = requests.get(url, headers=self._auth_headers(), timeout=10)
        response.raise_for_status()
        return response.json()

    def get_min_deal_size(self, epic):
        """Return the minimum deal size for an instrument."""
        info = self.get_market_info(epic)
        min_size = info.get("dealingRules", {}).get("minDealSize", {}).get("value", 0.1)
        return float(min_size)

    def get_margin_factor(self, epic):
        """Return the margin factor percentage (e.g. 5.0 means 5% margin = 1:20 leverage)."""
        info = self.get_market_info(epic)
        instrument = info.get("instrument", {})
        margin_factor = instrument.get("marginFactor", 100)
        unit = instrument.get("marginFactorUnit", "PERCENTAGE")
        if unit == "PERCENTAGE":
            return float(margin_factor)
        # fallback: no leverage
        return 100.0

    # ------------------------------------------------------------------
    # Positions
    # ------------------------------------------------------------------

    def get_open_positions(self):
        """Return list of all open positions."""
        self._ensure_session()
        url = f"{config.BASE_URL}/positions"
        response = requests.get(url, headers=self._auth_headers(), timeout=10)
        response.raise_for_status()
        return response.json().get("positions", [])

    def get_position_by_epic(self, epic):
        """Return the first open position for a given epic, or None."""
        positions = self.get_open_positions()
        for pos in positions:
            if pos.get("market", {}).get("epic") == epic:
                return pos
        return None

    def open_position(self, epic, direction, size, stop_level=None):
        """
        Open a new position.

        Args:
            epic (str): Capital.com instrument epic (e.g. "GOLD")
            direction (str): "BUY" or "SELL"
            size (float): Deal size in lots/units
            stop_level (float): Absolute price level for stop loss

        Returns:
            dict: API response with dealReference
        """
        self._ensure_session()
        url = f"{config.BASE_URL}/positions"
        payload = {
            "epic": epic,
            "direction": direction,
            "size": size,
            "guaranteedStop": False,
        }
        if stop_level is not None:
            payload["stopLevel"] = round(stop_level, 2)

        logger.info(
            "Opening position: epic=%s direction=%s size=%s stop=%s",
            epic, direction, size, stop_level,
        )
        response = requests.post(url, json=payload, headers=self._auth_headers(), timeout=10)
        if not response.ok:
            logger.error("Position error %s: %s", response.status_code, response.text)
        response.raise_for_status()
        return response.json()

    def close_position(self, deal_id):
        """
        Close a position by deal ID.

        Args:
            deal_id (str): The dealId of the position to close

        Returns:
            dict: API response
        """
        self._ensure_session()
        url = f"{config.BASE_URL}/positions/{deal_id}"
        logger.info("Closing position: dealId=%s", deal_id)
        response = requests.delete(url, headers=self._auth_headers(), timeout=10)
        response.raise_for_status()
        return response.json()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def calculate_size(self, epic, price):
        """
        Calculate deal size so that the margin used equals POSITION_SIZE_PERCENT of account equity.

        margin_used = size * price * (margin_factor / 100)
        Solving for size: size = (balance * position_size_percent/100) / (price * margin_factor/100)
                                = (balance * position_size_percent) / (price * margin_factor)
        """
        try:
            balance = self.get_account_balance()
            info = self.get_market_info(epic)
            instrument = info.get("instrument", {})
            margin_factor = float(instrument.get("marginFactor", 100))
            if instrument.get("marginFactorUnit", "PERCENTAGE") != "PERCENTAGE":
                margin_factor = 100.0
            min_size = float(info.get("dealingRules", {}).get("minDealSize", {}).get("value", 0.1))

            size = (balance * config.POSITION_SIZE_PERCENT) / (price * margin_factor)
            size = round(size, 2)
            logger.info(
                "Size calc: balance=%.2f margin_factor=%.2f%% price=%.2f → size=%.2f (min=%.2f)",
                balance, margin_factor, price, size, min_size,
            )
            return max(size, min_size)
        except Exception as exc:
            logger.warning("Could not calculate size, using min size: %s", exc)
            return self.get_min_deal_size(epic)
