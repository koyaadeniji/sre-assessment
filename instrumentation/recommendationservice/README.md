# Recommendation Service Instrumentation (Python)

## What was changed

The recommendationservice is a Python gRPC server. We added:

1. **Auto-instrumentation** — `opentelemetry-instrument` wrapper in the Dockerfile ENTRYPOINT
2. **gRPC auto-instrumentation** — `GrpcInstrumentorServer` + `GrpcInstrumentorClient` for all RPC calls
3. **Custom span: `fetch-product-catalog`** — wraps the catalog gRPC call, adds `catalog.size` attribute
4. **Custom span: `filter-recommendations`** — wraps the filtering logic, adds `recommendation.count`
5. **Custom metric: `recommendations_served_total`** — counter tracking how many recommendations we return
6. **Span events** — "catalog fetched" and "recommendations generated" events with product details

## How to build

```bash
docker build -t sre-assessment/recommendationservice:instrumented -f Dockerfile .
```

## Verification

1. Kibana → APM → Services → "recommendationservice"
2. Click a transaction — `fetch-product-catalog` and `filter-recommendations` should appear as child spans
3. Check the span metadata for `recommendation.count` and `catalog.size`
4. Metrics Explorer → `recommendations_served_total` — should show the counter incrementing
