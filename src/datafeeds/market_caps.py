from datetime import datetime, timezone
import requests

CG_BASE = "https://api.coingecko.com/api/v3"

def fetch_global_caps() -> dict:
    """
    Retorna TOTAL MCAP, BTC/ETH dominances e ALT MCAP/ALT dominance (ex-BTC,ETH).
    Sem chave de API. Ideal para rodar a cada 60–120s.
    """
    g = requests.get(f"{CG_BASE}/global", timeout=10).json().get("data", {})
    total_usd = float(g["total_market_cap"]["usd"])
    btc_dom = float(g["market_cap_percentage"]["btc"])
    eth_dom = float(g["market_cap_percentage"]["eth"])

    # Se quiser precisão no ALT MCAP em USD, também podemos buscar caps absolutos:
    # m = requests.get(f"{CG_BASE}/coins/markets", params={"vs_currency":"usd","ids":"bitcoin,ethereum"}, timeout=10).json()
    # btc_mcap = float(next(x["market_cap"] for x in m if x["id"]=="bitcoin"))
    # eth_mcap = float(next(x["market_cap"] for x in m if x["id"]=="ethereum"))
    # alt_usd = total_usd - (btc_mcap + eth_mcap)

    # Mas como CoinGecko já dá dominâncias, podemos obter ALT MCAP via dominância:
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

