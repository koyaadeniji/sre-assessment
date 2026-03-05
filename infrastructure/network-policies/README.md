# Network Policy Monitoring (Section 3.3)

## Network Policies

`network-policy.yaml` defines the policies applied to the `online-boutique` namespace:

- **Default deny all ingress** — baseline security, no pod accepts traffic unless allowed
- **Allow frontend from ingress** — only the NGINX ingress can reach the frontend
- **Allow frontend to backends** — frontend can call all backend services
- **Allow cartservice to Redis** — cart can reach redis-cart on port 6379
- **Allow checkout to backends** — checkout needs payment, shipping, email, etc.
- **Allow OTel export** — all pods can reach the DaemonSet agent on ports 4317/4318
- **Allow Elastic Stack** — all pods can reach Elasticsearch, Kibana, APM Server

## Flow Log Collection

Network policy enforcement logging depends on the CNI plugin:

### Option A: Cilium Hubble (recommended for minikube)

If using Cilium CNI (`minikube start --cni=cilium`):

```bash
# enable Hubble observability
cilium hubble enable --ui

# export flow logs to stdout (pipe to Filebeat or Elastic Agent)
hubble observe --verdict DROPPED --output json
```

Configure Elastic Agent with a custom log integration to read Hubble's JSON output.

### Option B: Calico (if using `--cni=calico`)

Calico community edition provides basic logging via Felix component.
Enable policy audit logging:

```bash
kubectl patch felixconfiguration default --type merge \
  -p '{"spec":{"policySyncPathPrefix":"/var/run/nodeagent"}}'
```

### Option C: Kubernetes Audit Logs (works with any CNI)

Even without CNI flow logs, we can track NetworkPolicy **changes** via the Kubernetes audit log:

```bash
# check if audit logging is enabled
kubectl get pods -n kube-system | grep apiserver
```

The Elastic Agent Kubernetes integration captures audit events from the API server.
Filter in Kibana Discover:

```
kubernetes.audit.objectRef.resource: "networkpolicies"
```

This shows create/update/delete events for all NetworkPolicies.

## Dashboard Panel: Denied Traffic

If flow logs are available (Cilium Hubble or Calico), build a Kibana panel:

- **Type:** Lens → Line chart
- **Data view:** Index containing flow logs
- **X-axis:** `@timestamp`
- **Y-axis:** Count where `event.action: "denied"` or `verdict: "DROPPED"`
- **Break down by:** `source.namespace` or `destination.port`

## Alerting: Unexpected Egress

Create a Kibana rule:
- **Type:** Elasticsearch query
- **Query (KQL):** `event.action: "denied" AND NOT destination.ip: 10.* AND NOT destination.ip: 172.16.* AND NOT destination.ip: 192.168.*`
- **Threshold:** > 0 matches in 5 minutes
- **Action:** Webhook notification
