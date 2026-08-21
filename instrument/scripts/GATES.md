# Por qué existe cada gate

Los seis salieron de defectos medidos en el bot anterior, no de buenas prácticas
genéricas. `gate.py` implementa el *qué*; esto guarda el *por qué*, para que el código
quepa en su propio presupuesto.

**G1 · Evidencia.** El bot anterior corrió un grid search de 120 configuraciones, el mejor
resultado fue `avg +0.01R`, y aun así una celda de **n=15** elegida post-hoc quedó cableada
y se citó por meses como "60% WR, +8.38R". Ningún cambio a las reglas se mergea sin ≥30
señales resueltas.

**G2 · Un spec abierto.** 36 specs en 3 meses, ninguna con un check de "¿la anterior
sirvió?" antes de la siguiente. Un solo día produjo 34 commits de spec. `docs/spec/`
(singular) es la convención de este paquete; el `docs/specs/` heredado tiene 111 archivos
de esa acumulación, y un gate mantenido en rojo por deuda que nadie va a pagar se apaga.
Por eso reporta SKIPPED hasta que el directorio nuevo exista: **un gate que no revisa nada
no debe parecerse a uno que revisó y no encontró nada.**

**G3 · Presupuesto de líneas.** El repo viejo declaró un límite de 600 líneas por archivo
y terminó con 11 archivos rompiéndolo, el mayor en 1,460. Dos presupuestos separados:
2,000 para el motor de señales y 800 para `knowledge/`, que es alcance nuevo del
2026-08-21. Juntarlos habría significado reventar el número o subirlo en silencio. Tests y
scripts quedan fuera de los totales — contar los tests le cobra impuesto al hábito que
queremos.

**G4 · Caducidad.** Cuatro calendarios escritos a mano (FOMC, earnings, OPEP, supresión)
gobernaban decisiones y **los cuatro estaban vencidos** el día de la auditoría: 24, 30, 67
y 108 días. Ninguno avisó. Uno llegó a apagar el 100% de las señales durante días sin un
solo log.

**G5 · Excepciones.** 177 `except Exception` en mayo, **344 en agosto**, 62 seguidos de
`pass`. Un `daily_report.py` llamaba una función que no existe desde hacía tres meses y el
`except` se lo tragaba: el reporte imprimía `UNKNOWN` y nadie se enteró. Es un ratchet: el
número solo puede bajar.

**G6 · Denominador.** De 92 filas, 22 tenían el stop del lado equivocado de la entrada y
0 registraban por qué había disparado la señal. Una señal huérfana —emitida y nunca
resuelta— reduce el denominador en silencio, que es cómo "92 filas" se volvió "91 cierres"
sin que nadie lo notara.
