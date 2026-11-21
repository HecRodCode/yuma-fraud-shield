# Yuma Shield

Sistema antifraude en tiempo real para **Yuma Pay**, una billetera digital ficticia. Prototipo para la **hackatón EstudIA – Ciberseguridad (Capa 2, nivel intermedio)**.

> Caso simulado: todas las cifras, condiciones y datos pertenecen a un escenario ficticio.

## Contexto

Yuma Pay detecta el fraude cuando el dinero ya salió de la cuenta. Su motor actual aplica reglas estáticas a una parte de las operaciones, por lotes cada 15 minutos, genera miles de alertas al día de las que cerca del 90 % son falsos positivos, y los analistas solo alcanzan a revisar un tercio. Las decisiones no se explican y la retroalimentación de los casos confirmados nunca vuelve a las reglas.

**Objetivo:** calificar el riesgo de cada operación **antes de autorizarla** (< 300 ms, picos de 150 TPS) combinando reglas, aprendizaje automático y análisis de comportamiento y dispositivo; explicar cada decisión y reducir los falsos positivos sin dejar pasar más fraude. La decisión es una de `approve` (aprobar), `challenge` (desafiar), `hold` (retener) o `reject` (rechazar).

Documentación de apoyo:

- [docs/yuma.pdf](docs/yuma.pdf) — enunciado original del reto.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — componentes, vida de una transacción, bandas de decisión, ciclo de retroalimentación, modelo de datos y brechas conocidas (diagramas Mermaid).
- [loadtest/RESULTS.md](loadtest/RESULTS.md) — prueba de carga a 150 TPS.
- [docs/CONTEXT.md](docs/CONTEXT.md) — notas iniciales de alcance (superadas por el documento de arquitectura).
- El **paquete del caso** (datos, reglas vigentes, API sandbox, diagramas) debe estar en `docs/Caso_de_estudio_Yuma_Pay/`. Es confidencial y está en `.gitignore`.

## Cómo funciona

```
Sandbox / cliente ──▶ API de scoring ──▶ reglas duras ▶ features de historial (PostgreSQL) ▶ XGBoost ▶ SHAP
                           │                                      │
                           ▼                                      ▼
                         Kafka ──▶ persister ──▶ PostgreSQL ◀── línea base (motor actual, lotes de 15 min)
                                                     │
                                            Grafana · portal del analista
```

1. Una transacción llega a `POST /score`.
2. Primero se revisan las reglas duras (destinos restringidos, topes de monto por operación).
3. La función SQL `compute_features` lee el historial del cliente (operaciones, eventos de sesión, dispositivos, dinero recibido) estrictamente **antes** de la operación, de modo que no se usa información del futuro.
4. XGBoost devuelve un puntaje; SHAP da la contribución de cada variable y las principales se convierten en razones en lenguaje claro.
5. Los umbrales convierten el puntaje en `approve`, `challenge`, `hold` o `reject`.
6. La decisión, los valores de las más de 21 variables, las reglas evaluadas y los tiempos se publican en Kafka; el persister los guarda con un rastro de auditoría (tiempo de la API, partición y offset de Kafka, retraso).
7. El servicio **baseline** aplica las 12 reglas vigentes oficiales a las mismas transacciones, en lotes de 15 minutos.

El entrenamiento y el servicio usan la misma función SQL y el mismo código Python de variables, por lo que no pueden desalinearse. El entrenamiento es temporal: mayo–agosto para entrenar, septiembre para calibrar los umbrales y octubre como prueba final.

## Stack

Kafka (KRaft) · Kafka UI · PostgreSQL · Python + FastAPI · XGBoost + scikit-learn · SHAP · Streamlit · Grafana · Docker Compose.

## Organización del código

```
services/api/app/            API de scoring (FastAPI)
  api/routes/                endpoints HTTP (health, scoring, admin)
  schemas/                   modelos de petición y respuesta
  services/                  caso de uso de scoring y reentrenamiento
  domain/                    reglas, umbrales, envoltorio del modelo, plantillas de razones
  infra/                     pool de PostgreSQL, publicador de Kafka, repositorios
  workers/                   persister (consumidor de Kafka) y replay (scoring masivo)
services/baseline/           el motor actual: 12 reglas estáticas en lotes de 15 minutos
services/simulator/          simulador de tráfico y ataques, conector del sandbox y servicio de control HTTP
services/portal/             portal Streamlit: comparar motores, explorar transacciones, cola del analista, control
ml/shield_ml/                definición de variables, cargador de datos del caso, entrenamiento, auditoría de equidad, registro de modelos
infra/postgres/init/         esquema, función SQL compute_features, vista de comparación
infra/grafana/               fuente de datos y dashboard aprovisionados
config/                      plantillas de reglas, umbrales y parámetros de la línea base
```

## Cómo ejecutar el entorno

**Requisitos:** Docker con Compose v2, `make`, `psql`, un **PostgreSQL local** con un usuario que pueda crear bases de datos y roles, y el paquete del caso en `docs/Caso_de_estudio_Yuma_Pay/`.

```bash
cp .env.example .env     # define POSTGRES_HOST/PORT/USER/PASSWORD/DB de tu PostgreSQL local
make db                  # crea la base si falta y (re)aplica el esquema
make load                # carga los datos del caso (clientes, eventos, transacciones, reglas y alertas históricas)
make up                  # Kafka, Kafka UI, Grafana, API, persister, baseline, portal y servicio de control
make train               # entrena el modelo, escribe los artefactos y config/thresholds.yaml
make sandbox             # levanta la API sandbox del caso
make sandbox-run ARGS="--reset"   # decide el periodo de prueba a través del sandbox e imprime sus indicadores
```

Luego abre el portal en http://localhost:8501.

La API arranca sin modelo y responde 503 en `/score` hasta que se ejecuta `make train`; recoge solos los modelos y archivos de configuración nuevos. La línea base necesita unos minutos para evaluar todo el historial después de `make up`.

| Servicio | URL | Notas |
|----------|-----|-------|
| Documentación de la API (Swagger) | http://localhost:8000/docs | `POST /score`, `GET /health`, endpoints `/admin` |
| Portal | http://localhost:8501 | comparar motores, explorador de transacciones, cola del analista, control |
| Dashboard | http://localhost:3000/d/yuma-shield | usuario y clave de Grafana en `.env` |
| Control del simulador | http://localhost:8001/docs | lanza tráfico, ataques y corridas del sandbox |
| Kafka UI | http://localhost:8080 | topics `decisions`, `session-events` |
| Sandbox del caso | http://localhost:8090/v1/metricas | indicadores oficiales |

Los puertos del host se cambian en `.env`. Grafana y los workers corren con `network_mode: host` para poder alcanzar un PostgreSQL que solo escucha en `127.0.0.1`.

Tráfico y ataques (también disponibles en la página Control del portal):

```bash
make live ARGS="--tps 10 --duration 30"
make attack TYPE=sim_swap ARGS="--speedup 600"   # account_takeover | sim_swap | social_engineering | qr_scam | mule_account
```

Las operaciones simuladas usan un **reloj virtual** que continúa después de la última transacción del dataset (31 de octubre), para que el modelo vea tiempos realistas; `--speedup` es el número de segundos virtuales por segundo real. Los ataques son aproximaciones hechas a mano de los cinco tipos de fraude del caso, ejecutadas sobre clientes reales del dataset.

Prueba de carga (k6, 150 TPS sostenidos 60 s más un pico de 200 TPS):

```bash
make loadtest-data   # construye las peticiones con operaciones de octubre (ignoradas por git)
make loadtest        # ejecuta k6; umbrales: p95 < 300 ms, errores < 1 %
make loadtest-clean  # borra las operaciones LT-* que creó
```

Otros comandos: `make evaluate` (puntúa en bloque las transacciones reservadas que no tienen decisión), `make psql`, `make topics`, `make logs`, `make ps`, `make down`.

### Reportes generados

- `ml/artifacts/meta.json` — versión del modelo, particiones, métricas de validación y prueba, importancia global de variables.
- `ml/artifacts/fairness.json` — tasas de bloqueo y marcación por departamento y rango de edad (estos atributos nunca son variables del modelo; solo se usan para auditar).
- `ml/artifacts/sandbox_report.json` — indicadores que devuelve el sandbox del caso para el periodo decidido.

### Ciclo de retroalimentación y versiones del modelo

Los analistas confirman o liberan alertas en el portal, y servicio al cliente puede reportar fraude que fue aprobado (una reclamación de cliente). Ambos se guardan en `labels`. `POST /admin/retrain` (o la página Control del portal) entrena una versión nueva con esas etiquetas: las operaciones simuladas después del periodo del dataset cuentan como legítimas salvo que una etiqueta diga otra cosa, y las etiquetas sobre el mes de prueba de octubre se guardan pero nunca se usan para entrenar.

Cada versión se guarda en `ml/artifacts/models/<versión>/` y se registra en `model_versions`. Una **compuerta de promoción** publica un modelo nuevo solo si, en la prueba limpia de octubre, el fraude detectado no cae más de 1 punto porcentual, los falsos positivos no suben más de 5 puntos y los clientes legítimos bloqueados no suben más de 0,5 puntos. De lo contrario, la versión queda como `rejected`. `POST /admin/models/{version}/promote` vuelve a cualquier versión guardada. `FEEDBACK_WEIGHT` (por defecto 2) controla cuánto pesan las etiquetas de retroalimentación.

### Qué se guarda de cada decisión

Los valores de las variables, las reglas duras evaluadas, el puntaje, las razones, el tiempo de cada etapa y un rastro de auditoría (`scored` por la API, `persisted` por el consumidor con topic, partición, offset y retraso de Kafka). Cada decisión de la línea base guarda las reglas vigentes que se activaron.

## Configuración y confidencialidad

El reto prohíbe publicar reglas y umbrales. `config/rules.yaml`, `config/thresholds.yaml`, `config/baseline_rules.yaml` y `.env` están en `.gitignore`; el repositorio solo contiene las plantillas `*.example.*` con valores ficticios. El paquete del caso y los datos también están ignorados por git.

## Restricciones del reto que guían el diseño

- Decisión en < 300 ms con picos de 150 TPS.
- Sin información del futuro: solo se usan datos anteriores a la operación.
- Decisiones explicables y auditables; sin usar región, edad ni ingresos como variables del modelo, y con una auditoría de equidad por segmento.
- Bloqueos definitivos solo tras revisión humana; sin fricción adicional para el cliente legítimo.
- Cifrado en tránsito y en reposo; componentes de código abierto.
