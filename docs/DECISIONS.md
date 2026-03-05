# Architectural Decisions

## 1. Collector Topology: Gateway + Agent

Went with DaemonSet agents per node + a single gateway deployment.

Agents run locally on each node so app pods send OTLP to `NODE_IP:4317` — fast, no cross-node hops. The gateway is where tail-based sampling happens. Sampling has to be centralized because the gateway needs to see all spans for a trace before deciding to keep or drop it. If agents sampled independently, we'd get partial traces.

Downside: gateway is a SPOF. In production, I'd run multiple replicas with trace-ID-based routing.

## 2. Service Selection: Go + Python + Node.js

Picked frontend (Go), recommendationservice (Python), paymentservice (Node.js).

- Three different languages as required
- These three have the most mature OTel SDKs
- Covers the full trace path: frontend is the entry, recommendation is mid-trace, payment is the final step in checkout
- Payment is revenue-critical — should always have full visibility

Considered cartservice (C#) but the Redis client tracing is less interesting to demonstrate than payment validation logic.

## 3. Tail Sampling Strategy

Four policies at the gateway:
1. **Keep all errors** — errors are rare, always worth investigating
2. **Keep traces > 2s** — p99 is normally ~500ms, so 2s means something is wrong
3. **Keep all checkout/payment** — business-critical path
4. **10% probabilistic for the rest** — enough for accurate percentile calculations

10s decision_wait because checkout traces complete in <5s normally.

## 4. RUM: Elastic APM Agent (not OTel Web SDK)

Used `@elastic/apm-rum` because it integrates directly with Kibana's User Experience dashboard — Core Web Vitals, page load breakdowns, and geographic maps work out of the box. OTel Web SDK would require more manual setup for the same Kibana experience.

The Online Boutique frontend is server-rendered Go (not a SPA), so each page navigation is a full document load. The Elastic RUM agent handles this well.

Trade-off: vendor lock-in to Elastic. Would need to switch to OTel Web SDK if migrating to Jaeger or Grafana Tempo.

## 5. Infrastructure: Fleet-Managed Elastic Agent

Used Fleet over standalone Beats because:
- Integrations come with pre-built dashboards (PostgreSQL, Redis)
- Central policy management from Kibana
- The assessment recommends Fleet-managed agents

Committed standalone config equivalents for reproducibility.

## 6. Alert Thresholds

| Alert | Threshold | Why |
|-------|-----------|-----|
| CPU > 85%, 5 min | 85% sustained | Brief spikes are normal. 5 min = real load. |
| Disk < 10% free | 90% used | Kubelet evicts pods at ~10-15%. |
| Memory < 500MB | 500MB available | OOM killer territory. |
| PG connections > 80% | 80% of max | 100% = rejected connections. 20% buffer to fix. |
| PG cache hit < 95% | 95% | Healthy is >99%. <95% = too much disk I/O. |
| Redis memory > 85% | 85% of max | Eviction starts at max. Buffer to investigate. |
| NGINX 5xx > 5%, 2 min | 5% for 2 min | Filters single-request noise. |
| SSL cert < 14 days | 14 days | Standard. Enough time to debug or renew. |
