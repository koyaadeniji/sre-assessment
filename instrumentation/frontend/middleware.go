package main

import (
	"net/http"
	"time"

	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/metric"
)

// metricsMiddleware records request duration per route.
// Wrap the router with this: handler := metricsMiddleware(router)
func metricsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		next.ServeHTTP(w, r)
		duration := time.Since(start).Seconds()

		requestDuration.Record(r.Context(), duration,
			metric.WithAttributes(
				attribute.String("http.route", r.URL.Path),
				attribute.String("http.method", r.Method),
			),
		)
	})
}
