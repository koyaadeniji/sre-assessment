"""
Recommendation Service — OpenTelemetry Instrumentation
=======================================================

The recommendation service is a Python gRPC server that fetches the product catalog
and returns a filtered list of product recommendations.

This file wraps the original recommendation_server.py with OTel instrumentation.
Apply these changes to: microservices-demo/src/recommendationservice/recommendation_server.py

WHAT THIS ADDS:
- Auto-instrumentation for gRPC (server + client)
- 2 custom spans (filter-recommendations, fetch-product-catalog)
- Custom attributes (recommendation.count, product.category)
- 1 custom metric (recommendations_served_total counter)
- Proper resource attributes for Kibana APM identification
"""

import os
import time
import grpc
from concurrent import futures

# --- OTel imports ---
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.instrumentation.grpc import (
    GrpcInstrumentorServer,
    GrpcInstrumentorClient,
)
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.baggage.propagation import W3CBaggagePropagator


def init_otel():
    """
    Set up OpenTelemetry with OTLP exporter pointing at the DaemonSet agent.

    The agent runs on every node and listens on port 4317.
    We use NODE_IP env var (set via k8s downward API) to find it.
    """
    resource = Resource.create({
        SERVICE_NAME: "recommendationservice",
        SERVICE_VERSION: "1.0.0",
        "deployment.environment": "assessment",
    })

    # --- traces ---
    otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "localhost:4317")
    trace_exporter = OTLPSpanExporter(
        endpoint=otlp_endpoint,
        insecure=True,  # TLS not needed inside cluster
    )
    trace_provider = TracerProvider(resource=resource)
    trace_provider.add_span_processor(BatchSpanExporter(trace_exporter))
    trace.set_tracer_provider(trace_provider)

    # --- metrics ---
    metric_exporter = OTLPMetricExporter(
        endpoint=otlp_endpoint,
        insecure=True,
    )
    metric_reader = PeriodicExportingMetricReader(
        metric_exporter,
        export_interval_millis=15000,  # export every 15s
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)

    # --- propagation ---
    # W3C TraceContext so traces connect across services
    set_global_textmap(CompositePropagator([
        TraceContextTextMapPropagator(),
        W3CBaggagePropagator(),
    ]))

    # --- auto-instrumentation for gRPC ---
    # this automatically creates spans for all incoming gRPC requests
    # and outgoing gRPC calls (like fetching the product catalog)
    GrpcInstrumentorServer().instrument()
    GrpcInstrumentorClient().instrument()

    return trace.get_tracer("recommendationservice"), metrics.get_meter("recommendationservice")


# initialize OTel before anything else
tracer, meter = init_otel()

# custom metric: how many recommendations we're serving
# useful for tracking if the recommendation engine is actually working
recommendations_counter = meter.create_counter(
    name="recommendations_served_total",
    description="Total number of product recommendations served",
    unit="1",
)


class RecommendationService(demo_pb2_grpc.RecommendationServiceServicer):
    """gRPC handler with custom OTel instrumentation."""

    def ListRecommendations(self, request, context):
        """
        Takes a list of product IDs the user has interacted with,
        fetches the full catalog, and returns filtered recommendations.
        """
        max_responses = 5

        # --- custom span: fetch the product catalog ---
        # this wraps the gRPC call to productcatalogservice
        # so we can see how long the catalog fetch takes separately from filtering
        with tracer.start_as_current_span(
            "fetch-product-catalog",
            attributes={
                "rpc.service": "ProductCatalogService",
                "rpc.method": "ListProducts",
            },
        ) as catalog_span:
            # call product catalog service
            catalog_response = product_catalog_stub.ListProducts(demo_pb2.Empty())
            product_ids = [p.id for p in catalog_response.products]
            catalog_span.set_attribute("catalog.size", len(product_ids))
            catalog_span.add_event("catalog fetched", {
                "product_count": len(product_ids),
            })

        # --- custom span: filter and rank recommendations ---
        with tracer.start_as_current_span(
            "filter-recommendations",
            attributes={
                "recommendation.input_products": str(request.product_ids),
                "recommendation.max_results": max_responses,
            },
        ) as filter_span:
            # remove products the user already has
            filtered = [pid for pid in product_ids if pid not in request.product_ids]

            # simple random sampling (in a real system this would be ML-based)
            import random
            num_products = min(max_responses, len(filtered))
            recommendations = random.sample(filtered, num_products)

            filter_span.set_attribute("recommendation.count", len(recommendations))
            filter_span.set_attribute("recommendation.filtered_out", len(product_ids) - len(filtered))

            # add a span event showing what we recommended
            filter_span.add_event("recommendations generated", {
                "recommended_ids": str(recommendations),
            })

        # record the custom metric
        recommendations_counter.add(
            len(recommendations),
            attributes={
                "recommendation.source": "random",  # vs "ml_model" in production
            },
        )

        response = demo_pb2.ListRecommendationsResponse()
        response.product_ids.extend(recommendations)
        return response


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    demo_pb2_grpc.add_RecommendationServiceServicer_to_server(
        RecommendationService(), server
    )

    port = os.environ.get("PORT", "8080")
    server.add_insecure_port(f"[::]:{port}")
    print(f"recommendation service listening on port {port}")
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
