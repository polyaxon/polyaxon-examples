import http from 'k6/http';
import { check } from 'k6';
import exec from 'k6/execution';
import { Rate } from 'k6/metrics';

const target = __ENV.TARGET;
const phase = __ENV.PHASE || 'measurement';
const rate = Number(__ENV.RATE || 10);
const duration = Number(__ENV.DURATION_SECONDS || 60);
const reportDir = __ENV.REPORT_DIR || '.';
const fixtures = JSON.parse(open('./fixtures.json'));
const invalidResponse = new Rate('invalid_response');

if (!target || !/^https?:\/\//.test(target)) {
  throw new Error('TARGET must be the complete HTTP(S) inference endpoint you own.');
}
if (!['warmup', 'measurement'].includes(phase)) {
  throw new Error('PHASE must be warmup or measurement.');
}
if (!Number.isInteger(rate) || rate < 1 || rate > 50) {
  throw new Error('RATE must be an integer between 1 and 50 requests per second.');
}
if (!Number.isInteger(duration) || duration < 1 || duration > 300) {
  throw new Error('DURATION_SECONDS must be an integer between 1 and 300.');
}
if (!Array.isArray(fixtures) || fixtures.length === 0) {
  throw new Error('fixtures.json must contain at least one request body.');
}

export const options = {
  scenarios: {
    inference: {
      executor: 'constant-arrival-rate',
      rate,
      timeUnit: '1s',
      duration: `${duration}s`,
      preAllocatedVUs: 50,
      maxVUs: 50,
      gracefulStop: '10s',
    },
  },
  summaryTrendStats: ['avg', 'med', 'p(95)', 'p(99)', 'max'],
  thresholds: {
    http_req_failed: [{ threshold: 'rate<0.01', abortOnFail: true, delayAbortEval: '10s' }],
    invalid_response: ['rate<0.01'],
    dropped_iterations: ['count==0'],
    ...(phase === 'measurement' ? { http_req_duration: ['p(99)<500'] } : {}),
  },
};

export default function () {
  const body = fixtures[exec.scenario.iterationInTest % fixtures.length];
  const response = http.post(target, JSON.stringify(body), {
    headers: { 'Content-Type': 'application/json' },
    tags: { name: 'inference', phase },
    timeout: '5s',
    redirects: 0,
  });
  let valid = false;
  try {
    const prediction = response.json('prediction');
    valid = response.status === 200 && typeof prediction === 'string' && prediction.length > 0;
  } catch (_) {
    valid = false;
  }
  invalidResponse.add(!valid);
  check(response, { 'valid prediction response': () => valid });
}

export function handleSummary(data) {
  const report = {
    configuration: { target, phase, rate, durationSeconds: duration, fixtureCount: fixtures.length },
    finishedAt: new Date().toISOString(),
    summary: data,
  };
  return {
    [`${reportDir}/${phase}-summary.json`]: JSON.stringify(report, null, 2),
    stdout: `Saved ${phase}-summary.json; inspect thresholds, dropped iterations, and latency.\n`,
  };
}
