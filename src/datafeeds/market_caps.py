from datetime import datetime, timezone
import requests
from loguru import logger

CG_BASE = "https://api.coingecko.com/api/v3"


def fetch_global_caps() -> dict:
    """
    Retorna TOTAL MCAP, BTC/ETH dominances e ALT MCAP/ALT dominance (ex-BTC,ETH).
    Sem chave de API. Ideal para rodar a cada 60–120s.

    Returns:
        Dict with market cap data, or empty dict on failure.
    """
    try:
        response = requests.get(f"{CG_BASE}/global", timeout=10)
        response.raise_for_status()

        g = response.json().get("data", {})

        total_mcap = g.get("total_market_cap", {})
        dominances = g.get("market_cap_percentage", {})

        total_usd = float(total_mcap.get("usd", 0))
        btc_dom = float(dominances.get("btc", 0))
        eth_dom = float(dominances.get("eth", 0))

        alt_dom = max(0.0, 100.0 - (btc_dom + eth_dom))
        alt_usd = total_usd * (alt_dom / 100.0)

        return {
            "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
            "total_mcap_usd": total_usd,
            "btc_dominance_pct": btc_dom,
            "eth_dominance_pct": eth_dom,
            "alt_dominance_pct": alt_dom,
            "alt_mcap_usd": alt_usd,
            "source": "coingecko",
        }

    except requests.RequestException as e:
        logger.error(f"Failed to fetch market caps from CoinGecko: {e}")
        return {}
    except (ValueError, KeyError, TypeError) as e:
        logger.error(f"Failed to parse CoinGecko response: {e}")
        return {}

