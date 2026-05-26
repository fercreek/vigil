# PTS Watchlist Deep Dive — Results

> **Fecha de ejecución:** 2026-05-25
> **NotebookLM URL:** https://notebooklm.google.com/notebook/55b77cb9-7e46-466a-b4bc-8669f357f61a
> **Operador:** Fernando

## Instrucciones

1. Correr cada prompt de `PROMPTS.md` en NotebookLM.
2. Pegar output debajo del prompt correspondiente.
3. Cuando todo esté pegado → avisar a Claude: "listo, pegué resultados de NotebookLM".
4. Claude integrará findings en `config.py`, `CLAUDE.md` sección 8 y creará spec 004 si aplica.

---

## Prompt 1 — Tabla consolidada por símbolo

| Símbolo | Sector | Dirección | Entry vigente | Stop | BE | Target 1 | Target 2 | Última mención | Status | Notas |
|---|---|---|---|---|---|---|---|---|---|---|
| ASTS | Aeroespacial | LONG | - | - | - | - | - | 8k | ACTIVE | Hold ganadores, ya tuvo movimiento la semana pasada. |
| CL | Defensivo | LONG | - | - | - | - | - | 8k | ACTIVE | Estable, sube despacio. |
| COIN | Crypto Proxy | LONG | 178-200 | 160.32 | 254 | 286 | 328 | 8k | ACTIVE | Alertas long activas, entry sigue válido. |
| CORZ | AI Infra | LONG | - | - | - | - | - | 8k | ACTIVE | Prioridad alta esta semana. |
| CRWV | AI Infra | LONG | 121.82 | 91.79 | 140 | 160 | 187 | 8k | ACTIVE | Prioridad alta esta semana. |
| CVX | Energía | LONG | - | - | - | - | - | 8k | ACTIVE | Estable, alerta long defensiva. |
| HOOD | Defensivo/Fintech | LONG | 70-85 | 65.35 | 97.84 | 120 | 134 | 8j | ACTIVE | Options rollover fin de mes. |
| JNJ | Defensivo | LONG | - | - | - | - | - | 8k | ACTIVE | Estable, sube despacio. |
| KO | Defensivo | LONG | - | - | - | - | - | 8k | ACTIVE | Estable, baja prioridad. |
| MO | Defensivo | LONG | - | - | - | - | - | 8k | ACTIVE | Estable, va muy bien. |
| MOO | Defensivo | LONG | - | - | - | - | - | 8k | ACTIVE | Estable, baja prioridad. |
| OKLO | Nuclear | LONG | 73.91 | 50.26 | 84 | 101 | 137 | 8k | ACTIVE | En zona entrada, max 2/cluster nuclear. |
| SMR | Nuclear | LONG | 12.67 | 9.54 | 15 | 17 | 22 | 8k | ACTIVE | En zona entrada. |
| SOFI | Fintech | LONG | 16.99 | 12.94 | 21 | 25 | 28 | 8j | ACTIVE | Zona/lateral post-earnings. |
| UUUU | Nuclear | LONG | 22.72 | 18.50 | 25 | 28 | 31 | 8k | ACTIVE | En zona entrada. |
| VAL | Energía | LONG | - | - | - | - | - | 8k | ACTIVE | Retrocedió, potencial intacto. |
| XBI | Biotech | LONG | - | - | - | - | - | 8j | ACTIVE | Zona/lateral. |
| XLE | Energía | LONG | 58.31 | 53.06 | 61 | 63 | 69 | 8k | ACTIVE | Estable. |
| ALAB | Tech | LONG | - | - | - | - | - | 8j | PENDING | Cerca de descubrimiento de precio. |
| ARM | Tech | LONG | - | - | - | - | - | 8j | PENDING | Cerca de descubrimiento de precio. |
| BABA | E-commerce | LONG | - | - | - | - | - | 8h | PENDING | Posible suelo en formación. |
| BNB | Crypto | LONG | - | - | - | - | - | 8h | PENDING | Pipeline post-activación BTC/ETH. |
| BTC | Crypto | LONG | 79,917 | 69,919 | 85,000 | 93,000 | 101,000 | 8h | PENDING | Crypto breakout pending, trigger >$79.9k. |
| CIFR | AI Infra | LONG | - | - | - | - | - | 8k | PENDING | Prioridad alta. |
| CLSK | AI Infra | LONG | - | - | - | - | - | 8j | PENDING | OM alcista formándose, target 23/32. |
| CRCL | Tech | LONG | 60.75-83.53 | <60.75 | ~105 | 145.67 | 174.51 | 8d | PENDING | BitLobo, alerta si entra en zona. |
| ETH | Crypto | LONG | 2,520 | 2,024 | 2,967 | 3,367 | 4,277 | 8h | PENDING | Pipeline BTC. |
| ETHA | Crypto Options | LONG | - | - | - | - | - | 8h | PENDING | Pipeline opciones post-breakout. |
| IBIT | Crypto Options | LONG | - | - | - | - | - | 8h | PENDING | Pipeline opciones post-breakout. |
| IREN | AI Infra | LONG | - | 57.00 | - | - | - | 8j | PENDING | Contradicción: Cerró stop ganancia (8i), recovery (8j). |
| IWM | Equities | SHORT | - | - | - | - | - | 8j | PENDING | Testeó soporte, clave small caps. |
| META | Tech | LONG | - | - | - | - | - | 8c | PENDING | Solo si SP500 rompe ZR al alza. |
| MP | Materiales | LONG | 63.28 | 48.11 | 73 | 79 | 89 | 8j | PENDING | Reentrada pendiente ~68. |
| MSFT | Tech | LONG | - | - | - | - | - | 8j | PENDING | Candidato rebote (8f), lista supresión earnings. |
| NKE | Consumo | LONG | - | - | - | - | - | 8d | PENDING | Señal semanal BitLobo. |
| RDDT | Tech | LONG | - | - | - | - | - | 8h | PENDING | Esperar earnings antes de entrada formal. |
| RIOT | Crypto Stock | LONG | - | - | - | - | - | 8h | PENDING | Pipeline acciones crypto. |
| SOL | Crypto | LONG | - | - | - | - | - | 8h | PENDING | Pipeline post-activación BTC/ETH. |
| SPY | Equities | SHORT | <6,728 | - | - | - | - | 8h | PENDING | Trigger si SP500 pierde 6,728. |
| TBT | Bonos | - | - | - | - | - | - | 8k | PENDING | Vigilar rendimientos. |
| TLT | Bonos | - | - | - | - | - | - | 8k | PENDING | Vigilar rendimientos. |
| TSLA | Equities | SHORT | 335.65 | 359.87 | 320 | 302 | 276 | 8h | PENDING | Solo si SP500 cae a naranja. |
| USAR | Tech | LONG | - | - | - | - | - | 8j | PENDING | PHY alcista, monitoreo. |
| WEN | Consumo | LONG | 4.30-7.06 | <4.30 | - | - | - | 8d | PENDING | BitLobo, no intradía. |
| XLK | Equities | SHORT | - | - | - | - | - | 8c | PENDING | Monitoreo bajista inicial. |
| XOM | Energía | LONG | 162.49 | 149.60 | 176 | 185 | 205 | 8k | PENDING | Tocó BE, reentrada pendiente. |
| IONQ | Cuántica | LONG | 50.05 | 35.44 | 62 | 72 | 85 | 8k | **SUPPRESSED** | Sobreextendida, no reentry hasta corrección. |
| RGTI | Cuántica | LONG | 19.00 | - | - | - | - | 8k | **SUPPRESSED** | Sobreextendida, no reentry hasta corrección. |
| GDX | Oro | LONG | 92.78 | - | - | 96.00 | - | 8h | CLOSED | T1 alcanzado ~$96. |
| MAGS | Equities | SHORT | - | - | - | - | - | 8e | CLOSED | Cerrada en ganancia. |
| RKLB | Aeroespacial | LONG | 74.90 | 91.00 | - | 100 | - | 8i | CLOSED | T1 +30%, stop ganancia 91. |
| XLC | Equities | SHORT | - | - | - | - | - | 8e | CLOSED | Cerrada en ganancia. |
| XLF | Equities | SHORT | - | - | - | - | - | 8e | CLOSED | Cerrada en ganancia. |

**Total:** 51 símbolos · 18 ACTIVE · 28 PENDING · 2 SUPPRESSED · 5 CLOSED

---

## Prompt 2 — Contradicciones y cambios de tono

### 1. 8c/8e vs 8f/8h — Cambio de sesgo macro en SP500
- **8c/8e (9-13 Abr):** Escenario bajista era el más probable, esperando rechazo de ZR e inicio de nueva ola bajista.
- **8f/8h (14-23 Abr):** SP500 rompió ZR y MACRO PHY al alza; toros gobiernan, régimen VERDE_BULL activo.
- **Hipótesis:** Mercado ignoró macroeconomía, subió por promesas Trump → short-covering masivo rompió niveles técnicos bajistas.
- **Implicación bot:** Cambiar `MACRO_REGIME = "VERDE_BULL"`, habilitar longs, cancelar supresión + bias bajista.

### 2. 8e vs 8h — Condicionamiento del short en TSLA
- **8e (13 Abr):** "BAJISTA SWING-POSICIONAL" para aprovechar rechazo SP500 en ZR.
- **8h (21-23 Abr):** Degradado a "SHORT pending", solo activar si SP500 cae a régimen naranja.
- **Hipótesis:** Al romper SP500 al alza hacia 7,000, short directo perdió ventaja estadística.
- **Implicación bot:** Gate estricto TSLA → solo disparar SHORT si `MACRO_REGIME == "NARANJA_BEAR"`.

### 3. 8c vs 8f vs 8h — Manejo de Stop en GDX
- **8c (9 Abr):** Target ~96 alcanzado, mover SL a BE.
- **8f (14 Abr):** Precio en ~100, SL sube a 96 para garantizar ganancias.
- **8h (23 Abr):** Posición cerrada ~$96 con ganancias.
- **Hipótesis:** GDX tuvo impulso a 100, trailing stop ajustado a 96, debilitamiento del metal hizo retroceder a stop ganancia.
- **Implicación bot:** Estado GDX = CLOSED permanente, suprimir nuevas entradas.

### 4. 8i vs 8j — Cambio de estado para IREN
- **8i (8 May):** Llegó a "stop ganancia 57", esperar sin reentrada externa.
- **8j (19-22 May):** Aparece marcada "Suelo establecido (recovery)" en convergencia con cluster ai_infra.
- **Hipótesis:** Tras barrida 19-May en sector AI, IREN alcanzó niveles técnicos que confirmaron suelo.
- **Implicación bot:** Remover stop ganancia interno, reactivar IREN en `SECTOR_CLUSTERS["ai_infra"]` como PENDING/RECOVERY.

### 5. 8i/8j vs 8k — IONQ/Cuánticas: de alcista fuerte a sobreextensión
- **8i/8j (8-22 May):** Nueva entrada en 50.05 que "activó fuerte", "potencial súper trade", enormes ganancias.
- **8k (25 May):** Cluster cuántico (IONQ, RGTI) etiquetado "SOBREEXTENDIDAS", pidiendo no emitir reentradas.
- **Hipótesis:** Movimiento alcista vertiginoso las dejó en nivel insostenible (fase euforia), vulnerables a retrocesos violentos.
- **Implicación bot:** Activar `QUANTUM_SUPPRESSED_UNTIL = "2026-06-01"`, añadir IONQ/RGTI a SUPPRESSED_LIST, alertar solo si caen >10%.

### 6. 8g vs 8i — Reentrada MP tras caída fuerte
- **8g (15 Abr):** Apertura "SWING ALCISTA".
- **8i (8 May):** "Subió y se devolvió con fuerza", "pueden tomar en 68", "esperar análisis" sin niveles fijos.
- **Hipótesis:** Rally post 14-Abr, barrida por earnings o volatilidad sectorial.
- **Implicación bot:** Estado PENDING en zona 68, desactivar entry inicial, suprimir ejecuciones hasta próximo reporte con SL/PT concretos.

---

## Prompt 3 — Sectores: convergencia y correlación

### 1. Nuclear (UUUU, OKLO, SMR)
- **Activas/Pending:** 3 simultáneas (todas activas en zona entrada).
- **Correlación:** Muy alta. Daniel las agrupa, formaron PHY con ZR al mismo tiempo, sufrieron misma barrida 20-May.
- **Líder:** OKLO — licencia NRC para reactor en Alaska, valoración madura $250-350.
- **Riesgo:** Alto colapso correlacionado. Daniel: "no acumular UUUU+OKLO+SMR misma sesión".

### 2. AI Infrastructure (CRWV, IREN, CORZ, CIFR, CLSK)
- **Activas/Pending:** 5 simultáneas (CRWV/CORZ active; IREN/CIFR/CLSK pending).
- **Correlación:** Alta, convergencia tema. Prioridad alta esta semana.
- **Líder:** IREN (más histórica, desde abril) y CLSK (OM alcista, target $32).
- **Riesgo:** Moderado. Permiso excepcional max 3 esta semana mientras SP500 > 7000.

### 3. Quantum (IONQ, RGTI)
- **Activas/Pending:** 0 (SUPPRESSED).
- **Correlación:** Extremadamente alta. Subida vertical post-earnings = sobreextensión conjunta.
- **Líder:** IONQ ("potencial súper trade" desde 50.05).
- **Riesgo:** Crítico. `QUANTUM_SUPPRESSED_UNTIL = "2026-06-01"`, alertar solo si caen >10%.

### 4. Crypto Proxy (COIN, BTC, ETH, mineras)
- **Activas/Pending:** 1 active (COIN); BTC/ETH/BNB/SOL/IBIT/ETHA/RIOT pendientes.
- **Correlación:** Total dependencia de BTC. Pipeline activa al romper >$74k.
- **Líder:** BTC catalizador macro; COIN proxy líder acciones.
- **Riesgo:** Si BTC falla ruptura, todas caen en bloque.

### 5. Petroleras / Energía (XOM, CVX, XLE, VAL)
- **Activas/Pending:** 4 simultáneas (XLE/CVX/VAL active; XOM pending reentry).
- **Correlación:** Alta entre ellas, **descorrelacionadas del SP500**. Van a su propio ritmo.
- **Líder:** XLE pauta técnica; XOM favorita defensiva swing.
- **Riesgo:** Bajo. Rebalance ideal para caídas tech.

### 6. Defensivos (JNJ, KO, CL, MO, MOO)
- **Activas/Pending:** 5 simultáneas (todas activas).
- **Correlación:** Bloque, refugio baja volatilidad.
- **Líder:** Históricamente MOO; ahora JNJ (defensiva con fuerza alcista semis) y MO.
- **Riesgo:** Muy bajo.

### 7. Otros únicos (Aero/Fintech/Biotech)
- **Activas/Pending:** ~4 (HOOD, SOFI, XBI, ASTS). RKLB CLOSED ganancia.
- **Correlación:** Baja/nula. Catalizadores particulares.
- **Líderes:** RKLB (+30% trimestre); HOOD > SOFI en fortaleza.
- **Riesgo:** Seguro.

### Recomendación MAX_PER_CLUSTER

| Cluster | MAX_PER_CLUSTER | Justificación |
|---------|-----------------|---------------|
| nuclear | **2** | Barridas conjuntas, regla explícita Daniel |
| ai_infra | **3 (temporal)** | Prioridad alta semana, default normal 2, boost si SP500 > 7000 |
| quantum | **0 (suprimido)** | Hasta jun-2026 o corrección 10%; default posterior 2 |
| crypto_proxy | **1-2** | Restringir hasta BTC > $74k |
| petroleras | **2-3** | Cobertura descorrelacionada, riesgo bajo |
| defensivos | **3** | Baja volatilidad, riesgo bajo |
| aisladas (fintech/space) | **1 por sub-nicho** | SOFI/HOOD max 1, ASTS/RKLB max 1 |

---

## Prompt 4 — Régimen macro: línea de tiempo

| Fecha | Sección | SP500 nivel | Régimen | VIX | Trigger relevante |
|-------|---------|-------------|---------|-----|-------------------|
| 9 Abr | 8c | ~6,772 (dentro ZR) | AMARILLA_INDECISA | N/D | Romper 6,858 (bull) o rechazar 6,741 (bear) |
| 9 Abr | 8d | N/D | AMARILLA_INDECISA | N/D | N/D |
| 13 Abr | 8e | Testeando alta ZR (0.78) | AMARILLA_INDECISA (sesgo bajista probable) | Mínimo reciente | Si rompe ZR al alza hacia 7,000 |
| 14 Abr | 8f | Avanzando hacia 7,000 | **VERDE_BULL** (rebote short-covering) | N/D | Si SP500 sigue arriba |
| 15 Abr | 8g | ~6,832 (intenta romper MACRO PHY) | AMARILLA_INDECISA | N/D | Pierde 6,832 prep short; pierde 6,728 entra short |
| 21-23 Abr | 8h | >7,000 (consolidando) | **VERDE_BULL** (toros gobiernan) | Volatilidad intradía 60-80 pts | Pierde 7,000 alarma; pierde 6,728 naranja |
| 8 May | 8i | N/D post-earnings | VERDE_BULL | N/D | N/D |
| 19-22 May | 8j | ~7,100-7,200 (a 2% máx) | **VERDE_BULL_DORMANT** (barridas = oportunidad) | <22 rompiendo a la baja | IWM perdiendo soporte o VIX > 22 |
| 25 May | 8k | Muy arriba de 7,000 | VERDE_BULL (gap alcista probable) | <22 heredado | Pierde mínimos semana pasada (50%); pierde 7,000 (amarilla) |

### Puntos de inflexión

1. **14-Abr (8f):** SP500 rompe ZR al alza → invalida bear case primera semana abril.
2. **21-23 Abr (8h):** SP500 consolida >7,000 → régimen oficial **VERDE_BULL**, longs habilitadas.
3. **19-22 May (8j):** Absorción de barridas con VIX <22 → barridas = oportunidad, no pánico.

### Patrón visible

Inicio Abr: bear market rally / short-covering / macro presión (inflación + oil). Tras ruptura MACRO PHY: recuperación alcista legítima guiada por rotación sectorial. Fines May: volatilidad alta intradía pero estructura subyacente soporta máximos históricos en acciones calidad.

### Señales a vigilar semana 26-30 May

1. **SP500 < 7,000** → degrada a AMARILLA_INDECISA, suprimir nuevas longs.
2. **Pérdida mínimos semana anterior** → reducir 50% tamaño posiciones en longs vigentes.
3. **VIX > 22** → invalida VERDE_BULL_DORMANT, volver a filtrar longs en picos bajistas.

---

## Prompt 5 — Operaciones cerradas: análisis de éxito

| Símbolo | Entry | Exit aprox | % ganancia | Días en posición | Sector | Tipo |
|---------|-------|------------|------------|------------------|--------|------|
| RKLB | 74.90 | 97.37-100 (T1) | +26-30% | ~25d (13 Abr - 8 May) | Aeroespacial explosivas | Rápida |
| IREN | 52.38 | 57.00 (stop ganancia) | ~8.8% | ~17d (21 Abr - 8 May) | AI Infra | Swing |
| GDX | 92.78 | ~96.00 | ~3.5% | >14d (cerrada 21 Abr) | Oro defensivo | Swing |
| IONQ | N/D | N/D | Ganancia pre-earnings | N/D | Cuánticas | N/D |
| SPY SHORT | N/D | N/D | N/D | Cerrada pre 13 Abr | Equities | Bajista |
| MAGS SHORT | N/D | N/D | N/D | Cerrada pre 13 Abr | Equities | Bajista |
| XLC SHORT | N/D | N/D | N/D | Cerrada pre 13 Abr | Equities | Bajista |
| XLF SHORT | N/D | N/D | N/D | Cerrada pre 13 Abr | Equities | Bajista |

### Patrones de éxito

1. **Sector mayor % ganadores:** Aeroespacial/explosivas (RKLB +30%). A nivel de tasa de éxito en bloque: shorts/bajistas (Equities + petroleras pre-13 Abr durante rechazo bear market rally).
2. **Rápida vs Swing:** Paradójicamente Swing (GDX, IREN) cerró más rápido (~14-17d) pero con márgenes menores (3.5-8.8%). Rápida (RKLB) requirió +paciencia (~25d) pero capitalizó movimiento direccional 30%.
3. **Dos patrones de ganadores:**
   - **Transición (RKLB):** acciones explosivas con corrección previa, justo cuando SP500 amenaza romper ZR al alza.
   - **Defensivos en presión (GDX/shorts):** mientras SP500 estancado en AMARILLA_INDECISA + presión macro inflación + oil.

### Filtros propuestos para el bot

1. **`EXPLOSIVE_CORRECTION` filter:** Si transición AMARILLA_INDECISA → VERDE_BULL → aplicar `PRIORITY_BOOST` a acciones volátiles/explosivas (RKLB, HOOD, ASTS) que vengan de corrección severa. Capturan short-covering.
2. **`BARRIDA_OPPORTUNITY` filter:** Si `MACRO_REGIME = VERDE_BULL` (SP500 > 7000) + `VIX < 22` → caída súbita intradía en clusters AI-Infra/Nuclear NO se filtra por stops rígidos, se alerta inmediatamente como reentrada fuerte.

---

## Prompt 6 — Plan accionable semana 26-30 May

### Plan Semanal PTS (26-30 May 2026)

| Día | Símbolos | Niveles clave | Catalizadores | Acción del bot |
|-----|----------|---------------|---------------|----------------|
| **Lunes 26** | CRWV, CORZ, CIFR 🔥 / COIN 🔥 | CRWV 121.82/91.79/160 · COIN 178-200/160.32/254 | Apertura. Futuros gap alcista probable | Confirmar SP500 > 7000 + gap. Habilitar longs AI Infra + Crypto. `PRIORITY_BOOST_CLUSTER = "ai_infra"`, max 3 |
| **Martes 27** | OKLO (Media) | OKLO 73.91/50.26/101 | **OKLO Earnings** | 🚨 SUPPRESS 24H OKLO. No sobreextender nuclear (max 2/cluster) |
| **Miércoles 28** | UUUU, SMR (Media) / IONQ, RGTI ⛔ | UUUU 22.72/18.50/28 · SMR 12.67/9.54/17 | Sin catalizador macro grande | Vigilar UUUU/SMR si sostienen suelo barrida previa. `QUANTUM_SUPPRESSED_UNTIL = "2026-06-01"` |
| **Jueves 29** | XOM, CVX (Baja) / TLT, TBT | XOM reentry BE · CVX pullback | Bonos 20Y máximo? · 2da clase Taller PTS | Vigilar rendimientos bonos (retroceso = bull equities). Petroleras tag "DEFENSIVA_ESTABLE" |
| **Viernes 30** | HOOD (Media) / JNJ, MO (Baja) | HOOD 70-85/65.35/120 · JNJ/MO arriba entry | Rollover options fin de mes | Vigilar volatilidad anómala HOOD por cierre contratos. Defensivas sin urgencia |

### Top 3 oportunidades

1. **Cluster AI Infra (CRWV, CORZ, CIFR)** — directriz explícita "Prioridad alta esta semana", boost SP500>7000.
2. **COIN** — entry zone 178-200 intacta post-volatilidad, alerta long activa post-breakout BTC.
3. **Nuclear sin earnings (UUUU, SMR)** — zona entrada atractiva tras suelo PHY+ZR, menor riesgo salto stop vs OKLO.

### Top 3 riesgos

1. **SP500 pierde mínimos semana pasada** — reducir 50% tamaño en todas longs abiertas.
2. **Rebote violento rendimientos bonos (TLT/TBT)** — si suben, presión bajista en equities (especialmente sectores beta alta).
3. **Cuánticas (IONQ/RGTI) marcadas "SOBREEXTENDIDAS"** — corrección vertical >10% podría detonar pánico en clusters de alta beta correlacionados.

### Triggers cambio de régimen

| Trigger | Cambio | Acción bot |
|---------|--------|-----------|
| SP500 < 7,000 | → AMARILLA_INDECISA | Suprimir nuevas longs, mercado en falsa ruptura |
| SP500 < 6,800-6,728 | → NARANJA_BEAR | MACRO PHY invalidado, activar shorts (TSLA, SPY), bloquear longs débiles |
| VIX > 22 | Desactiva VERDE_BULL_DORMANT | Barridas dejan de ser oportunidad, volver a filtrar longs en picos |

---

## Prompt 7 — Audio Overview (opcional)

<!-- Si generaste el audio, pegar URL del audio compartido (NotebookLM permite share link). -->

---

## Notas adicionales del operador

<!-- Cualquier observación de Fernando al revisar los outputs. Ej:
- "El Audio Overview se equivoca en XLE — el nivel correcto es 60, no 58".
- "NotebookLM no mencionó RKLB T1 alcanzado, pero el commit f648d0c lo confirma".
-->
