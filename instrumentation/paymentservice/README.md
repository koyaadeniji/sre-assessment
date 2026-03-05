# Payment Service Instrumentation (Node.js)

## What was changed

The paymentservice is a Node.js gRPC server that handles credit card charges. We added:

1. **tracing.js** — OTel SDK init, loaded via `--require` before app code (critical for auto-patching)
2. **Auto-instrumentation** — `@opentelemetry/auto-instrumentations-node` covers gRPC and HTTP
3. **Custom span: `validate-credit-card`** — wraps card validation, records card type and last-four
4. **Custom span: `process-payment-transaction`** — wraps the charge logic with full payment context
5. **Custom metric: `payment_transactions_total`** — counter with labels: status (success/failure), currency, card_type
6. **Error recording** — uses `span.recordException()` + `span.setStatus(ERROR)` for proper error display in Kibana

## Why --require is important

Node.js OTel auto-instrumentation works by monkey-patching modules at `require()` time. If the app imports `@grpc/grpc-js` before `tracing.js` runs, the gRPC module won't be patched and we won't see gRPC spans. The `--require ./tracing.js` flag in the Dockerfile ensures OTel loads first.

## Verification

1. Kibana → APM → Services → "paymentservice"
2. Find a checkout trace — `validate-credit-card` and `process-payment-transaction` as child spans
3. Click on a failed payment span — error tab should show exception with stack trace
4. Check span metadata for `payment.amount`, `payment.currency`, `payment.card_type`
5. Metrics Explorer → `payment_transactions_total` — should show success/failure breakdown
