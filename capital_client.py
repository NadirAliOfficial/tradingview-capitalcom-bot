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

    def get_min_deal_size(self, epic):
        """Return the minimum deal size for an instrument."""
        self._ensure_session()
        url = f"{config.BASE_URL}/markets/{epic}"
        response = requests.get(url, headers=self._auth_headers(), timeout=10)
        response.raise_for_status()
        dealing_rules = response.json().get("dealingRules", {})
        min_size = dealing_rules.get("minDealSize", {}).get("value", 0.1)
        return float(min_size)

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
        Calculate deal size based on configured equity percentage.
        Falls back to minimum deal size if calculated size is too small.
        """
        try:
            balance = self.get_account_balance()
            allocation = balance * (config.POSITION_SIZE_PERCENT / 100)
            min_size = self.get_min_deal_size(epic)
            # For CFDs size is typically in lots; allocation / price gives approximate lots
            size = round(allocation / price, 2)
            return max(size, min_size)
        except Exception as exc:
            logger.warning("Could not calculate size, using min size: %s", exc)
            return self.get_min_deal_size(epic)
