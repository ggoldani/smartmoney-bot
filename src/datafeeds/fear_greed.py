"""Fear & Greed Index fetcher with exponential backoff retry."""

import asyncio
import aiohttp
import json
import os
from typing import Optional, Tuple
from src.utils.logging import logger


async def fetch_fear_greed_index() -> Tuple[Optional[int], str]:
    """
    Fetch Fear & Greed Index from CoinMarketCap API.

    Returns:
        Tuple of (index_value, label) where:
        - index_value: Integer 0-100 (or None if fetch failed)
        - label: Description like "Extreme Greed", "Fear", etc.

    Implements exponential backoff retry: 2s, 4s, 8s (total 3 attempts)
    """
    api_url = "https://pro-api.coinmarketcap.com/v3/fear-and-greed/latest"

    # Exponential backoff delays: 2s, 4s, 8s
    retry_delays = [2, 4, 8]

    for attempt, delay in enumerate(retry_delays, 1):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    api_url,
                    timeout=aiohttp.ClientTimeout(total=10),
                    headers={
                        "User-Agent": "tech.goldani@gmail.com",
                        "X-CMC_PRO_API_KEY": os.getenv("COINMARKETCAP_API_KEY", "")
                    }
                ) as response:
                    if response.status == 200:
                        data = await response.json()

                        # Extract Fear & Greed value and label from API response
                        fgi_value = data.get("data", {}).get("value", None)
                        fgi_label = data.get("data", {}).get("value_classification", "Indisponível")

                        if fgi_value is not None:
                            logger.info(
                                f"✅ Fear & Greed Index fetched: {fgi_value}/100 - {fgi_label}"
                            )
                            return fgi_value, fgi_label
                    else:
                        logger.warning(
                            f"❌ Fear & Greed API error (attempt {attempt}): "
                            f"status {response.status}"
                        )

        except asyncio.TimeoutError:
            logger.warning(
                f"⏱️ Fear & Greed API timeout (attempt {attempt}/3)"
            )
        except aiohttp.ClientError as e:
            logger.warning(
                f"🔌 Fear & Greed API connection error (attempt {attempt}/3): {str(e)}"
            )
        except json.JSONDecodeError as e:
            logger.warning(
                f"📦 Fear & Greed API invalid JSON (attempt {attempt}/3): {str(e)}"
            )
        except Exception as e:
            logger.warning(
                f"⚠️ Fear & Greed API unexpected error (attempt {attempt}/3): {str(e)}"
            )

        # Wait before retry (except on last attempt)
        if attempt < len(retry_delays):
            logger.info(f"⏳ Retry in {delay}s...")
            await asyncio.sleep(delay)

    # All retries exhausted
    logger.error(
        "❌ Fear & Greed Index fetch failed after 3 attempts - using fallback"
    )
    return None, "Indisponível"


def get_fear_greed_sentiment(
    fgi_value: Optional[int]
) -> Tuple[str, str]:
    """
    Map Fear & Greed Index value to sentiment category.

    Args:
        fgi_value: Integer 0-100 (or None)

    Returns:
        Tuple of (emoji, sentiment_text) for message formatting
    """
    if fgi_value is None:
        return "❓", "Indisponível"

    if fgi_value >= 80:
        return "🤑", "Ganância Extrema"
    elif fgi_value >= 60:
        return "😊", "Ganância"
    elif fgi_value >= 40:
        return "😐", "Neutro"
    elif fgi_value >= 25:
        return "😨", "Medo"
    else:
        return "😱", "Medo Extremo"
