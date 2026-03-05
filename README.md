# SRE Assessment — Elastic Stack + OpenTelemetry

Observability implementation for the [Google Online Boutique](https://github.com/GoogleCloudPlatform/microservices-demo) on a pre-provisioned Kubernetes cluster.

## Environment

| Component | Status | Notes |
|-----------|--------|-------|
| Kubernetes cluster (2 nodes) | Pre-provisioned | minikube / EKS / AKS / GKE |
| NGINX Ingress Controller | Pre-provisioned | Cluster load balancer |
| Elastic Stack (ES, Kibana, APM) | Pre-provisioned | APM Server OTLP intake on :8200 |
| Online Boutique (11 services) | Pre-provisioned | Running in `online-boutique` namespace |
| PostgreSQL | Deployed as part of assessment | For DB monitoring (Section 3) |
| Redis | Part of Online Boutique | `redis-cart` service |

## What I Deployed

### 1. OTel Collector (Gateway + Agent topology)

```bash
helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts

# DaemonSet agents — one per node, collects from local pods + host metrics
helm install otel-agent open-telemetry/opentelemetry-collector \
  -f otel-collector/values-agent.yaml -n online-boutique

# Gateway — central collector for tail sampling, exports to Elastic APM
helm install otel-gateway open-telemetry/opentelemetry-collector \
  -f otel-collector/values-gateway.yaml -n online-boutique
```

### 2. Service Instrumentation

Three services instrumented in different languages:

| Service | Language | Custom Spans | Custom Metric |
|---------|----------|-------------|---------------|
| frontend | Go | `render-product-page`, `process-checkout-form` | `http.request.duration.by_route` histogram |
| recommendationservice | Python | `fetch-product-catalog`, `filter-recommendations` | `recommendations_served_total` counter |
| paymentservice | Node.js | `validate-credit-card`, `process-payment-transaction` | `payment_transactions_total` counter |

Build and deploy each:
```bash
# example for frontend — repeat for each service
cd instrumentation/frontend
docker build -t frontend:instrumented .
kubectl set image deployment/frontend server=frontend:instrumented -n online-boutique
kubectl apply -f deployment-patch.yaml
```

### 3. RUM (Real User Monitoring)

Injected Elastic APM RUM agent into the frontend Go templates. See `rum/`.

### 4. Dashboards

Built in Kibana, exported as NDJSON saved objects. See `dashboards/` for build instructions and exported files.

```bash
# import dashboards
for f in dashboards/*.ndjson; do
  curl -X POST "https://KIBANA_URL/api/saved_objects/_import" \
    -H "kbn-xsrf: true" --form file=@"$f" -u elastic:PASSWORD -k
done
```

### 5. Infrastructure Monitoring

- **Elastic Agent** DaemonSet with System integration (CPU, memory, disk, network)
- **PostgreSQL** integration via Fleet
- **Redis** integration via Fleet
- **NGINX Ingress** metrics + structured access logs
- **11 alerting rules** in Kibana (see `infrastructure/alerting-rules/`)

### 6. Traffic Generation

```bash
./scripts/generate-traffic.sh http://FRONTEND_URL
```

## Verification Checklist

- [ ] Kibana → APM → Services shows frontend, recommendationservice, paymentservice
- [ ] APM → Traces shows end-to-end spans across 3+ service hops
- [ ] APM → Service Map displays connected service graph
- [ ] Custom spans visible in trace waterfall (render-product-page, validate-credit-card, etc.)
- [ ] Custom metrics queryable in Metrics Explorer
- [ ] RUM data in Observability → User Experience
- [ ] Browser-to-backend trace correlation works
- [ ] Infrastructure → Inventory shows both nodes with live metrics
- [ ] PostgreSQL and Redis dashboards populated
- [ ] NGINX metrics flowing
- [ ] All alerting rules active

## Repository Structure

```
sre-assessment/
├── otel-collector/           # Helm values for Gateway + Agent
├── instrumentation/          # Per-service OTel SDK code
│   ├── frontend/             # Go
│   ├── recommendationservice/# Python
│   └── paymentservice/       # Node.js
├── rum/                      # Browser RUM agent
├── dashboards/               # Kibana dashboard build specs + NDJSON exports
├── infrastructure/           # Elastic Agent, integrations, alerts, network policies
├── scripts/                  # Traffic generation
├── docs/DECISIONS.md         # Architectural decisions
└── README.md
```
