import logging
import uuid
from decimal import Decimal
import requests
from .base import BalanceProvider

log = logging.getLogger(__name__)

ETORO_API = "https://public-api.etoro.com/api/v1"


class EtoroProvider(BalanceProvider):
    name = "etoro"
    display_name = "eToro"
    credential_fields = [
        {"key": "api_key", "label": "Public API Key", "type": "password",
         "help": "Go to Settings \u2192 Trading \u2192 API Key Management. Copy your Public API Key.",
         "help_url": "https://www.etoro.com/settings/trade"},
        {"key": "user_key", "label": "User Key", "type": "password",
         "help": "Generate a User Key with 'Read' permission for your Real account. Requires SMS verification."},
    ]

    def _headers(self, credentials: dict) -> dict:
        return {
            "x-api-key": credentials["api_key"],
            "x-user-key": credentials["user_key"],
            "x-request-id": str(uuid.uuid4()),
        }

    def validate_credentials(self, credentials: dict) -> bool:
        if not credentials.get("api_key") or not credentials.get("user_key"):
            return False
        try:
            resp = requests.get(
                f"{ETORO_API}/trading/info/real/pnl",
                headers=self._headers(credentials),
                timeout=15,
            )
            return resp.status_code == 200
        except Exception as e:
            log.warning("eToro credential validation failed: %s", e)
            return False

    def get_balance(self, credentials: dict) -> Decimal:
        resp = requests.get(
            f"{ETORO_API}/trading/info/real/pnl",
            headers=self._headers(credentials),
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        portfolio = data.get("clientPortfolio", {})
        # Total equity = available credit + unrealized PnL + sum of position values
        credit = Decimal(str(portfolio.get("credit", 0)))
        unrealized_pnl = Decimal(str(portfolio.get("unrealizedPnL", 0)))
        # credit already includes cash not in positions; unrealizedPnL is the
        # floating profit/loss on open positions. Together they represent total equity.
        return credit + unrealized_pnl

    def get_currency(self, credentials: dict) -> str:
        return "USD"
