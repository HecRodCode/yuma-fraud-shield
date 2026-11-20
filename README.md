# Yuma Shield

Real-time fraud prevention system for **Yuma Pay**, a fictional digital wallet. Prototype for the **EstudIA hackathon – Cybersecurity (Layer 2, intermediate level)**.

> Simulated case: all figures and conditions belong to a fictional scenario and all data is synthetic.

## Context

Yuma Pay detects fraud after the money has already left the account. Its current engine runs ~140 static rules over part of the operations in 15-minute batches, raises ~4,000 alerts per day of which 92 % are false positives, and analysts can only review a third of them. Decisions are not explained, and feedback from confirmed cases never flows back into the rules.

**Goal:** score the risk of every operation **before authorizing it** (< 300 ms, peaks of 150 TPS) by combining rules, machine learning, and behavior and device analysis; explain each decision and cut false positives without letting more fraud through.

Supporting documentation:

- [docs/yuma.pdf](docs/yuma.pdf) — original challenge statement.
- [docs/CONTEXT.md](docs/CONTEXT.md) — scope, architecture, decision logic, fraud types, data model and demo script (Spanish).

## How it works

```
Simulator ──REST──▶ Scoring API ──▶ rules ▶ features ▶ XGBoost ▶ SHAP ──▶ approve | challenge | hold
    │                   │
    └── events ──▶ Kafka ◀── decisions          PostgreSQL ──▶ Grafana (KPIs) · Analyst console
```

- Scoring is a **synchronous** call (`POST /score`); Kafka carries session/device events and decouples decision persistence.
- There is never an automatic permanent block: an analyst decides.
- A simulated "current" engine acts as the comparison baseline.

## Stack

Kafka (KRaft) · Kafka UI · PostgreSQL · Python + FastAPI · XGBoost + scikit-learn · SHAP · PaySim + custom generator · Streamlit · Grafana · k6 · Docker Compose.

## Layout

```
docs/        Challenge and scope
infra/       Postgres (schema), Kafka (topics), Grafana (provisioning)
services/    api, simulator, baseline, analyst_console
ml/          Training and retraining
data/        Local data (not versioned)
loadtest/    k6 load tests
config/      Rules and thresholds templates
```

## Running the environment

**Requirements:** Docker with Compose v2 and `make`.

```bash
make up        # creates .env and config/*.yaml from templates and starts the infrastructure
make ps        # service status
```

| Service | URL / port | Credentials |
|---------|------------|-------------|
| Grafana | http://localhost:3000 | `admin` / `GRAFANA_ADMIN_PASSWORD` from `.env` |
| Kafka UI | http://localhost:8080 | — |
| PostgreSQL | `localhost:5432` | `.env` |
| Kafka (external) | `localhost:29092` | — |

Host ports can be changed in `.env` (`POSTGRES_PORT`, `GRAFANA_PORT`, `KAFKA_UI_PORT`).

Other commands: `make psql` (SQL shell), `make topics` (list topics), `make logs`, `make down`, `make reset` (removes volumes and re-applies the schema).

The schema in [infra/postgres/init/01_schema.sql](infra/postgres/init/01_schema.sql) is applied on the first start of the volume. The `session-events` and `decisions` topics are created automatically.

## Configuration and confidentiality

The challenge forbids publishing rules and thresholds. `config/rules.yaml`, `config/thresholds.yaml` and `.env` are therefore git-ignored; the repository only holds `*.example.*` templates with dummy values. Data is not versioned either.

## Challenge constraints driving the design

- Synthetic data that never leaves the hackathon environment.
- Explainable and auditable decisions; no region, age or income used as model features.
- Permanent blocks only after human review; no extra friction for legitimate users.
- Encryption in transit and at rest; open-source components.
