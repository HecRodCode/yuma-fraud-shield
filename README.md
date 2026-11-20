# Escudo Yuma

Sistema antifraude en tiempo real para **Yuma Pay** (billetera digital ficticia). Proyecto para la hackatón **EstudIA – Ciberseguridad, Capa 2, nivel intermedio**.

> Caso simulado: todas las cifras y condiciones son de un escenario ficticio. Solo se usan datos sintéticos.

## El reto en una línea

Calificar el riesgo de cada operación **antes de autorizarla, en < 300 ms y a 150 TPS**, combinando reglas, ML y comportamiento/dispositivo, con decisiones **explicables**, bajando los falsos positivos de **92 % a < 60 %** sin dejar pasar más fraude.

## Qué resolvemos

| # | Problema | Solución del MVP |
|---|----------|------------------|
| P1 | Fraude detectado después de que el dinero salió | Scoring síncrono previo a autorizar (< 300 ms) |
| P2 | 92 % de falsos positivos | Modelo + comportamiento + dispositivo; cola priorizada por riesgo |
| P3 | Decisiones sin explicación ni feedback | Razones en lenguaje claro (SHAP) + feedback del analista que reentrena |

Alcance completo, arquitectura, decisiones y guion de demo: [docs/CONTEXT.md](docs/CONTEXT.md). Enunciado original: [docs/yuma.pdf](docs/yuma.pdf).

## Arquitectura (resumen)

Simulador → **API FastAPI** (`POST /score`, síncrono) → reglas → features (Postgres) → XGBoost → SHAP → decisión **aprobar / fricción / retener**. Las decisiones y eventos de sesión viajan por **Kafka** hacia **PostgreSQL**; **Grafana** muestra KPIs y **Streamlit** es la consola del analista. Un motor "actual" simulado sirve de línea base.

## Stack

Kafka (KRaft) · Kafka UI · PostgreSQL · Python/FastAPI · XGBoost + scikit-learn · SHAP · PaySim + generador propio · Streamlit · Grafana · k6 · Docker Compose.

## Estructura del repositorio

```
docs/                 Enunciado del reto y CONTEXT.md (alcance y stack)
infra/                postgres (esquema), kafka, grafana (provisioning y dashboards)
services/
  api/                API de scoring (FastAPI)
  simulator/          Generador de tráfico, sesión y las 4 modalidades de fraude
  baseline/           Motor actual simulado (línea base)
  analyst_console/    Consola del analista (Streamlit)
ml/                   Entrenamiento, reentrenamiento, notebooks y artefactos (no versionados)
data/                 raw (PaySim) y synthetic — no versionados
loadtest/             Pruebas de carga k6
config/               Ejemplos de reglas y umbrales (los reales NO se versionan)
tests/  scripts/      Pruebas y utilidades
```

## Plan por fases

| Fase | Entregable | Estado |
|------|-----------|--------|
| 1 | Docker Compose (Kafka, Postgres, Grafana) + esquema de tablas | ☐ |
| 2 | Simulador: transacciones, sesión y 4 modalidades | ☐ |
| 3 | Scoring: reglas, features, XGBoost, SHAP | ☐ |
| 4 | Línea base + dashboard Grafana | ☐ |
| 5 | Consola del analista + feedback/reentrenamiento | ☐ |
| 6 | Prueba de carga k6 + ensayo de demo | ☐ |

Regla de corte: las fases 1–4 ya cuentan la historia completa; la 5 cierra explicabilidad y feedback; la 6 valida requisitos técnicos.

## Métricas de éxito

p95 < 300 ms · 150 TPS sostenidos · falsos positivos < 60 % · fraude detectado ≥ línea base · 100 % de decisiones con explicación · fricción al legítimo menor que la línea base.

*Honestidad:* con datos sintéticos las métricas demuestran viabilidad de la arquitectura, no generalización a datos reales.

## Restricciones del caso a respetar

- **Reglas y umbrales no se publican**: viven en `config/*.yaml` (ignorados por git); solo hay `*.example.yaml`.
- Datos sintéticos, sin salir del entorno de la hackatón.
- Bloqueo definitivo **solo** por decisión de un analista.
- No usar región, edad ni ingresos en el modelo; verificar equidad por segmento.
- Cifrado en tránsito (TLS) y en reposo; todo open source.

## Arranque (se completará en la Fase 1)

```bash
cp .env.example .env
cp config/thresholds.example.yaml config/thresholds.yaml
cp config/rules.example.yaml config/rules.yaml
docker compose up
```
