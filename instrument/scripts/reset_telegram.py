#!/usr/bin/env python3
"""Manual, one-time reset of the instrument's Telegram surface.

Run this by hand after retiring the legacy bot. It clears the persistent
keyboard the OLD process left behind -- Pos / PnL / WinRate / Intel BTC /
Status / Audit, none of which answer anything now that the process behind
them is stopped -- and installs the current instrument's three real buttons
(telegram_poll.REPORT_BUTTONS) in its place.

A dead button is worse than no button: it teaches the user to stop trusting
taps on this chat at all. This script exists so that lesson gets undone in
one step instead of the user discovering it button by button.

Idempotent in the sense that matters: every run converges the chat to the
same end state (old keyboard gone, current instrument keyboard installed).
Telegram has no "set keyboard" call independent of sending a message, so
reaching that state is two more chat messages each time this runs -- reading
them twice is harmless, unlike leaving the dead keyboard up.

Usage:
    TELEGRAM_TOKEN=... TELEGRAM_CHAT_ID=... \\
        python instrument/scripts/reset_telegram.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from instrument import notify, telegram_poll  # noqa: E402

_OLD_KEYBOARD_NOTE = (
    "🧹 Quitando el teclado del bot anterior (Pos / PnL / WinRate / Intel BTC / "
    "Status / Audit) -- ese proceso ya no corre y ningún botón respondía."
)


def main() -> int:
    if not notify.TELEGRAM_TOKEN or not notify.TELEGRAM_CHAT_ID:
        print("TELEGRAM_TOKEN / TELEGRAM_CHAT_ID no configurados -- nada que hacer.")
        return 1

    removed_id = notify.send_telegram(_OLD_KEYBOARD_NOTE, reply_markup={"remove_keyboard": True})
    if removed_id:
        print(f"teclado viejo removido -- message_id={removed_id}")
    else:
        print("no se pudo remover el teclado viejo (ver log arriba)")

    labels = ", ".join(telegram_poll.REPORT_BUTTONS)
    installed_id = notify.send_telegram(
        f"✅ Teclado del instrumento nuevo instalado. Botones: {labels}.",
        reply_markup=telegram_poll.keyboard_markup(),
    )
    if installed_id:
        print(f"teclado nuevo instalado -- message_id={installed_id}")
    else:
        print("no se pudo instalar el teclado nuevo (ver log arriba)")

    commands_ok = _reset_command_menu()
    return 0 if (removed_id and installed_id and commands_ok) else 1


# The slash-command menu is a THIRD registry, separate from both the reply keyboard
# and anything a message carries: it lives on the bot account via setMyCommands and
# survives every deploy. The retired bot left /pos /pnl /winrate /intel /status
# /audit /regime /funding /macro /commodities in there, all of them pointing at a
# process that no longer runs -- a menu of dead ends.
def _reset_command_menu() -> bool:
    import json
    import urllib.error
    import urllib.request

    commands = [
        {"command": "scoreboard", "description": "Marcador: n, expectancy, MFE/MAE"},
        {"command": "pulso", "description": "Vivo + alertas de la semana"},
        {"command": "frescura", "description": "Qué tan fresco está cada dato"},
    ]
    url = notify._TELEGRAM_API.format(token=notify.TELEGRAM_TOKEN, method="setMyCommands")
    body = json.dumps({"commands": commands}).encode()
    request = urllib.request.Request(url, data=body,
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            ok = json.load(response).get("ok", False)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        print(f"no se pudo fijar el menu de comandos: {exc}")
        return False
    print("menu de comandos reemplazado -- " +
          ", ".join("/" + c["command"] for c in commands) if ok
          else "setMyCommands devolvio ok=false")
    return bool(ok)


if __name__ == "__main__":
    raise SystemExit(main())
