/**
 * Payment Service — OpenTelemetry Instrumentation
 * =================================================
 *
 * This file initializes the OTel Node.js SDK and must be loaded BEFORE
 * any other application code. That's why it's specified as a --require
 * in the Dockerfile entrypoint.
 *
 * IMPORTANT: Node.js OTel auto-instrumentation works by monkey-patching
 * modules at require() time. If tracing.js loads after the app imports
 * grpc or http, those modules won't be patched and we get no spans.
 *
 * WHAT THIS SETS UP:
 * - OTLP/gRPC exporter → DaemonSet agent on the node
 * - Auto-instrumentation for gRPC, HTTP, Express (if used)
 * - W3C TraceContext propagation
 * - Custom tracer and meter for manual instrumentation in charge.js
 */

"use strict";

const { NodeSDK } = require("@opentelemetry/sdk-node");
const {
  OTLPTraceExporter,
} = require("@opentelemetry/exporter-trace-otlp-grpc");
const {
  OTLPMetricExporter,
} = require("@opentelemetry/exporter-metrics-otlp-grpc");
const {
  PeriodicExportingMetricReader,
} = require("@opentelemetry/sdk-metrics");
const {
  getNodeAutoInstrumentations,
} = require("@opentelemetry/auto-instrumentations-node");
const { Resource } = require("@opentelemetry/resources");
const {
  SEMRESATTRS_SERVICE_NAME,
  SEMRESATTRS_SERVICE_VERSION,
  SEMRESATTRS_DEPLOYMENT_ENVIRONMENT,
} = require("@opentelemetry/semantic-conventions");
const {
  W3CTraceContextPropagator,
} = require("@opentelemetry/core");

const otlpEndpoint =
  process.env.OTEL_EXPORTER_OTLP_ENDPOINT || "http://localhost:4317";

const sdk = new NodeSDK({
  resource: new Resource({
    [SEMRESATTRS_SERVICE_NAME]: "paymentservice",
    [SEMRESATTRS_SERVICE_VERSION]: "1.0.0",
    [SEMRESATTRS_DEPLOYMENT_ENVIRONMENT]: "assessment",
  }),

  traceExporter: new OTLPTraceExporter({
    url: otlpEndpoint,
  }),

  metricReader: new PeriodicExportingMetricReader({
    exporter: new OTLPMetricExporter({
      url: otlpEndpoint,
    }),
    exportIntervalMillis: 15000,
  }),

  // auto-instrument all supported libraries
  // this catches gRPC server/client, HTTP, and any Express middleware
  instrumentations: [
    getNodeAutoInstrumentations({
      // disable fs instrumentation — too noisy, not useful for us
      "@opentelemetry/instrumentation-fs": { enabled: false },
      // enable grpc with detailed events
      "@opentelemetry/instrumentation-grpc": { enabled: true },
    }),
  ],

  textMapPropagator: new W3CTraceContextPropagator(),
});

// start the SDK — this must happen before any app code loads
sdk.start();
console.log("OpenTelemetry SDK initialized for paymentservice");

// clean shutdown on SIGTERM (k8s sends this before killing the pod)
process.on("SIGTERM", () => {
  sdk
    .shutdown()
    .then(() => console.log("OTel SDK shut down"))
    .catch((err) => console.error("OTel shutdown error", err))
    .finally(() => process.exit(0));
});
