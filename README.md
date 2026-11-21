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

services/baseline/baseline/  simulated current engine: static rules evaluated in 15-minute batches
services/simulator/simulator/control/  HTTP service that launches simulator jobs
ml/shield_ml/                feature definitions (shared with the API) and training
infra/postgres/init/         schema, compute_features SQL function and comparison view
infra/grafana/dashboards/    provisioned Grafana dashboard
```

## Running the environment

**Requirements:** Docker with Compose v2, `make`, `psql`, and a **local PostgreSQL** (not managed by compose) with a user allowed to create databases and roles.

```bash
cp .env.example .env     # set POSTGRES_HOST/PORT/USER/PASSWORD/DB for your local PostgreSQL
make db                  # creates the database if missing and (re)applies the schema
make seed                # generates a labeled synthetic history into PostgreSQL
make train               # trains the model and writes artifacts and config/thresholds.yaml
make up                  # starts Kafka, Kafka UI, Grafana, the API, the persister and the baseline
make evaluate            # scores the held-out transactions so both engines can be compared
```

The API starts without a model and answers 503 on `/score` until `make train` has run; it picks up new models and config files automatically.

`make db` is repeatable: it drops and recreates only the project tables.

Grafana and the simulator run with `network_mode: host` so they reach a PostgreSQL that listens only on `127.0.0.1`; `POSTGRES_HOST` must therefore be reachable from the host (default `localhost`).

| Service | URL / port | Credentials |
|---------|------------|-------------|
| Grafana | http://localhost:3000 | `admin` / `GRAFANA_ADMIN_PASSWORD` from `.env` |
| Scoring API docs (Swagger) | http://localhost:8000/docs (`POST /score`, `GET /health`) | — |
| Dashboard | http://localhost:3000/d/yuma-shield | Grafana login |
| Kafka UI | http://localhost:8080 | — |
| Kafka (external) | `localhost:29092` | — |

`make seed` accepts simulator options, e.g. `docker compose run --rm simulator history --accounts 10000 --days 90 --fraud-rate 0.005 --seed 7 --reset`.

Generating traffic against the API:

```bash
make live ARGS="--tps 20 --duration 30"                 # legitimate traffic
make attack TYPE=sim_swap ARGS="--speedup 60"           # account_takeover | sim_swap | mule_account | fake_qr
```

Attacks run their timeline compressed by `--speedup`, so a scenario that lasts 90 minutes in the history finishes in seconds.

The **baseline** service simulates the current engine as the case describes it: static rules (amount caps per channel, a night-time cap, a daily cumulative cap and a restricted-accounts list that is updated by hand after each incident) reviewed in 15-minute batches, with no behavior or device analysis. Its thresholds live in `config/baseline_rules.yaml` (not versioned) and are calibrated only to the ~92 % false-positive rate stated in the case. It evaluates every stored transaction, so both engines are compared on the same data.

`make evaluate` scores with Yuma Shield only the transactions the model did not see during training.

### Simulator control service

`control` exposes the simulator over HTTP (docs at http://localhost:8001/docs) so seeds, live traffic and attacks can be launched as background jobs, for example from the portal:

| Endpoint | What it does |
|----------|--------------|
| `POST /jobs/seed` | Generates a new labeled dataset (replacing the current one), waits for the baseline and scores everything with Yuma Shield. A different `seed` gives data the model has never seen. |
| `POST /jobs/live` | Sends legitimate traffic to the scoring API. |
| `POST /jobs/attack` | Launches one fraud scenario. |
| `GET /jobs`, `GET /jobs/{id}` | Job status and log. |

The scoring API also has `POST /admin/replay` (used by the seed job) at http://localhost:8000/docs.

### What is stored for every decision

Each Yuma Shield decision keeps the 21 feature values, the hard rules evaluated, the score, the reasons, the time spent per stage (features, model, total) and an audit trail (`scored` by the API, `persisted` by the consumer with Kafka topic, partition, offset and lag). Each baseline decision keeps the result of every static rule. This is what allows any transaction to be reconstructed and explained.

Other commands: `make psql` (SQL shell on the project database), `make topics`, `make logs`, `make ps`, `make down`. The `session-events` and `decisions` topics are created automatically.

## Configuration and confidentiality

The challenge forbids publishing rules and thresholds. `config/rules.yaml`, `config/thresholds.yaml` and `.env` are therefore git-ignored; the repository only holds `*.example.*` templates with dummy values. Data is not versioned either.

## Challenge constraints driving the design

- Synthetic data that never leaves the hackathon environment.
- Explainable and auditable decisions; no region, age or income used as model features.
- Permanent blocks only after human review; no extra friction for legitimate users.
- Encryption in transit and at rest; open-source components.
