# Learning log — vigil / instrument

### 2026-08-23 · Las acciones entran al instrumento

**Pros (qué salió bien):**
- Se midió antes de recomendar, con el ciclo entero: disparos → resolución → baseline sin
  gates → partición temporal → separación por lado. El baseline (+0.026R sobre n=1,044) es
  el que convierte el +0.216R en un dato; sin él podría haber sido la deriva del mercado.
- `verify_fast.py` probó que el evaluador rápido reproduce `rules.evaluate` vela por vela
  ANTES de citar una sola cifra. Sin ese paso las 268 resoluciones no tenían derecho a
  existir.
- El bug del reloj (72 horas ≠ 72 velas cuando la bolsa cierra) se buscó en el segundo
  sitio después de arreglar el primero, y estaba: `scoreboard._count_orphans`.
- El criterio de retiro pasó de prosa a código el mismo día que se escribió. Un criterio
  en un `.md` se renegocia justo cuando toca aplicarlo.

**Cons (qué se atoró o sobrecomplicó):**
- **Un diagnóstico causal completo sobre n=13.** Publiqué "los huecos rebasan el stop, la
  geometría está rota" y escribí el código del arreglo. Con n=268 el MAE real era −0.78R
  (no −1.40R) y el arreglo salió idéntico a no hacer nada. Lo grave no es el número flojo:
  es que el mecanismo físico plausible lo blindó. Fernando decidió sobre eso.
- **Ocho variantes de un click fallido en el navegador**, ~25 turnos, cuando la regla #27
  dice saltar a la vía confiable a la segunda. Fernando lo cortó: *"esto está muy lento"*.
  Los pasos que le escribí los hizo en 30 segundos.
- **Perdí sus indicadores del chart** con un doble-click a ciegas. Se recuperaron por
  suerte (el layout no se había autoguardado), no por control.
- **El portapapeles se contaminó** entre `pbcopy` y `⌘V` con una URL de otra sesión suya,
  y la guardé como versión del script.

**Consejo Claude Code (cómo prompteamos mejor):**
- Cuando yo entregue un diagnóstico con explicación causal, la pregunta que más ahorra es
  **"¿con qué n?"**. Hoy la respuesta habría sido 13 y se habría cortado media hora de
  trabajo sobre un problema inexistente.
- Si me ves peleando con el navegador más de dos intentos, **"dame los pasos"** es más
  rápido que dejarme seguir. Funcionó hoy.

**Patrón nuevo capturado:**
- El portapapeles del sistema es estado compartido entre sesiones, igual que el stack de
  guardado temporal de git: verificar con `pbpaste | head -1` justo antes de pegar, no al
  copiar.

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
