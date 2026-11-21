import http from 'k6/http';
import { check } from 'k6';
import { SharedArray } from 'k6/data';
import { Trend } from 'k6/metrics';

const payloads = new SharedArray('payloads', () => JSON.parse(open('./payloads.json')));
const BASE_URL = __ENV.API_URL || 'http://localhost:8000';
const TARGET = Number(__ENV.TPS || 150);
const HOLD = __ENV.HOLD || '60s';
const server_latency = new Trend('server_latency_ms');

export const options = {
  scenarios: {
    peak: {
      executor: 'ramping-arrival-rate',
      startRate: 10,
      timeUnit: '1s',
      preAllocatedVUs: 100,
      maxVUs: 400,
      stages: [
        { target: 50, duration: '15s' },
        { target: TARGET, duration: '15s' },
        { target: TARGET, duration: HOLD },
        { target: Math.round(TARGET * 1.33), duration: '20s' },
        { target: 10, duration: '10s' },
      ],
    },
  },
  thresholds: {
    http_req_duration: ['p(95)<300'],
    http_req_failed: ['rate<0.01'],
    checks: ['rate>0.99'],
  },
};

export default function () {
  const base = payloads[Math.floor(Math.random() * payloads.length)];
  const body = Object.assign({}, base, {
    transaction_id: `LT-${__VU}-${__ITER}-${Date.now()}`,
    meta: { loadtest: true, is_fraud: false },
  });
  const res = http.post(`${BASE_URL}/score`, JSON.stringify(body), {
    headers: { 'Content-Type': 'application/json' },
  });
  const ok = check(res, {
    'status is 200': (r) => r.status === 200,
    'has a decision': (r) => r.status === 200 && ['approve', 'challenge', 'hold', 'reject'].includes(r.json('action')),
  });
  if (ok) server_latency.add(res.json('latency_ms'));
}
