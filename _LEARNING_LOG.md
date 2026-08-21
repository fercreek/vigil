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
