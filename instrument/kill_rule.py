"""La kill-rule, ejecutada.

El criterio estaba escrito antes de la primera senal, que es la parte dificil y
ya estaba hecha: *si tras 100 senales resueltas el borde superior del IC de la
expectancy sigue por debajo de cero, el universo se retira*. Lo que faltaba es que
alguien lo aplicara. Vivia en `EQUITIES.md` y en `_MAP-instrument.md`, y un
criterio que solo existe en prosa se renegocia exactamente cuando toca aplicarlo
-- que es cuando menos ganas dan de aplicarlo, porque para entonces ya hay meses
invertidos en la regla que va a morir.

Tres propiedades deliberadas:

  * **Por universo.** Acciones y cripto tienen evidencia distinta y mueren por
    separado. Retirar las dos porque una fallo seria el mismo promedio que el
    marcador ya dejo de hacer.
  * **Solo en una direccion.** Este modulo escribe retiros, nunca los borra.
    Reactivar un universo es una decision humana, con nombre y fecha, no algo que
    ocurra solo porque llegaron unas velas buenas.
  * **Conservador por construccion.** Hacen falta n >= umbral Y un IC entero bajo
    cero. Con menos muestra el veredicto es EN OBSERVACION y no pasa nada; el
    modo de fallo que importa aqui es apagar el bot por un calculo flojo, no
    tardar una semana de mas en apagarlo.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any

from . import scoreboard


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def is_retired(conn: sqlite3.Connection, universe: str) -> bool:
    return conn.execute("SELECT 1 FROM retirements WHERE universe = ?",
                        (universe,)).fetchone() is not None


def retirement(conn: sqlite3.Connection, universe: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM retirements WHERE universe = ?",
                        (universe,)).fetchone()


def retired_universes(conn: sqlite3.Connection) -> set[str]:
    return {r["universe"] for r in conn.execute("SELECT universe FROM retirements")}


def _record(conn: sqlite3.Connection, universe: str, report: dict[str, Any],
            now: str | None = None) -> None:
    ci_lo, ci_hi = report["expectancy_ci"]
    conn.execute(
        "INSERT OR IGNORE INTO retirements "
        "(universe, retired_at, n_resolved, ci_upper, expectancy, threshold, note) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (universe, now or _now(), report["n_resolved"], ci_hi, report["expectancy_r"],
         scoreboard.KILL_RULE_N,
         f"IC95 [{ci_lo:+.3f}, {ci_hi:+.3f}] tras {report['n_resolved']} resueltas"))


def evaluate(conn: sqlite3.Connection, now: str | None = None) -> list[dict[str, Any]]:
    """Revisa cada universo vivo y retira los que cumplan el criterio.

    Devuelve una entrada por universo RETIRADO EN ESTA PASADA -- no por universo
    ya retirado antes. Eso es lo que permite avisar una sola vez: quien llame
    puede mandar el mensaje sin llevar su propia memoria de a quien ya le aviso.
    """
    nuevos = []
    for universe in scoreboard.UNIVERSES:
        if is_retired(conn, universe):
            continue
        report = scoreboard.build_report(conn, universe=universe)
        if report["n_resolved"] < scoreboard.KILL_RULE_N:
            continue
        _, ci_hi = report["expectancy_ci"]
        if ci_hi >= 0:
            continue
        _record(conn, universe, report, now)
        conn.commit()
        nuevos.append({"universe": universe, "n_resolved": report["n_resolved"],
                       "ci_upper": ci_hi, "expectancy": report["expectancy_r"]})
    return nuevos


_LABEL = {"crypto": "cripto", "equities": "acciones"}


def announcement(entry: dict[str, Any]) -> str:
    """El mensaje trae los numeros que lo decidieron, no solo el veredicto: la
    kill-rule apaga algo que costo meses, y quien lo lea tiene derecho a
    comprobar la aritmetica antes de creersela."""
    quien = _LABEL.get(entry["universe"], entry["universe"])
    return (f"🛑 Retirado: {quien}.\n"
            f"Tras {entry['n_resolved']} señales resueltas la expectancy es "
            f"{entry['expectancy']:+.3f}R y el borde superior de su intervalo sigue en "
            f"{entry['ci_upper']:+.3f} — por debajo de cero.\n"
            f"El criterio se escribió antes de la primera señal. Dejo de emitir en "
            f"{quien}; cripto y acciones se retiran por separado.\n"
            f"Reactivarlo es decisión tuya: borra la fila de `retirements`.")
