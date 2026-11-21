# Yuma Shield

Real-time fraud prevention system for **Yuma Pay**, a fictional digital wallet. Prototype for the **EstudIA hackathon – Cybersecurity (Layer 2, intermediate level)**.

> Simulated case: all figures, conditions and data belong to a fictional scenario.

## Context

Yuma Pay detects fraud after the money has already left the account. Its current engine applies static rules to part of the operations in 15-minute batches, raises thousands of alerts per day of which ~90 % are false positives, and analysts can only review a third of them. Decisions are not explained, and feedback from confirmed cases never flows back into the rules.

**Goal:** score the risk of every operation **before authorizing it** (< 300 ms, peaks of 150 TPS) by combining rules, machine learning and behavior and device analysis; explain each decision and cut false positives without letting more fraud through. The decision is one of `approve`, `challenge`, `hold` or `reject`.

Supporting documentation:

- [docs/yuma.pdf](docs/yuma.pdf) — original challenge statement.
- [docs/CONTEXT.md](docs/CONTEXT.md) — initial scope and architecture notes (Spanish, partly superseded by this README).
- The **case package** (data, current rules, sandbox API, diagrams) is expected in `docs/Caso_de_estudio_Yuma_Pay/`. It is confidential and git-ignored.

## How it works

```
Sandbox / client ──▶ Scoring API ──▶ hard rules ▶ history features (PostgreSQL) ▶ XGBoost ▶ SHAP
                         │                                   │
                         ▼                                   ▼
                       Kafka ──▶ persister ──▶ PostgreSQL ◀── baseline (current engine, 15-min batches)
                                                   │
                                          Grafana · analyst portal
```

1. A transaction arrives at `POST /score`.
2. Hard rules (restricted destinations, amount caps per operation) are checked first.
3. The SQL function `compute_features` reads the customer's history (operations, session events, devices, money received) strictly **before** the operation, so no future information is used.
4. XGBoost returns a score; SHAP gives each feature's contribution; the top ones become plain-language reasons.
5. Thresholds turn the score into `approve`, `challenge`, `hold` or `reject`.
6. The decision, the 21+ feature values, the rules evaluated and the timings are published to Kafka; the persister stores them with an audit trail (API time, Kafka partition/offset, lag).
7. The **baseline** service applies the 12 official legacy rules to the same transactions, in 15-minute batches.

Training and serving use the same SQL function and the same Python feature code, so they cannot drift apart. Training is time-based: May–August to train, September to calibrate thresholds, October as the final test.

## Stack

Kafka (KRaft) · Kafka UI · PostgreSQL · Python + FastAPI · XGBoost + scikit-learn · SHAP · Streamlit · Grafana · Docker Compose.

## Code organization

```
services/api/app/            Scoring API (FastAPI)
  api/routes/                HTTP endpoints (health, scoring, admin)
  schemas/                   request/response models
  services/                  scoring use case
  domain/                    rules, thresholds, model wrapper, reason templates
  infra/                     PostgreSQL pool, Kafka publisher, repositories
  workers/                   persister (Kafka consumer) and replay (bulk scoring)
services/baseline/           the legacy engine: 12 static rules in 15-minute batches
services/simulator/          traffic and attack simulator, sandbox connector and HTTP control service
services/portal/             Streamlit portal: compare engines, explore transactions, analyst queue, control
ml/shield_ml/                feature definitions, case data loader, training, fairness audit
infra/postgres/init/         schema, compute_features SQL function, comparison view
infra/grafana/               provisioned datasource and dashboard
config/                      templates for rules, thresholds and baseline parameters
```

## Running the environment

**Requirements:** Docker with Compose v2, `make`, `psql`, a **local PostgreSQL** with a user allowed to create databases and roles, and the case package in `docs/Caso_de_estudio_Yuma_Pay/`.

```bash
cp .env.example .env     # set POSTGRES_HOST/PORT/USER/PASSWORD/DB for your local PostgreSQL
make db                  # creates the database if missing and (re)applies the schema
make load                # loads the case data (customers, events, transactions, legacy rules/alerts)
make up                  # Kafka, Kafka UI, Grafana, API, persister and baseline
make train               # trains the model, writes artifacts and config/thresholds.yaml
make sandbox             # starts the case sandbox API
make sandbox-run ARGS="--reset"   # decides the test period through the sandbox and prints its indicators
```

Then open the portal at http://localhost:8501.

The API starts without a model and answers 503 on `/score` until `make train` has run; it picks up new models and config files automatically. The baseline needs a few minutes to evaluate the whole history after `make up`.

| Service | URL | Notes |
|---------|-----|-------|
| Scoring API docs (Swagger) | http://localhost:8000/docs | `POST /score`, `GET /health`, `POST /admin/replay` |
| Portal | http://localhost:8501 | compare engines, transaction explorer, analyst queue, control |
| Dashboard | http://localhost:3000/d/yuma-shield | Grafana login from `.env` |
| Simulator control | http://localhost:8001/docs | launches traffic, attacks and sandbox runs |
| Kafka UI | http://localhost:8080 | topics `decisions`, `session-events` |
| Case sandbox | http://localhost:8090/v1/metricas | official indicators |

Host ports can be changed in `.env`. Grafana and the workers run with `network_mode: host` so they can reach a PostgreSQL that listens only on `127.0.0.1`.

Traffic and attacks (also available from the portal's Control page):

```bash
make live ARGS="--tps 10 --duration 30"
make attack TYPE=sim_swap ARGS="--speedup 600"   # account_takeover | sim_swap | social_engineering | qr_scam | mule_account
```

Simulated operations use a **virtual clock** that continues after the last transaction of the dataset (31 October), so the model sees realistic timing; `--speedup` is the number of virtual seconds per real second. Attacks are hand-made approximations of the five fraud types in the case, run on real customers of the dataset.

Other commands: `make evaluate` (bulk-scores held-out transactions that have no decision), `make psql`, `make topics`, `make logs`, `make ps`, `make down`.

### Reports produced

- `ml/artifacts/meta.json` — model version, splits, validation and test metrics, global feature importance.
- `ml/artifacts/fairness.json` — block and flag rates by department and age range (these attributes are never model features; they are only used to audit).
- `ml/artifacts/sandbox_report.json` — indicators returned by the case sandbox for the decided period.

### Feedback loop and model versions

Analysts confirm or release alerts in the portal, and customer service can report fraud that was approved (a customer claim). Both are stored in `labels`. `POST /admin/retrain` (or the portal's Control page) trains a new version using those labels: operations simulated after the dataset period count as legitimate unless a label says otherwise, and labels on the October test month are stored but never used for training.

Every version is stored in `ml/artifacts/models/<version>/` and registered in `model_versions`. A **promotion gate** publishes a new model only if, on the clean October test, fraud detected does not drop more than 1 pp, false positives do not rise more than 5 pp and legitimate customers blocked do not rise more than 0.5 pp. Otherwise the version is kept as `rejected`. `POST /admin/models/{version}/promote` rolls back to any stored version. `FEEDBACK_WEIGHT` (default 2) controls how much feedback labels weigh.

### What is stored for every decision

The feature values, the hard rules evaluated, the score, the reasons, the time spent per stage and an audit trail (`scored` by the API, `persisted` by the consumer with Kafka topic, partition, offset and lag). Each baseline decision keeps the legacy rules that fired.

## Configuration and confidentiality

The challenge forbids publishing rules and thresholds. `config/rules.yaml`, `config/thresholds.yaml`, `config/baseline_rules.yaml` and `.env` are git-ignored; the repository only holds `*.example.*` templates with dummy values. The case package and the data are git-ignored too.

## Challenge constraints driving the design

- Decision in < 300 ms with peaks of 150 TPS.
- No future information: only data before the operation is used.
- Explainable and auditable decisions; no region, age or income used as model features, and a fairness audit by segment.
- Permanent blocks only after human review; no extra friction for legitimate users.
- Encryption in transit and at rest; open-source components.
