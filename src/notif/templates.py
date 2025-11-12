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

# Disclaimer para todos os alertas
ALERT_DISCLAIMER = """
⚠️ IMPORTANTE: Este é apenas um alerta de condição de mercado.
NÃO É recomendação de compra ou venda. DYOR."""


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

    return f"""🔴 RSI Sobrecomprado ({timeframe})

💰 Mercado entrando em GANANCIA no {timeframe}.

{symbol}: {price}
RSI: {rsi}

⏰ {timestamp}
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

    return f"""🟢 RSI Sobrevendido ({timeframe})

😨 Mercado entrando em MEDO no {timeframe}.

{symbol}: {price}
RSI: {rsi}

⏰ {timestamp}
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

    return f"""🚨🔴 RSI EXTREMAMENTE SOBRECOMPRADO! ({timeframe})

💸 Mercado entrando em GANANCIA EXTREMA no {timeframe}.

⚠️ CONDIÇÃO EXTREMA DETECTADA!
{symbol}: {price}
RSI: {rsi}

🔥 Mercado pode estar em topo absoluto!
⚡ Atenção redobrada!

⏰ {timestamp}
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

    return f"""🚨🟢 RSI EXTREMAMENTE SOBREVENDIDO! ({timeframe})

😱 Mercado entrando em MEDO EXTREMO no {timeframe}.

⚠️ CONDIÇÃO EXTREMA DETECTADA!
{symbol}: {price}
RSI: {rsi}

🔥 Mercado pode estar em fundo absoluto!
⚡ Atenção redobrada!

⏰ {timestamp}
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
        emoji = "🔴" if cond["condition"] == "OVERBOUGHT" else "🟢"
        condition_text = "Sobrecomprado" if cond["condition"] == "OVERBOUGHT" else "Sobrevendido"

        tf_lines.append(f"  {emoji} {tf}: RSI {rsi} ({condition_text})")

    tf_list = "\n".join(tf_lines)

    return f"""🚨 ALERTA: Múltiplos Timeframes Críticos

{symbol}: {price}

Condições detectadas:
{tf_list}

⏰ {timestamp}
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

    return f"""🚀 ROMPIMENTO DE ALTA AGORA! ({timeframe})

⚡ {symbol} está rompendo a máxima anterior AGORA!
👀 Observe o price action!

Preço atual: {price}
Máxima anterior: {prev_high}
Variação: +{change_pct}

⏰ {timestamp}
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

    return f"""📉 ROMPIMENTO DE BAIXA AGORA! ({timeframe})

⚡ {symbol} está rompendo a mínima anterior AGORA!
👀 Observe o price action!

Preço atual: {price}
Mínima anterior: {prev_low}
Variação: -{change_pct}

⏰ {timestamp}
{ALERT_DISCLAIMER}"""


def template_circuit_breaker(alert_count: int, conditions: List[str]) -> str:
    """
    Template for circuit breaker mega-alert (extreme volatility).

    Args:
        alert_count: Number of alerts triggered
        conditions: List of condition descriptions
    """
    timestamp = format_datetime_br()
    conditions_list = "\n".join([f"• {c}" for c in conditions])

    return f"""🚨 VOLATILIDADE EXTREMA DETECTADA

⚠️ {alert_count} condições críticas atingidas simultaneamente!

Condições:
{conditions_list}

📊 Recomenda-se cautela e análise cuidadosa antes de operar.

⏰ {timestamp}"""


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

    return f"""✅ {bot_name} Iniciado (v{version})

📊 Monitorando: {sym_display}
⏱️ Timeframes: {tf_display}
🔔 Alertas ativos: RSI, Rompimentos

⏰ {timestamp}"""


def template_shutdown() -> str:
    """Template for bot shutdown/maintenance message."""
    bot_name = get_bot_name()
    timestamp = format_datetime_br()

    return f"""⚠️ {bot_name} Entrando em Manutenção

O bot será reiniciado em breve.
Alertas voltarão automaticamente após o restart.

⏰ {timestamp}"""


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

    msg = f"""❌ ERRO CRÍTICO - {error_type}

Bot: {bot_name}
Erro: {error_msg}"""

    if context:
        msg += f"\nContexto: {context}"

    msg += f"\n\n⏰ {timestamp}"

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

    return f"""⚠️ AVISO - {warning_type}

Bot: {bot_name}
Aviso: {warning_msg}

⏰ {timestamp}"""


def template_backfill_complete(results: Dict[str, int]) -> str:
    """
    Template for backfill completion (admin channel).

    Args:
        results: {"1h": 200, "4h": 200, "1d": 200, "1w": 200}
    """
    total = sum(results.values())
    details = "\n".join([f"  • {format_timeframe_display(tf)}: {count} velas"
                         for tf, count in results.items()])

    return f"""✅ Backfill Histórico Completado

Total: {total} velas salvas

Detalhes:
{details}

⏰ {format_datetime_br()}"""
