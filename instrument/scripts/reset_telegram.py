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

    return 0 if (removed_id and installed_id) else 1


if __name__ == "__main__":
    raise SystemExit(main())
