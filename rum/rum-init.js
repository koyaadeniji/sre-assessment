/**
 * Real User Monitoring — Elastic APM RUM Agent
 *
 * Injected into the Online Boutique frontend Go templates.
 * Captures browser-side performance and correlates with backend traces.
 *
 * Add to: src/frontend/templates/header.html, inside <head>.
 */
(function () {
  // APM Server must be reachable from the browser.
  // Use the external URL (via ingress or port-forward), NOT the internal k8s service DNS.
  //
  // Examples:
  //   minikube:  "http://localhost:8200" (after: kubectl port-forward svc/apm-server-apm-http -n elastic-system 8200:8200)
  //   ingress:   "https://apm.your-domain.com"
  //   nodeport:  "http://NODE_IP:30820"
  var APM_SERVER_URL = "http://localhost:8200";

  var script = document.createElement("script");
  script.src = "https://unpkg.com/@elastic/apm-rum@5.16.0/dist/bundles/elastic-apm-rum.umd.min.js";
  script.crossOrigin = "anonymous";
  script.onload = function () {
    var apm = window.elasticApm.init({
      serviceName: "frontend-browser",
      serverUrl: APM_SERVER_URL,
      environment: "assessment",
      serviceVersion: "1.0.0",

      // distributed tracing — adds traceparent header to outbound requests
      // so browser spans connect to backend traces
      distributedTracingOrigins: [window.location.origin],
      distributedTracing: true,
      propagateTracestate: true,

      // sample everything for the assessment
      transactionSampleRate: 1.0,
    });

    // session tracking
    var sessionId = sessionStorage.getItem("_sid");
    if (!sessionId) {
      sessionId = "sess_" + Math.random().toString(36).substr(2, 12);
      sessionStorage.setItem("_sid", sessionId);
    }

    // classify device type
    var isMobile = /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);

    apm.addLabels({
      session_id: sessionId,
      page_route: window.location.pathname,
      "user_agent.type": isMobile ? "mobile" : "desktop",
    });

    // track "Add to Cart" clicks
    document.addEventListener("click", function (e) {
      if (e.target.textContent && e.target.textContent.indexOf("Add to Cart") !== -1) {
        var tx = apm.startTransaction("click - Add to Cart", "user-interaction");
        if (tx) {
          tx.addLabels({ product_id: window.location.pathname.split("/product/")[1] || "unknown" });
          setTimeout(function () { tx.end(); }, 3000);
        }
      }

      if (e.target.textContent && e.target.textContent.indexOf("Place Order") !== -1) {
        var tx = apm.startTransaction("click - Place Order", "user-interaction");
        if (tx) {
          setTimeout(function () { tx.end(); }, 5000);
        }
      }
    });
  };

  document.head.appendChild(script);
})();
