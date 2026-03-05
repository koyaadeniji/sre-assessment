# Kibana Dashboards

## How to build and export

Each dashboard below is built manually in Kibana using the steps described.
After building, export as NDJSON:

```
Kibana → Stack Management → Saved Objects → select dashboard → Export → Include related objects → Export
```

Save the exported `.ndjson` file in this directory. To re-import:

```bash
curl -X POST "https://KIBANA_URL/api/saved_objects/_import" \
  -H "kbn-xsrf: true" --form file=@service-health.ndjson -u elastic:PASSWORD -k
```

---

## Dashboard 1: Service Health Overview

**Data view:** `traces-apm-*`

### Panel 1a — Request Rate by Service (RPM)

- **Type:** Lens → Line chart
- **X-axis:** `@timestamp` (date histogram, 1-minute interval)
- **Y-axis:** Count of records
- **Break down by:** `service.name` (Top 10)
- **Title:** "Request Rate by Service (RPM)"

### Panel 1b — Error Rate by Service (%)

- **Type:** Lens → Line chart
- **X-axis:** `@timestamp` (date histogram, 5-minute interval)
- **Y-axis:** Formula: `count(kql='event.outcome: failure') / count() * 100`
- **Break down by:** `service.name`
- **Title:** "Error Rate by Service (%)"

### Panel 1c — Latency p95 by Service

- **Type:** Lens → Line chart
- **X-axis:** `@timestamp` (date histogram, 5-minute interval)
- **Y-axis:** Percentile (95th) of `transaction.duration.us`
- **Break down by:** `service.name`
- **Title:** "p95 Latency by Service (μs)"

### Panel 1d — Service Dependency Map

- **Type:** Navigate to APM → Service Map (or embed via saved search)
- This is built-in to Kibana APM — no custom panel needed.
- Shows all connected services with traffic flow direction.

### Panel 1e — Apdex Score per Service

- **Type:** Lens → Metric
- **Metric:** Formula:
  ```
  (count(kql='transaction.duration.us <= 500000') +
   count(kql='transaction.duration.us > 500000 AND transaction.duration.us <= 2000000') / 2)
  / count()
  ```
- **Break down by:** `service.name`
- **Color rules:** Red < 0.5, Orange 0.5–0.75, Green > 0.75
- **Note:** T=500ms (satisfying threshold). Apdex = (satisfied + tolerating/2) / total.

### Panel 1f — Error Count Table

- **Type:** Lens → Data table
- **Columns:**
  - `service.name` (terms, top 5)
  - `error.exception.message` (terms, top 10)
  - Count
- **Sort by:** Count descending

### Controls

Add Kibana Controls panel at the top:
- **Options control:** `service.name` dropdown
- **Options control:** `deployment.environment` dropdown
- **Time slider:** For time range selection

---

## Dashboard 2: Frontend / RUM Performance

**Data view:** `traces-apm-*` filtered by `service.name: frontend-browser`

### Panel 2a — Core Web Vitals Gauges

Build 4 separate Lens → Metric panels:

| Metric | Field | Good | Needs Improvement | Poor |
|--------|-------|------|-------------------|------|
| LCP | `transaction.marks.agent.largestContentfulPaint` | < 2500ms | 2500–4000ms | > 4000ms |
| FID | `transaction.marks.agent.firstInputDelay` | < 100ms | 100–300ms | > 300ms |
| CLS | `transaction.experience.cls` | < 0.1 | 0.1–0.25 | > 0.25 |
| TTFB | `transaction.marks.agent.timeToFirstByte` | < 800ms | 800–1800ms | > 1800ms |

For each: use Median aggregation, apply color palette with thresholds matching Google's standards.

### Panel 2b — Page Load Waterfall Breakdown

- **Type:** Lens → Stacked bar chart
- **X-axis:** `@timestamp` (5-minute intervals)
- **Y-axis (stacked):**
  - DNS: `transaction.marks.navigationTiming.domainLookupEnd`
  - TCP: `transaction.marks.navigationTiming.connectEnd` minus DNS
  - TLS: `transaction.marks.navigationTiming.secureConnectionStart` (if present)
  - TTFB: `transaction.marks.navigationTiming.responseStart` minus TCP
  - Download: `transaction.marks.navigationTiming.responseEnd` minus TTFB
  - DOM: `transaction.marks.navigationTiming.domComplete` minus Download

### Panel 2c — Latency by Route (p50/p90/p99)

- **Type:** Lens → Data table
- **Rows:** `labels.page_route` (terms, top 15)
- **Columns:**
  - Percentile 50th of `transaction.duration.us`
  - Percentile 90th of `transaction.duration.us`
  - Percentile 99th of `transaction.duration.us`
  - Count

### Panel 2d — Geographic Latency Map

- **Type:** Kibana Maps
- **Layer:** Clusters and grids
- **Index:** `traces-apm-*` where `service.name: frontend-browser`
- **Geo field:** `client.geo.location`
- **Metric:** Average of `transaction.duration.us`
- **Color ramp:** Green (fast) → Red (slow)

### Panel 2e — JS Exception Table

- **Type:** Lens → Data table
- **Filter:** `processor.event: error AND service.name: frontend-browser`
- **Columns:**
  - `error.exception.message` (terms, top 20)
  - Count
  - `@timestamp` (last value — "Last Seen")
- **Sort by:** Count descending

### Panel 2f — Session Error Rate

- **Type:** Lens → Area chart
- **X-axis:** `@timestamp` (15-minute intervals)
- **Y-axis:** Formula: `count(kql='processor.event: error') / count() * 100`
- **Title:** "Session Error Rate (%)"

---

## Dashboard 3: Business Transaction Monitoring

**Data view:** `traces-apm-*` for APM data, `metrics-*` for custom OTel metrics

### Panel 3a — Checkout Funnel

- **Type:** Lens → Bar chart (vertical)
- **X-axis:** `@timestamp` (1-hour intervals)
- **Y-axis (5 series, each filtered):**
  - Browse: Count where `transaction.name: "GET /"`
  - View Product: Count where `transaction.name: "GET /product/*"`
  - Add to Cart: Count where `transaction.name: "POST /cart"`
  - Checkout: Count where `transaction.name: "POST /cart/checkout"`
  - Confirmed: Count where `transaction.name: "POST /cart/checkout" AND event.outcome: success`

### Panel 3b — Revenue-Correlated Latency (Dual Axis)

- **Type:** Lens → Line chart with right axis
- **Left axis:** Percentile 95th of `transaction.duration.us` where `transaction.name: "POST /cart/checkout"`
- **Right axis:** Formula: `count(kql='transaction.name: "POST /cart/checkout" AND event.outcome: success') / count(kql='transaction.name: "POST /cart/checkout"') * 100`
- **X-axis:** `@timestamp` (15-minute intervals)
- **Title:** "Checkout p95 Latency vs Completion Rate"

### Panel 3c — Cart Abandonment

- **Type:** Lens → Area chart (2 series)
- **Series 1:** Count where `transaction.name: "POST /cart"` — label "Cart Additions"
- **Series 2:** Count where `transaction.name: "POST /cart/checkout" AND event.outcome: success` — label "Completed Checkouts"
- **X-axis:** `@timestamp` (1-hour intervals)
- **Gap between lines = abandonment**

### Panel 3d — Payment Transactions (Custom OTel Metric)

- **Data view:** `metrics-*`
- **Type:** Lens → Stacked bar chart
- **X-axis:** `@timestamp` (5-minute intervals)
- **Y-axis:** Sum of `payment_transactions_total`
- **Break down by:** `payment.status` (success / failure)
- **Source:** Custom metric from paymentservice instrumentation

### Panel 3e — Recommendations Served (Custom OTel Metric)

- **Data view:** `metrics-*`
- **Type:** Lens → Bar chart
- **X-axis:** `@timestamp` (5-minute intervals)
- **Y-axis:** Sum of `recommendations_served_total`
- **Source:** Custom metric from recommendationservice instrumentation

### Panel 3f — Request Duration by Route (Custom OTel Metric)

- **Data view:** `metrics-*`
- **Type:** Lens → Line chart
- **X-axis:** `@timestamp` (5-minute intervals)
- **Y-axis:** Average of `http.request.duration.by_route`
- **Break down by:** `http.route`
- **Source:** Custom metric from frontend instrumentation
