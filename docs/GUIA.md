# Yuma Shield en lenguaje claro

> **Versión con imágenes:** abre [GUIA.html](GUIA.html) en el navegador. Esta página dice lo mismo en texto.
> Detalle técnico: [ARCHITECTURE.md](ARCHITECTURE.md).

## 1. Qué problema resolvemos

Una transferencia inmediata se completa en segundos y no se puede reversar. El motor actual de Yuma Pay revisa por lotes cada 15 minutos, así que cuando alerta, el dinero ya salió. Además, cerca del 92 % de sus alertas son falsas, y los 12 analistas solo alcanzan a revisar una de cada tres.

```
HOY             cliente confirma → el dinero sale → (hasta 15 min) → alerta tardía, casi siempre falsa
CON SHIELD      cliente confirma → Shield decide en ~0,02 s → solo sale lo aprobado
```

## 2. Qué pasa cuando alguien hace una transferencia

**¿La operación se queda esperando a que un analista la apruebe? No.** La decisión la toma el sistema solo, en milisegundos. Solo cuando el sistema frena una operación interviene un analista, y para esas el dinero no sale mientras tanto.

```
Cliente confirma ──► Yuma Shield (< 300 ms, sin personas) ──┬─► Aprobar    (96,2 %)
                                                            ├─► Desafiar   ( 2,4 %)
                                                            ├─► Retener    ( 0,4 %)
                                                            └─► Rechazar   ( 1,1 %)
```

| Decisión | Qué ve el cliente | Qué pasa con el dinero | Quién interviene |
|----------|-------------------|------------------------|------------------|
| **Aprobar** | Nada: se completa | Sale normalmente | Nadie |
| **Desafiar** | La app pide una verificación extra (biometría o código) | Sale si la supera; si no, el caso pasa a un analista | El propio cliente, en segundos |
| **Retener** | "Estamos verificando tu operación" | **No sale** mientras se revisa | Un analista, que confirma con el cliente |
| **Rechazar** | La operación no se realiza | **No sale** | Un analista revisa el caso después |

*Los porcentajes son de las 21.600 operaciones de octubre.*

- **Retener vs. rechazar:** retener es "tengo sospechas, dejo la operación en pausa"; rechazar es "casi seguro es fraude, la niego". En ambos casos se abre un caso para un analista.
- **Si el sistema se equivoca con un cliente real:** el analista lo contacta y **libera** la operación. Es un costo real (el cliente espera), y por eso el sistema busca frenar muy pocos legítimos: el 0,4 % en octubre.
- **Qué construimos y qué no:** el prototipo decide, abre el caso y registra el veredicto del analista. Completar de nuevo una operación liberada o pedir de verdad la biometría le corresponde al sistema central de pagos de Yuma, que no es parte de este proyecto.

## 3. Cómo decide en menos de 300 ms

En esos milisegundos no hay personas ni llamadas lentas. Solo se hace lo necesario para decidir; todo lo demás ocurre después de responder.

```
ANTES DE RESPONDER (4–6 ms)                      DESPUÉS DE RESPONDER (no hace esperar a nadie)
1. Revisa las reglas duras                        1. Publica la decisión en Kafka
2. Lee el historial del cliente   (~1,5 ms)       2. El persister la guarda en la base de datos
3. El modelo calcula el puntaje   (~2,5 ms)       3. Se anota en el registro de auditoría
4. Elige la decisión y las razones                4. El motor actual la evalúa en su lote
```

Prueba de carga: 150 transacciones por segundo sostenidas 60 segundos y un pico de 200. Respuesta p95 de 10 ms (el 95 % de las respuestas tardó 10 ms o menos), 0 errores.

## 4. Qué revisa Yuma Shield

### Primera capa: las reglas duras

Son reglas fijas de "esto nunca debe pasar". Si saltan, se decide al instante y ni siquiera se consulta al modelo. Hay dos:

| Regla dura | Qué comprueba | Decisión | Ejemplo |
|-----------|---------------|----------|---------|
| **Destino restringido** | ¿El dinero va a una cuenta de una lista de cuentas reportadas? | Rechazar | En el prototipo la lista está vacía: no tenemos una real |
| **Tope de monto** | ¿El monto supera el máximo permitido para ese tipo de operación? | Retener | En octubre se activó 2 veces: retiros de cajero de COP 5,3 y 6,9 millones |

Los topes están en un archivo de configuración que no se publica (el reto prohíbe publicar reglas y umbrales).

### Segunda capa: el modelo

Mira 46 datos, todos **anteriores** a la operación, y los agrupa en cinco temas:

1. **La operación:** monto, qué porcentaje del saldo es, tipo, hora y día.
2. **El dispositivo y la sesión:** ¿dispositivo nuevo?, inicios de sesión fallidos, cambio de clave o de SIM recientes, conexión desde fuera de su zona habitual.
3. **El hábito del cliente:** cuántas operaciones hizo en los últimos 10 minutos y en la última hora, su monto promedio de 30 días.
4. **El destino:** ¿es la primera vez que le paga?, ¿cuántos clientes distintos le pagaron en la última hora?, ¿qué antigüedad tiene la cuenta?
5. **El dinero que el cliente recibió:** cuánto y de cuántas personas distintas (señal típica de las cuentas "mula").

**Lo que NO mira:** departamento, edad ni ingresos del cliente, ni si la operación fue fraude (esa etiqueta solo se usa para entrenar y medir).

El modelo devuelve un puntaje de 0 a 1. Según el puntaje se elige la decisión, y el sistema escribe **las tres razones que más pesaron** en lenguaje claro, por ejemplo: "Primera operación a este destino en 180 días", "3 inicios de sesión fallidos en 24 horas", "Dispositivo registrado hace 14 minutos".

### Comparación: el motor actual

Son 12 reglas fijas: transferencia de monto alto, dispositivo nuevo, operación de madrugada, velocidad de salidas, vaciado de saldo a destino nuevo, cambio de clave reciente, cambio de SIM reciente, cuenta reciente con retiros, ubicación atípica, acumulado diario, pago QR de monto alto y retiro de monto alto. Casi todas exigen además que el monto supere un mínimo, así que un fraude de monto moderado puede no activar ninguna. El modelo mira la **secuencia completa**.

## 5. El analista

- **Quién es:** una persona del equipo de Prevención de Fraude. Hoy hay 12 para unas 4.000 alertas diarias.
- **Qué decide:** confirma el fraude o libera la operación frenada. Es la **única** figura que puede decidir el bloqueo definitivo de una cuenta; el sistema nunca la cierra solo.
- **Qué ve:** en el portal (*Analyst queue*), una lista ordenada del caso más riesgoso al menos riesgoso. Al abrir un caso ve el monto, el cliente y las razones. Dos botones: **Confirmar fraude** o **Liberar**.
- **Qué pasa después:** el veredicto queda guardado y mejora al modelo en el próximo entrenamiento.

```
Shield frena → llega a la cola → el analista revisa → veredicto → el modelo aprende
```

**La carga en octubre:** el motor actual generó 1.743 alertas y solo 137 (8 de cada 100) eran fraude. Yuma Shield pasó 315 casos al analista y 231 (73 de cada 100) eran fraude: unas 5,5 veces menos trabajo.

## 6. Un caso real: `T00117063`

Puedes abrirlo en el portal: *Explorer → buscar T00117063*.

```
Antes de operar   3 inicios de sesión fallidos
≈ 21:56–22:00     se registra un dispositivo nuevo
≈ 22:06           cambian la clave
22:14             transfieren COP 132.300 (63 % del saldo) a una cuenta Yuma nueva
```

- **Motor actual:** ninguna de sus 12 reglas se activa, porque el monto está por debajo de los mínimos de las reglas de dispositivo nuevo y cambio de clave. La operación se autoriza y el fraude se completa.
- **Yuma Shield:** **rechaza** (puntaje 1,00) en unos 20 ms, con tres razones. El dinero no sale y el caso llega a un analista.

Ninguna señal por sí sola era concluyente: lo que delata el fraude es la **secuencia**. En octubre hubo 244 fraudes; en 105 de ellos (43 %) el motor actual no dijo nada y Yuma Shield sí.

## 7. Resultados (octubre, sandbox oficial)

| Indicador | Yuma Shield | Motor actual |
|-----------|-------------|--------------|
| Fraude detectado | 98,8 % | 56,1 % (62,6 % en la muestra completa) |
| Falsos positivos (meta < 60 %) | 25,9 % | 92,1 % (89,0 % en la muestra completa) |
| Clientes legítimos frenados | 0,4 % | — |
| Legítimos con verificación extra | 2,3 % | — |

**Con honestidad:** los datos son sintéticos y la muestra tiene 1,41 % de fraude (en la realidad, ~0,01 %). Con tan poco fraude real los falsos positivos subirían mucho para cualquier motor. Estas cifras demuestran que la arquitectura funciona, no que el modelo rinda igual con datos reales.

## 8. Para qué sirve cada pieza

| Pieza | Para qué sirve | Dónde verla |
|-------|----------------|-------------|
| **API de scoring** | Recibe la operación y devuelve la decisión; es lo único dentro de los 300 ms | `localhost:8000/docs` |
| **El modelo** | Calcula el puntaje y explica qué datos pesaron | Portal → Control |
| **PostgreSQL** | La memoria: historial, decisiones, alertas, auditoría y versiones del modelo | Portal → Explorer |
| **Kafka + persister** | Canal de mensajes y el programa que guarda las decisiones sin hacer esperar al cliente | `localhost:8080` |
| **Motor actual (baseline)** | Reproduce las 12 reglas para tener contra qué comparar | Explorer → pestaña *Current engine* |
| **Portal y Grafana** | Comparar, explorar una operación, trabajar la cola, controlar la demo | `localhost:8501`, `localhost:3000` |
| **Entrenamiento y compuerta** | Enseña al modelo; un modelo nuevo solo se activa si no empeora el actual, y se puede volver atrás | Portal → Control |
| **Sandbox del caso** | API oficial del reto: entrega operaciones y calcula los indicadores | `localhost:8090/v1/metricas` |
| **Simulador** | Lanza tráfico normal y cinco tipos de ataque para la demo | Portal → Control |
| **Prueba de carga (k6)** | Demuestra los 150 TPS | `make loadtest` |

## 9. Cómo se levanta

**Necesitas:** Linux con Docker, `make` y `psql`; un PostgreSQL local con un usuario que pueda crear bases; el paquete del caso copiado en `docs/Caso_de_estudio_Yuma_Pay/`; y los puertos 8000, 8001, 8080, 8090, 8501, 3000 y 29092 libres.

**Camino rápido:** copia `.env.example` a `.env` y ajusta tu base de datos, ejecuta `make setup`, llena `config/baseline_rules.yaml` con los valores de `reglas_vigentes.csv` y ejecuta `make bootstrap` (unos 15 minutos).

| # | Paso | Qué debes ver |
|---|------|---------------|
| 1 | `make db` | Sin errores |
| 2 | `make load` (~1 min) | customers 6000 · session_events 48281 · transactions 120972 · legacy_rules 12 · legacy_alerts 9687 |
| 3 | `make up` (3–5 min) | `make ps` con todo en "Up" |
| 4 | Esperar al motor actual (~3 min) | 9.687 alertas, igual que el caso |
| 5 | `make train` (~3 min) | "gate passed: True" y fraude detectado ≈ 98,8 % |
| 6 | `make sandbox` | `localhost:8090/v1/salud` responde "ok" |
| 7 | `make sandbox-run ARGS="--reset"` (~2 min) | 21.600 decididas y falsos positivos ≈ 26 % |

Cuando termine, abre el portal en `localhost:8501`.

| Si ves... | Haz esto |
|-----------|----------|
| `password authentication failed` | Revisa usuario y clave de PostgreSQL en `.env` |
| Puerto ocupado | Cámbialo en `.env` (el 5432 suele estar ocupado si tienes otro PostgreSQL) |
| `/score` responde 503 | Falta `make train` |
| El motor actual alerta todo o nada | `config/baseline_rules.yaml` está vacío o mal llenado |
| No funciona en Mac o Windows | Los servicios usan la red del equipo, que solo funciona bien en Linux |

`make logs` muestra lo que pasa por dentro; `make db` borra todo y reinicia.

## 10. Cómo contarlo

**En 30 segundos:** "Yuma Pay se entera del fraude cuando el dinero ya salió. Yuma Shield decide antes, en menos de 300 milisegundos, mirando el comportamiento del cliente y su dispositivo, y explica cada decisión. En el mes de prueba detecta casi todo el fraude con una cuarta parte de falsos positivos, frente a casi el 90 % del motor actual. Y los casos dudosos los decide siempre una persona."

**En 5 minutos:** el problema (1 min) → la idea con las cuatro respuestas (1 min) → la demo: una operación explicada, un ataque y la cola del analista (1,5 min) → la evidencia (1 min) → límites y siguientes pasos (0,5 min).

**Preguntas probables**

- **¿Por qué los números son tan buenos?** Los datos son sintéticos y los patrones de fraude son claros. Se evaluó en un mes que el modelo no vio, pero eso no garantiza el mismo resultado con fraude real.
- **¿Por qué el motor actual detecta menos?** Sus reglas miran el monto de una operación aislada; mucho fraude es de montos moderados y lo delata la secuencia.
- **¿La operación espera al analista?** No. El sistema decide solo en milisegundos; el analista solo recibe los casos frenados (≈ 1,5 %).
- **¿Cómo se evita discriminar?** El modelo no recibe departamento, edad ni ingresos, y se audita el trato por grupo. Un punto a vigilar es la señal de conexión fuera de la zona habitual, que compara con la zona del propio cliente y no con una región.
- **¿Se puede auditar una decisión?** Sí: para cada una se guardan los datos que se miraron, las reglas evaluadas, las razones, los tiempos y un registro que no permite modificaciones.
- **¿Y si el modelo se equivoca?** El cliente pasa una verificación extra, o un analista lo revisa y lo libera. El sistema nunca cierra una cuenta solo.
- **¿Está cifrado?** Todavía no: es una brecha declarada. En producción serían conexiones cifradas y almacenamiento cifrado.
- **¿Escala a 1,8 millones de operaciones al día?** Son unas 21 por segundo de media, con picos de 150. Probamos 150 sostenidas y 200 de pico en un solo equipo sin saturar; la pieza a vigilar es la base de datos.
- **¿El feedback del analista mejora el modelo?** El mecanismo funciona. En una prueba con ataques simulados el modelo reentrenado empeoró la precisión general y la compuerta lo rechazó. Con fraude real el feedback vendría de la misma distribución que se evalúa.

El guion de la demo en vivo queda para el final.
