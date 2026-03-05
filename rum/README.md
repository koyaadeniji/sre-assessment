# Real User Monitoring (RUM) Implementation

## Approach

The Online Boutique frontend is a **Go server-rendered app** (not a SPA). Every page load is a full HTML response from the Go server. This means:

- No client-side routing to intercept
- RUM agent captures traditional page loads (document load timing)
- Each navigation is a new page-load transaction in Kibana

We use the **Elastic APM RUM agent** (`@elastic/apm-rum`) rather than the OTel Web SDK because:
1. Native integration with Kibana's User Experience dashboard
2. Automatic Core Web Vitals capture
3. Built-in distributed tracing header injection
4. Less configuration needed for server-rendered apps

## What's captured

| Signal | How |
|--------|-----|
| Page load timing | Automatic — document load transaction |
| Core Web Vitals (LCP, FID, CLS, TTFB) | Automatic — reported as transaction marks |
| API calls (XHR/fetch) | Automatic — instrumented by the agent |
| "Add to Cart" clicks | Custom transaction via event listener |
| "Place Order" clicks | Custom transaction via event listener |
| Session ID | Generated per browser session, stored in sessionStorage |
| User agent type | Classified as "mobile" or "desktop" via regex |
| Page route | `window.location.pathname` added as label |

## Distributed tracing

The RUM agent adds `traceparent` and `tracestate` headers to all outbound fetch/XHR requests matching `distributedTracingOrigins`. This means:

```
Browser (page-load) → frontend Go server → productcatalog → ...
```

Shows up as a **single connected trace** in Kibana APM → Traces.

## CORS requirement

The APM Server must accept RUM data from the frontend's origin. Add this to the APM Server config:

```yaml
apm-server:
  rum:
    enabled: true
    allow_origins: ["*"]  # restrict in production
    allow_headers: ["Content-Type", "traceparent", "tracestate"]
```

## How to inject

Edit `src/frontend/templates/header.html` and add the script block from `header.html.patch` inside the `<head>` tag.

## Verification

1. Kibana → Observability → User Experience — should show page load data
2. Kibana → APM → Services → "frontend-browser" — RUM transactions appear here
3. Click a page-load transaction → trace waterfall should show browser span as root, then backend spans
4. Check labels tab for `session_id`, `user_agent.type`, `page_route`
