# Frontend Instrumentation (Go)

## Changes to the Online Boutique frontend

The frontend is a Go HTTP server in `microservices-demo/src/frontend/`. These files add OpenTelemetry instrumentation:

| File | What it does |
|------|-------------|
| `otel.go` | Initializes OTel SDK — tracer, meter, OTLP exporter. Call `initOtel()` at the top of `main()`. |
| `handlers.go` | Custom spans: `render-product-page` (wraps template rendering) and `process-checkout-form` (wraps form validation). Call these from the existing handler functions. |
| `middleware.go` | HTTP middleware that records `http.request.duration.by_route` histogram. Wrap the router: `handler := metricsMiddleware(router)`. |
| `Dockerfile` | Build with OTel dependencies included. |
| `deployment-patch.yaml` | Sets `OTEL_EXPORTER_OTLP_ENDPOINT` to the DaemonSet agent via node IP. |

## How to apply

1. Copy `otel.go`, `handlers.go`, `middleware.go` into `src/frontend/`
2. Add the OTel imports to `go.mod`:
   ```bash
   cd src/frontend
   go get go.opentelemetry.io/otel@v1.24.0
   go get go.opentelemetry.io/otel/sdk@v1.24.0
   go get go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc@v1.24.0
   go get go.opentelemetry.io/otel/exporters/otlp/otlpmetric/otlpmetricgrpc@v1.24.0
   go get go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp@v0.49.0
   go get go.opentelemetry.io/contrib/instrumentation/google.golang.org/grpc/otelgrpc@v0.49.0
   ```
3. In `main.go`, add at the top of `main()`:
   ```go
   cleanup, err := initOtel(context.Background())
   if err != nil { log.Fatal(err) }
   defer cleanup()
   ```
4. Wrap the HTTP router with `otelhttp` and the metrics middleware:
   ```go
   handler := metricsMiddleware(otelhttp.NewHandler(router, "frontend"))
   ```
5. Add gRPC interceptors to all client connections:
   ```go
   conn, _ := grpc.DialContext(ctx, addr,
       grpc.WithUnaryInterceptor(otelgrpc.UnaryClientInterceptor()),
       grpc.WithStreamInterceptor(otelgrpc.StreamClientInterceptor()),
   )
   ```
6. Call `instrumentedProductRender()` from `productHandler` and `instrumentedCheckoutForm()` from `placeOrderHandler`
7. Build and deploy:
   ```bash
   docker build -t frontend:instrumented .
   kubectl apply -f deployment-patch.yaml
   ```

## Verification

- Kibana → APM → Services → "frontend"
- Click a transaction → trace waterfall shows `render-product-page` and `process-checkout-form`
- Span metadata shows `product.id`, `user.currency`, `session.id`
- Metrics Explorer → `http.request.duration.by_route`
