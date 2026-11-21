# Load test results

Tool: k6 (`make loadtest`), scenario in [score.js](score.js). Requests are real October operations from the case dataset with unique ids prefixed `LT-`; they go through the full path (features, model, Kafka, persister) and are removed afterwards with `make loadtest-clean`.

## Profile

| Stage | Arrival rate | Duration |
|-------|--------------|----------|
| Warm-up | 10 → 50 TPS | 15 s |
| Ramp | 50 → 150 TPS | 15 s |
| **Peak required by the case** | **150 TPS** | **60 s** |
| Spike | 150 → 200 TPS (+33 %) | 20 s |
| Cool-down | 200 → 10 TPS | 10 s |

## Result (run of 2026-11-21)

| Indicator | Value | Goal |
|-----------|-------|------|
| Requests | 15,499 | — |
| Failed requests | 0 (0.00 %) | < 1 % |
| Valid decisions (`checks`) | 100 % (30,998 / 30,998) | > 99 % |
| Client latency p95 (k6) | **10.4 ms** | < 300 ms |
| Client latency p50 / max | 6.5 ms / 104.8 ms | — |
| Time inside the API p50 / p95 / p99 | 3.7 / 6.2 / 11.7 ms | — |
| Of which features (SQL) / model | 1.5 / 2.5 ms on average | — |
| Decisions persisted through Kafka | 15,499 of 15,499 | no loss |
| Concurrent connections needed | at most 2 virtual users | — |

All thresholds passed. The system never saturated, so the real limit is above the 200 TPS tested.

## How to read it

- Everything ran on one machine (k6, API with 2 workers, Kafka, PostgreSQL and the persister), so numbers show headroom but are not a capacity claim for production.
- The official sandbox run (`make sandbox-run`) reports a higher latency (p50 91 ms, p99 137 ms) because it sends 32 concurrent requests per batch and measures from delivery, including queueing. The same API answers a single request in a few milliseconds.
- PostgreSQL is the component to watch when scaling: every score reads the customer history with indexed queries.
