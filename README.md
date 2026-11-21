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

## Code organization

```
services/api/app/            Scoring API (FastAPI)
  main.py                    app factory and lifespan
  api/routes/                HTTP endpoints (health, scoring) and dependencies
  schemas/                   request/response models
  services/                  scoring use case (rules, features, model, publish)
  domain/                    rules, thresholds, model wrapper, reason templates
  infra/                     PostgreSQL pool, Kafka publisher, repositories
  workers/persister.py       Kafka consumer that stores decisions and session events
  core/settings.py           environment and paths

services/simulator/simulator/
  cli.py                     command line entry point (history, live, attack)
  commands/                  one module per command
  generators/                population, legitimate traffic, history
  generators/fraud/          one module per fraud type (+ shared context)
  sinks/                     PostgreSQL, Kafka and scoring API clients
  domain/models.py           accounts, session events, transactions
  settings.py                environment

ml/shield_ml/                feature definitions (shared with the API) and training
infra/postgres/init/         schema and the compute_features SQL function
```

## Running the environment

**Requirements:** Docker with Compose v2, `make`, `psql`, and a **local PostgreSQL** (not managed by compose) with a user allowed to create databases and roles.

```bash
cp .env.example .env     # set POSTGRES_HOST/PORT/USER/PASSWORD/DB for your local PostgreSQL
make db                  # creates the database if missing and (re)applies the schema
make seed                # generates a labeled synthetic history into PostgreSQL
make up                  # starts Kafka, Kafka UI, Grafana, the scoring API and the persister
make train               # trains the model and writes artifacts and config/thresholds.yaml
```

The API starts without a model and answers 503 on `/score` until `make train` has run; it picks up new models and config files automatically.

`make db` is repeatable: it drops and recreates only the project tables.

Grafana and the simulator run with `network_mode: host` so they reach a PostgreSQL that listens only on `127.0.0.1`; `POSTGRES_HOST` must therefore be reachable from the host (default `localhost`).

| Service | URL / port | Credentials |
|---------|------------|-------------|
| Grafana | http://localhost:3000 | `admin` / `GRAFANA_ADMIN_PASSWORD` from `.env` |
| Scoring API | http://localhost:8000/docs (`POST /score`) | — |
| Kafka UI | http://localhost:8080 | — |
| Kafka (external) | `localhost:29092` | — |

`make seed` accepts simulator options, e.g. `docker compose run --rm simulator history --accounts 10000 --days 90 --fraud-rate 0.005 --seed 7 --reset`.

Generating traffic against the API:

```bash
make live ARGS="--tps 20 --duration 30"                 # legitimate traffic
make attack TYPE=sim_swap ARGS="--speedup 60"           # account_takeover | sim_swap | mule_account | fake_qr
```

Attacks run their timeline compressed by `--speedup`, so a scenario that lasts 90 minutes in the history finishes in seconds.

Other commands: `make psql` (SQL shell on the project database), `make topics`, `make logs`, `make ps`, `make down`. The `session-events` and `decisions` topics are created automatically.

## Configuration and confidentiality

The challenge forbids publishing rules and thresholds. `config/rules.yaml`, `config/thresholds.yaml` and `.env` are therefore git-ignored; the repository only holds `*.example.*` templates with dummy values. Data is not versioned either.

## Challenge constraints driving the design

- Synthetic data that never leaves the hackathon environment.
- Explainable and auditable decisions; no region, age or income used as model features.
- Permanent blocks only after human review; no extra friction for legitimate users.
- Encryption in transit and at rest; open-source components.
