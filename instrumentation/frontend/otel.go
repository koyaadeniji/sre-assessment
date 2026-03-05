package main

import (
	"context"
	"fmt"
	"time"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
	"go.opentelemetry.io/otel/exporters/otlp/otlpmetric/otlpmetricgrpc"
	"go.opentelemetry.io/otel/metric"
	"go.opentelemetry.io/otel/propagation"
	"go.opentelemetry.io/otel/sdk/resource"
	sdkmetric "go.opentelemetry.io/otel/sdk/metric"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.24.0"
	"go.opentelemetry.io/otel/trace"
)

var (
	tracer          trace.Tracer
	meter           metric.Meter
	requestDuration metric.Float64Histogram
)

func initOtel(ctx context.Context) (func(), error) {
	res, err := resource.New(ctx,
		resource.WithAttributes(
			semconv.ServiceNameKey.String("frontend"),
			semconv.ServiceVersionKey.String("1.0.0"),
			semconv.DeploymentEnvironmentKey.String("assessment"),
		),
		resource.WithHost(),
	)
	if err != nil {
		return nil, fmt.Errorf("creating resource: %w", err)
	}

	traceExp, err := otlptracegrpc.New(ctx, otlptracegrpc.WithInsecure())
	if err != nil {
		return nil, fmt.Errorf("creating trace exporter: %w", err)
	}

	tp := sdktrace.NewTracerProvider(
		sdktrace.WithBatcher(traceExp),
		sdktrace.WithResource(res),
		sdktrace.WithSampler(sdktrace.AlwaysSample()),
	)

	metricExp, err := otlpmetricgrpc.New(ctx, otlpmetricgrpc.WithInsecure())
	if err != nil {
		return nil, fmt.Errorf("creating metric exporter: %w", err)
	}

	mp := sdkmetric.NewMeterProvider(
		sdkmetric.WithReader(sdkmetric.NewPeriodicReader(metricExp)),
		sdkmetric.WithResource(res),
	)

	otel.SetTracerProvider(tp)
	otel.SetMeterProvider(mp)
	otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(
		propagation.TraceContext{},
		propagation.Baggage{},
	))

	tracer = tp.Tracer("frontend")
	meter = mp.Meter("frontend")

	requestDuration, _ = meter.Float64Histogram(
		"http.request.duration.by_route",
		metric.WithDescription("Request duration in seconds per route"),
		metric.WithUnit("s"),
	)

	cleanup := func() {
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		tp.Shutdown(shutdownCtx)
		mp.Shutdown(shutdownCtx)
	}

	return cleanup, nil
}
