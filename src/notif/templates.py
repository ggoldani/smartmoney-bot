# -*- coding: utf-8 -*-
"""
Message templates for Telegram alerts in Portuguese (Brazil).
All messages use Brazilian formatting for numbers, dates, and currency.
"""
from typing import List, Dict
from src.notif.formatter import (
    format_price_br,
    format_datetime_br,
    format_rsi_value,
    format_symbol_display,
    format_timeframe_display,
    format_percentage_br
)
from src.config import get_bot_name, get_bot_version

# Disclaimer simplificado
ALERT_DISCLAIMER = "⚠️ Apenas alerta de condição. Não é recomendação. DYOR."


def template_rsi_overbought(data: Dict) -> str:
    """
    Template for RSI overbought alert.

    Args:
        data: {
            "symbol": "BTCUSDT",
            "interval": "4h",
            "rsi": 75.3,
            "price": 67420.50
        }
    """
    symbol = format_symbol_display(data["symbol"])
    timeframe = format_timeframe_display(data["interval"])
    rsi = format_rsi_value(data["rsi"])
    price = format_price_br(data["price"])
    timestamp = format_datetime_br()

    return f"""RSI Sobrecomprado ({timeframe})

{symbol} {price}
RSI {rsi}

{timestamp}
{ALERT_DISCLAIMER}"""


def template_rsi_oversold(data: Dict) -> str:
    """
    Template for RSI oversold alert.

    Args:
        data: Same as template_rsi_overbought
    """
    symbol = format_symbol_display(data["symbol"])
    timeframe = format_timeframe_display(data["interval"])
    rsi = format_rsi_value(data["rsi"])
    price = format_price_br(data["price"])
    timestamp = format_datetime_br()

    return f"""RSI Sobrevendido ({timeframe})

{symbol} {price}
RSI {rsi}

{timestamp}
{ALERT_DISCLAIMER}"""


def template_rsi_extreme_overbought(data: Dict) -> str:
    """
    Template for EXTREME RSI overbought alert (RSI > 85).

    Args:
        data: Same as template_rsi_overbought
    """
    symbol = format_symbol_display(data["symbol"])
    timeframe = format_timeframe_display(data["interval"])
    rsi = format_rsi_value(data["rsi"])
    price = format_price_br(data["price"])
    timestamp = format_datetime_br()

    return f"""RSI EXTREMO Sobrecomprado ({timeframe})

{symbol} {price}
RSI {rsi}

{timestamp}
{ALERT_DISCLAIMER}"""


def template_rsi_extreme_oversold(data: Dict) -> str:
    """
    Template for EXTREME RSI oversold alert (RSI < 15).

    Args:
        data: Same as template_rsi_overbought
    """
    symbol = format_symbol_display(data["symbol"])
    timeframe = format_timeframe_display(data["interval"])
    rsi = format_rsi_value(data["rsi"])
    price = format_price_br(data["price"])
    timestamp = format_datetime_br()

    return f"""RSI EXTREMO Sobrevendido ({timeframe})

{symbol} {price}
RSI {rsi}

{timestamp}
{ALERT_DISCLAIMER}"""


def template_rsi_multi_tf(critical_conditions: List[Dict]) -> str:
    """
    Template for multi-timeframe RSI critical alert (consolidation).

    Args:
        critical_conditions: List of RSI conditions
            [
                {"interval": "1h", "rsi": 75, "condition": "OVERBOUGHT", ...},
                {"interval": "4h", "rsi": 72, "condition": "OVERBOUGHT", ...}
            ]
    """
    if not critical_conditions:
        return ""

    # Get symbol and price from first condition
    symbol = format_symbol_display(critical_conditions[0]["symbol"])
    price = format_price_br(critical_conditions[0]["price"])
    timestamp = format_datetime_br()

    # Build timeframe list
    tf_lines = []
    for cond in critical_conditions:
        tf = format_timeframe_display(cond["interval"])
        rsi = format_rsi_value(cond["rsi"])
        condition_text = "Sobrecomprado" if cond["condition"] == "OVERBOUGHT" else "Sobrevendido"

        tf_lines.append(f"{tf}: RSI {rsi} ({condition_text})")

    tf_list = "\n".join(tf_lines)

    return f"""Múltiplos Timeframes Críticos

{symbol} {price}
{tf_list}

{timestamp}
{ALERT_DISCLAIMER}"""


def template_breakout_bull(data: Dict) -> str:
    """
    Template for bullish breakout alert (real-time).

    Args:
        data: {
            "symbol": "BTCUSDT",
            "interval": "1d",
            "price": 67420.50,
            "prev_high": 67000.00,
            "change_pct": 0.63
        }
    """
    symbol = format_symbol_display(data["symbol"])
    timeframe = format_timeframe_display(data["interval"])
    price = format_price_br(data["price"])
    prev_high = format_price_br(data["prev_high"])
    change_pct = format_percentage_br(data["change_pct"])
    timestamp = format_datetime_br()

    return f"""Rompimento de Alta ({timeframe})

{symbol} {price}
Máx anterior: {prev_high} | +{change_pct}

{timestamp}
{ALERT_DISCLAIMER}"""


def template_breakout_bear(data: Dict) -> str:
    """
    Template for bearish breakdown alert (real-time).

    Args:
        data: Similar to template_breakout_bull but with "prev_low"
    """
    symbol = format_symbol_display(data["symbol"])
    timeframe = format_timeframe_display(data["interval"])
    price = format_price_br(data["price"])
    prev_low = format_price_br(data["prev_low"])
    change_pct = format_percentage_br(abs(data["change_pct"]))
    timestamp = format_datetime_br()

    return f"""Rompimento de Baixa ({timeframe})

{symbol} {price}
Mín anterior: {prev_low} | -{change_pct}

{timestamp}
{ALERT_DISCLAIMER}"""


def template_divergence(data: Dict) -> str:
    """
    Template for RSI divergence alert.

    Args:
        data: {
            "symbol": "BTCUSDT",
            "interval": "4h",
            "div_type": "BULLISH" or "BEARISH",
            "price": 67420.50,
            "rsi": 35.2
        }
    """
    symbol = format_symbol_display(data["symbol"])
    timeframe = format_timeframe_display(data["interval"])
    div_type = data["div_type"]
    price = format_price_br(data["price"])
    rsi = format_rsi_value(data["rsi"])
    timestamp = format_datetime_br()

    div_label = "Bullish" if div_type == "BULLISH" else "Bearish"

    return f"""Divergência {div_label} ({timeframe})

{symbol} {price} | RSI {rsi}

{timestamp}
{ALERT_DISCLAIMER}"""


def template_circuit_breaker(alert_count: int, conditions: List[str]) -> str:
    """
    Template for circuit breaker mega-alert (extreme volatility).

    Args:
        alert_count: Number of alerts triggered
        conditions: List of condition descriptions
    """
    timestamp = format_datetime_br()
    conditions_list = " | ".join(conditions)

    return f"""Volatilidade Extrema

{alert_count} condições críticas simultâneas
{conditions_list}

{timestamp}"""


def template_mega_alert(alerts: List[Dict]) -> str:
    """
    Template for consolidated mega-alert (2+ alerts in same window).

    Args:
        alerts: List of alert dicts with type, condition, symbol, interval, rsi/price, etc
    """
    timestamp = format_datetime_br()
    alert_blocks = []

    for alert in alerts:
        if alert['type'] == 'RSI':
            symbol = format_symbol_display(alert['symbol'])
            tf = format_timeframe_display(alert['interval'])
            rsi = format_rsi_value(alert['rsi'])
            price = format_price_br(alert['price'])

            if alert['condition'] in ['EXTREME_OVERBOUGHT', 'EXTREME_OVERSOLD']:
                label = 'RSI EXTREMO' + (' Sobrecomprado' if 'OVERBOUGHT' in alert['condition'] else ' Sobrevendido')
            else:
                label = 'RSI' + (' Sobrecomprado' if 'OVERBOUGHT' in alert['condition'] else ' Sobrevendido')

            alert_blocks.append(f"{label} ({tf}): \n{symbol} {price} | RSI {rsi}")

        elif alert['type'] == 'BREAKOUT':
            symbol = format_symbol_display(alert['symbol'])
            tf = format_timeframe_display(alert['interval'])
            price = format_price_br(alert['price'])
            
            # Get breakout variation data if available
            prev_high = alert.get('prev_high')
            prev_low = alert.get('prev_low')
            change_pct = alert.get('change_pct', 0)
            
            label = 'Rompimento de Alta' if alert['condition'] == 'BULL' else 'Rompimento de Baixa'
            
            if alert['condition'] == 'BULL' and prev_high is not None:
                prev_price = format_price_br(prev_high)
                change_pct_fmt = format_percentage_br(abs(change_pct))
                sign = "+" if change_pct >= 0 else "-"
                alert_blocks.append(f"{label} ({tf}): \n{symbol} {price}\nMáx anterior: {prev_price} | {sign}{change_pct_fmt}")
            elif alert['condition'] == 'BEAR' and prev_low is not None:
                prev_price = format_price_br(prev_low)
                change_pct_fmt = format_percentage_br(abs(change_pct))
                alert_blocks.append(f"{label} ({tf}): \n{symbol} {price}\nMín anterior: {prev_price} | -{change_pct_fmt}")
            else:
                alert_blocks.append(f"{label} ({tf}): \n{symbol} {price}")

        elif alert['type'] == 'DIVERGENCE':
            symbol = format_symbol_display(alert['symbol'])
            tf = format_timeframe_display(alert['interval'])
            price = format_price_br(alert['price'])
            rsi = format_rsi_value(alert['rsi'])

            div_label = 'Bullish' if alert['condition'] == 'BULLISH' else 'Bearish'
            alert_blocks.append(f"Divergência {div_label} ({tf}): \n{symbol} {price} | RSI {rsi}")

    alerts_text = "\n\n".join(alert_blocks)

    return f"""Múltiplas Condições Críticas

{alerts_text}

{timestamp}
{ALERT_DISCLAIMER}"""


def template_startup(timeframes: List[str], symbols: List[str]) -> str:
    """
    Template for bot startup message.

    Args:
        timeframes: List of monitored timeframes
        symbols: List of monitored symbols
    """
    bot_name = get_bot_name()
    version = get_bot_version()
    timestamp = format_datetime_br()

    tf_display = ", ".join([format_timeframe_display(tf) for tf in timeframes])
    sym_display = ", ".join([format_symbol_display(s) for s in symbols])

    return f"""{bot_name} iniciado (v{version})
Monitorando: {sym_display}
Timeframes: {tf_display}
{timestamp}"""


def template_shutdown() -> str:
    """Template for bot shutdown/maintenance message."""
    bot_name = get_bot_name()
    timestamp = format_datetime_br()

    return f"""{bot_name} em manutenção
Reiniciando em breve. Alertas voltarão automaticamente.
{timestamp}"""


def template_error_admin(error_type: str, error_msg: str, context: str = "") -> str:
    """
    Template for admin channel error alerts.

    Args:
        error_type: Type of error (e.g., "WebSocket", "Telegram API", "Database")
        error_msg: Error message
        context: Additional context (optional)
    """
    bot_name = get_bot_name()
    timestamp = format_datetime_br()

    msg = f"""Erro: {error_type}
Bot: {bot_name}
{error_msg}"""

    if context:
        msg += f"\nContexto: {context}"

    msg += f"\n{timestamp}"

    return msg


def template_warning_admin(warning_type: str, warning_msg: str) -> str:
    """
    Template for admin channel warnings.

    Args:
        warning_type: Type of warning
        warning_msg: Warning message
    """
    bot_name = get_bot_name()
    timestamp = format_datetime_br()

    return f"""Aviso: {warning_type}
Bot: {bot_name}
{warning_msg}
{timestamp}"""


def template_backfill_complete(results: Dict[str, int]) -> str:
    """
    Template for backfill completion (admin channel).

    Args:
        results: {"1h": 200, "4h": 200, "1d": 200, "1w": 200}
    """
    total = sum(results.values())
    details = ", ".join([f"{format_timeframe_display(tf)}: {count}" for tf, count in results.items()])

    return f"""Backfill concluído
Total: {total} velas
{details}
{format_datetime_br()}"""


def template_daily_summary(
    symbol: str,
    fear_greed_value: int,
    fear_greed_label: str,
    rsi_1d: float,
    rsi_1w: float,
    rsi_1m: float,
    price_open: float,
    price_close: float,
    fear_emoji: str = "❓"
) -> str:
    """
    Template for daily summary alert (21:01 BRT / 00:01 UTC).

    Args:
        symbol: Trading pair (e.g., "BTCUSDT")
        fear_greed_value: Fear & Greed Index value (0-100)
        fear_greed_label: Sentiment from API
        rsi_1d: Daily RSI value
        rsi_1w: Weekly RSI value
        rsi_1m: Monthly RSI value
        price_open: Candle open price (previous day)
        price_close: Candle close price (previous day)
        fear_emoji: Emoji representing sentiment
    """
    symbol_display = format_symbol_display(symbol)
    timestamp = format_datetime_br()

    rsi_1d_fmt = format_rsi_value(rsi_1d)
    rsi_1w_fmt = format_rsi_value(rsi_1w)
    rsi_1m_fmt = format_rsi_value(rsi_1m)

    if price_open > 0:
        variation_pct = ((price_close - price_open) / price_open) * 100
    else:
        variation_pct = 0

    variation_sign = "+" if variation_pct > 0 else "-" if variation_pct < 0 else ""
    variation_formatted = format_percentage_br(abs(variation_pct))
    price_close_formatted = format_price_br(price_close)
    
    # Determine RSI trends
    rsi_1d_trend = "📈 ALTA" if rsi_1d >= 50 else "📉 BAIXA"
    rsi_1w_trend = "📈 ALTA" if rsi_1w >= 50 else "📉 BAIXA"
    rsi_1m_trend = "📈 ALTA" if rsi_1m >= 50 else "📉 BAIXA"

    return f"""Resumo Diário - {symbol_display}

Fear & Greed: {fear_greed_value}/100 ({fear_greed_label})

RSI:
1D: {rsi_1d_fmt} {rsi_1d_trend}
1W: {rsi_1w_fmt} {rsi_1w_trend}
1M: {rsi_1m_fmt} {rsi_1m_trend}

Preço: {price_close_formatted} ({variation_sign}{variation_formatted})

{timestamp}
{ALERT_DISCLAIMER}"""


def template_daily_summary_multi(
    symbols_data: List[Dict],
    fear_greed_value: int,
    fear_greed_label: str,
    fear_emoji: str = "❓"
) -> str:
    """
    Template for daily summary with multiple symbols (consolidated message).

    Args:
        symbols_data: List of dicts with symbol data:
            [{
                "symbol": "BTCUSDT",
                "rsi_1d": 52.3,
                "rsi_1w": 48.1,
                "rsi_1m": 55.2,
                "price_open": 104000.0,
                "price_close": 104250.0
            }, ...]
        fear_greed_value: Fear & Greed Index value (0-100)
        fear_greed_label: Sentiment from API
        fear_emoji: Emoji representing sentiment
    """
    timestamp = format_datetime_br()
    date_str = format_datetime_br().split()[0]  # Get date part (DD/MM/YYYY)
    
    # Build message header
    message_parts = [f"Resumo Diário - {date_str}", ""]
    message_parts.append(f"Fear & Greed: {fear_greed_value}/100 ({fear_greed_label})")
    message_parts.append("")
    
    # Process each symbol
    for symbol_info in symbols_data:
        symbol = symbol_info.get("symbol", "")
        rsi_1d = symbol_info.get("rsi_1d", 0)
        rsi_1w = symbol_info.get("rsi_1w", 0)
        rsi_1m = symbol_info.get("rsi_1m", 0)
        price_open = symbol_info.get("price_open", 0)
        price_close = symbol_info.get("price_close", 0)
        
        symbol_display = format_symbol_display(symbol)
        
        # Format RSI with ALTA/BAIXA
        rsi_1d_fmt = format_rsi_value(rsi_1d)
        rsi_1w_fmt = format_rsi_value(rsi_1w)
        rsi_1m_fmt = format_rsi_value(rsi_1m)
        
        rsi_1d_trend = "📈 ALTA" if rsi_1d >= 50 else "📉 BAIXA"
        rsi_1w_trend = "📈 ALTA" if rsi_1w >= 50 else "📉 BAIXA"
        rsi_1m_trend = "📈 ALTA" if rsi_1m >= 50 else "📉 BAIXA"
        
        # Calculate price variation
        if price_open > 0:
            variation_pct = ((price_close - price_open) / price_open) * 100
        else:
            variation_pct = 0
        
        variation_sign = "+" if variation_pct > 0 else "-" if variation_pct < 0 else ""
        variation_formatted = format_percentage_br(abs(variation_pct))
        price_close_formatted = format_price_br(price_close)
        
        # Add symbol section
        message_parts.append(f"{symbol_display}")
        message_parts.append("RSI:")
        message_parts.append(f"1D: {rsi_1d_fmt} {rsi_1d_trend}")
        message_parts.append(f"1W: {rsi_1w_fmt} {rsi_1w_trend}")
        message_parts.append(f"1M: {rsi_1m_fmt} {rsi_1m_trend}")
        message_parts.append(f"Preço: {price_close_formatted} ({variation_sign}{variation_formatted})")
        message_parts.append("")
    
    # Add footer
    message_parts.append(timestamp)
    message_parts.append(ALERT_DISCLAIMER)
    
    return "\n".join(message_parts)
