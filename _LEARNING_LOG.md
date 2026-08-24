# Learning log — vigil / instrument

### 2026-08-21 · Del bot que decide al instrumento que mide

**Pros:**
- El paso adversarial se corrió 3 veces y las 3 tumbaron un consenso ya dado por bueno: la
  regla de pesimismo del resolver aplicada a medias, `knowledge/` sin un solo llamador, y el
  botón de Scoreboard promediando dos estrategias. Ningún test verde los habría visto.
- El único resultado positivo del día (+0.110R "consistente entre regímenes") se mató en 10
  minutos al espaciar las entradas — era autocorrelación. La disciplina aguantó justo cuando
  había un incentivo para no mirar.
- Probar el camino real (`--once` contra datos vivos) cazó un `TypeError` que habría matado el
  loop en la primera alerta y que `restartPolicyType=ALWAYS` habría disfrazado de reinicios.
- Se entregó un "no hay ventaja" medido tres formas distintas, en vez de la regla bonita que el
  repo ya había shippeado una vez como celda de n=15.

**Cons:**
- Recorté comentarios 4 veces para que `gate.py` pasara su propio tope de líneas, en vez de
  partirlo. Raspar prosa para que un gate pase es cómo un gate deja de significar algo.
- Entregué `railway down -y` con `railway up` pegado debajo. Se corrieron los dos y el bot viejo
  volvió a producción a mandar alertas con el stop invertido.
- Afirmé que la ruptura salía plana "por la geometría" sin mirar su propio baseline, que con la
  misma geometría es positivo. Era el gate.
- Pusheé a `main` una vez sin leer el gate; quedó 21 líneas sobre presupuesto.

**Consejo Claude Code (cómo prompteamos mejor la próxima):**
- El brief de un agente debe decir **"si lanzas algo en fondo, reporta y termina; no esperes"**.
  Tres agentes hoy consumieron un turno cada uno para decir "sigo esperando".
- Los briefs que funcionaron traían el **defecto medido con su archivo:línea** pegado ("ETH a
  RSI 96.6 mientras la regla exige ≤30"). Los que decían "mejora X" salieron genéricos.
- Al pedir una búsqueda de parámetros, decir explícitamente **"reporta la distribución, no el
  ganador"** — un agente lo hizo bien sólo después de que se le dijo así.

**Patrón nuevo:** un módulo con la suite verde y **cero llamadores** no arregló nada. `knowledge/`
existió completo mientras el bug que venía a matar seguía vivo. Todo módulo nuevo cierra con un
grep de quién lo invoca; cero llamadores = no está terminado.

### 2026-08-24 · Las alertas de salida y por qué el pullback no dispara

**Pros (qué salió bien):**
- Ordenar los mensajes de Telegram por hora antes de tocar código: el spam de IREN
  (26 alertas) murió con el bot viejo el 21-ago a las 15:59, y el instrumento nuevo ya
  emite stops del lado correcto. Lo que quedaba vivo era el ARCHIVO heredado, no el
  proceso — y ahí sí estaban los tres defectos.
- El baseline se midió con worktree temporal en `HEAD`, no moviendo el árbol: 24 failed /
  16 errors idénticos antes y después, +9 passed míos. Sin eso, los fallos preexistentes
  de la suite (API key de Gemini al colectar) se habrían leído como daño propio.
- Convertir "el instrumento suprime todo" en 0.4% / 11.6% / 43.4% / 77.2% y 11 de 6,170
  barras. El 1.3 señales/semana concuerda con el 1.0 del backtest de 2 años que este
  mismo archivo ya tenía — dos corpus distintos sosteniéndose.

**Cons (qué se atoró o sobrecomplicó):**
- `railway link` es interactivo y no se puede correr desde aquí, así que la DB de
  producción quedó fuera de alcance. Se midió con yfinance como aproximación declarada,
  que sirve para el orden de magnitud pero no es el feed real del instrumento.

**Consejo Claude Code (cómo prompteamos mejor):**
- Ante "arregla X que está fallando", la primera pregunta no es dónde está el código:
  es **si eso sigue corriendo**. Aquí la respuesta cambió el trabajo entero.
- Al reportar un fix sobre una suite con fallos previos, medir el baseline en un
  worktree aparte y publicar los dos números. "9 tests pasan" no dice nada si 24
  fallaban antes y siguen fallando.

**Patrón nuevo capturado:**
- Marcar y luego limpiar borra la marca: `_mark_alert` seguido de `_clear_alert` dejaba
  el guard vacío en el siguiente ciclo. Un cierre debe conservar la marca terminal y
  tirar sólo lo intermedio.
