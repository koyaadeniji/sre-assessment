# Complete Environment Setup — Fresh Mac (16GB RAM)

Everything from a blank Mac to a running cluster with Elastic Stack, Online Boutique, and OTel.

---

## Phase 1: Install All Tools

Open Terminal and run each block in order.

### 1.1 — Install Homebrew (macOS package manager)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Follow the post-install instructions it prints — you'll need to add Homebrew to your PATH:

```bash
# For Apple Silicon Macs (M1/M2/M3/M4):
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"

# For Intel Macs:
echo 'eval "$(/usr/local/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/usr/local/bin/brew shellenv)"
```

Verify:
```bash
brew --version
```

### 1.2 — Install Docker Desktop

```bash
brew install --cask docker
```

Open Docker Desktop from Applications folder (or Spotlight: Cmd+Space → "Docker").

Accept the license agreement. Wait for it to start (whale icon in menu bar stops animating).

**Configure Docker Desktop resources:**
1. Click the Docker whale icon in the menu bar → **Settings** (gear icon)
2. Go to **Resources** → **Advanced**
3. Set:
   - **CPUs**: 6
   - **Memory**: 10 GB
   - **Swap**: 2 GB
   - **Virtual disk limit**: 60 GB
4. Click **Apply & Restart**
5. Wait for Docker to restart fully

Verify:
```bash
docker info | grep -E "CPUs|Total Memory"
# Should show: CPUs: 6, Total Memory: ~9.7GiB
```

### 1.3 — Install Kubernetes tools

```bash
brew install kubectl minikube helm
```

Verify:
```bash
kubectl version --client
minikube version
helm version
```

### 1.4 — Install useful extras

```bash
brew install curl jq watch
```

- `curl` — HTTP requests (traffic generation)
- `jq` — JSON parsing (reading k8s secrets)
- `watch` — repeat commands (monitoring pod status)

---

## Phase 2: Start the Kubernetes Cluster

### 2.1 — Create a 2-node cluster

```bash
minikube start \
  --nodes=2 \
  --cpus=4 \
  --memory=8g \
  --cni=calico \
  --driver=docker \
  --kubernetes-version=v1.28.0 \
  --addons=metrics-server
```

This takes 3-5 minutes. It creates:
- 2 Docker containers acting as Kubernetes nodes
- Calico CNI for NetworkPolicy enforcement
- metrics-server for `kubectl top`

Verify:
```bash
kubectl get nodes
```

Expected output:
```
NAME           STATUS   ROLES           AGE   VERSION
minikube       Ready    control-plane   2m    v1.28.0
minikube-m02   Ready    <none>          1m    v1.28.0
```

If a node shows `NotReady`, wait 1-2 minutes — Calico takes time to initialize.

### 2.2 — Enable NGINX Ingress Controller

```bash
minikube addons enable ingress
```

Verify:
```bash
kubectl get pods -n ingress-nginx
# Wait until the controller pod shows Running (1-2 min)
```

---

## Phase 3: Deploy the Elastic Stack (ECK)

### 3.1 — Install ECK Operator

The ECK operator manages Elasticsearch, Kibana, APM Server, and Elastic Agent as Kubernetes custom resources.

```bash
kubectl create -f https://download.elastic.co/downloads/eck/2.11.1/crds.yaml
kubectl apply -f https://download.elastic.co/downloads/eck/2.11.1/operator.yaml
```

Wait for the operator to be ready:
```bash
kubectl -n elastic-system rollout status deployment elastic-operator
# "deployment "elastic-operator" successfully rolled out"
```

### 3.2 — Deploy Elasticsearch, Kibana, APM Server, Fleet Server

```bash
cd ~/sre-assessment
kubectl apply -f infrastructure/elastic-agent-policies/eck-stack.yaml
```

This deploys everything into the `elastic-system` namespace. **Elasticsearch takes 3-5 minutes to start** because it needs to initialize the cluster and generate TLS certificates.

Watch the progress:
```bash
# In one terminal, watch all pods:
watch kubectl get pods -n elastic-system

# Or watch Elasticsearch specifically:
kubectl get elasticsearch -n elastic-system -w
# Wait until: elasticsearch   green   1   8.12.0   Ready
# Then Ctrl+C
```

Then check Kibana and APM Server:
```bash
kubectl get kibana -n elastic-system
# HEALTH=green

kubectl get apmserver -n elastic-system
# HEALTH=green
```

**Troubleshooting**: If Elasticsearch stays in `Pending`, check:
```bash
kubectl describe pod -n elastic-system -l elasticsearch.k8s.elastic.co/cluster-name=elasticsearch
# Look for events like "Insufficient memory" — means Docker needs more RAM
```

### 3.3 — Deploy Elastic Agent DaemonSet

```bash
kubectl apply -f infrastructure/elastic-agent-policies/elastic-agent-daemonset.yaml
```

Verify agents are running on both nodes:
```bash
kubectl get pods -n elastic-system -l agent.k8s.elastic.co/name=elastic-agent -o wide
# Should show 2 pods, one per node
```

### 3.4 — Get credentials (you'll need these later)

```bash
# Kibana password for the "elastic" user
ELASTIC_PASSWORD=$(kubectl get secret elasticsearch-es-elastic-user -n elastic-system \
  -o jsonpath='{.data.elastic}' | base64 -d)
echo "Elastic password: $ELASTIC_PASSWORD"

# APM Server secret token
APM_TOKEN=$(kubectl get secret apm-server-apm-token -n elastic-system \
  -o jsonpath='{.data.secret-token}' | base64 -d)
echo "APM token: $APM_TOKEN"
```

Save these somewhere — you'll need them.

---

## Phase 4: Deploy Online Boutique

### 4.1 — Deploy the 11 microservices

```bash
kubectl create namespace online-boutique

kubectl apply -n online-boutique \
  -f https://raw.githubusercontent.com/GoogleCloudPlatform/microservices-demo/main/release/kubernetes-manifests.yaml
```

Wait for all pods:
```bash
watch kubectl get pods -n online-boutique
# Wait until all pods show Running (2-3 min)
```

You should see these services:
```
adservice, cartservice, checkoutservice, currencyservice,
emailservice, frontend, loadgenerator, paymentservice,
productcatalogservice, recommendationservice, shippingservice,
redis-cart
```

### 4.2 — Verify the frontend works

```bash
# Port-forward the frontend
kubectl port-forward svc/frontend -n online-boutique 8080:80 &

# Test it
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080
# Should print: 200
```

Open http://localhost:8080 in your browser — you should see the Online Boutique shop.

Stop the port-forward for now:
```bash
kill %1 2>/dev/null
```

---

## Phase 5: Deploy OTel Collector (Gateway + Agent)

### 5.1 — Create the APM token secret

The OTel gateway needs the APM token to authenticate with the APM Server:

```bash
# Use the APM_TOKEN from Phase 3.4
kubectl create secret generic apm-token \
  --from-literal=token="$APM_TOKEN" \
  -n online-boutique
```

### 5.2 — Deploy OTel Collector

```bash
helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts
helm repo update

# DaemonSet agents (one per node)
helm install otel-agent open-telemetry/opentelemetry-collector \
  -f otel-collector/values-agent.yaml \
  -n online-boutique

# Gateway (single deployment)
helm install otel-gateway open-telemetry/opentelemetry-collector \
  -f otel-collector/values-gateway.yaml \
  -n online-boutique
```

Verify:
```bash
kubectl get pods -n online-boutique -l app.kubernetes.io/name=opentelemetry-collector
# Should see: otel-agent (2 pods, one per node) + otel-gateway (1 pod)
```

Check the gateway logs for successful connection to APM:
```bash
kubectl logs -n online-boutique -l app.kubernetes.io/instance=otel-gateway --tail=20
# Look for: "Everything is ready" or exporter connection messages
# If you see TLS errors, see Troubleshooting below
```

---

## Phase 6: Apply Network Policies

```bash
kubectl apply -f infrastructure/network-policies/network-policy.yaml
```

Verify policies are created:
```bash
kubectl get networkpolicies -n online-boutique
# Should show 7 policies
```

---

## Phase 7: Access All Services

Open 3 separate terminal tabs/windows:

**Terminal 1 — Kibana** (https://localhost:5601):
```bash
kubectl port-forward svc/kibana-kb-http -n elastic-system 5601:5601
```

**Terminal 2 — Frontend** (http://localhost:8080):
```bash
kubectl port-forward svc/frontend -n online-boutique 8080:80
```

**Terminal 3 — APM Server for RUM** (https://localhost:8200):
```bash
kubectl port-forward svc/apm-server-apm-http -n elastic-system 8200:8200
```

Now open in your browser:
- **Kibana**: https://localhost:5601 (accept the self-signed cert warning)
  - Username: `elastic`
  - Password: the one from Phase 3.4
- **Online Boutique**: http://localhost:8080

---

## Phase 8: Generate Traffic + Verify

```bash
cd ~/sre-assessment
chmod +x scripts/generate-traffic.sh
./scripts/generate-traffic.sh http://localhost:8080
```

Then verify in Kibana:

1. **Observability → APM → Services** — should list services
2. **Observability → APM → Traces** — click a transaction to see the trace waterfall
3. **Observability → APM → Service Map** — shows service dependencies
4. **Observability → Infrastructure → Inventory** — shows both nodes with CPU/memory/disk metrics

---

## Phase 9: Configure Fleet Integrations (for Section 3)

In Kibana, go to **Management → Fleet → Agent Policies**:

### 9.1 — System Integration (already included by default)
The Elastic Agent DaemonSet auto-enrolls with Fleet. Verify:
- Fleet → Agents — should show 2 healthy agents

### 9.2 — PostgreSQL Integration

First deploy PostgreSQL (Online Boutique doesn't include one):
```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm install postgresql bitnami/postgresql \
  -n online-boutique \
  --set auth.postgresPassword=assessment123 \
  --set primary.extendedConfiguration="shared_preload_libraries='pg_stat_statements'" \
  --set primary.initdb.scripts."enable-ext\.sql"="CREATE EXTENSION IF NOT EXISTS pg_stat_statements;"
```

Then in Kibana:
1. Fleet → Agent Policies → click your policy → **Add Integration**
2. Search "PostgreSQL" → Add
3. Configure:
   - Host: `postgres://postgresql.online-boutique.svc.cluster.local:5432/postgres`
   - Username: `postgres`
   - Password: `assessment123`
4. Save

### 9.3 — Redis Integration

Redis is already running (`redis-cart` in Online Boutique).

In Kibana:
1. Fleet → Agent Policies → Add Integration → **Redis**
2. Configure:
   - Host: `redis-cart.online-boutique.svc.cluster.local:6379`
   - No password
3. Save

### 9.4 — NGINX Integration

In Kibana:
1. Fleet → Agent Policies → Add Integration → **Nginx**
2. Configure:
   - Stub status URL: `http://ingress-nginx-controller.ingress-nginx.svc.cluster.local:10254/nginx_status`
3. Save

---

## Phase 10: Build + Export Dashboards

Build each dashboard in Kibana following `dashboards/README.md`, then export:

1. **Stack Management → Saved Objects**
2. Search for the dashboard name
3. Select checkbox → **Export** → check **Include related objects** → **Export**
4. Save downloaded `.ndjson` files to `~/sre-assessment/dashboards/`:
   - `service-health.ndjson`
   - `rum-performance.ndjson`
   - `business-transactions.ndjson`

Also export alerting rules:
1. Create all 11 rules from `infrastructure/alerting-rules/alerting-rules.yaml` in **Observability → Rules**
2. Export from Saved Objects as NDJSON

---

## Phase 11: Push to GitHub

```bash
cd ~/sre-assessment
git add -A
git status  # review what's being added
git commit -m "Add dashboard NDJSON exports and finalize assessment"
git push
```

---

## Troubleshooting

### Pods stuck in Pending
```bash
kubectl describe pod <pod-name> -n <namespace>
# Look at Events section. Common causes:
# - Insufficient memory → give Docker more RAM
# - Insufficient cpu → give Docker more CPUs
# - No persistent volume → minikube auto-provisions, just wait
```

### Elasticsearch OOMKilled
```bash
kubectl get pods -n elastic-system
# If STATUS=OOMKilled or CrashLoopBackOff:
# 1. Close heavy Mac apps (Chrome, Slack, VS Code)
# 2. Or reduce ES heap in eck-stack.yaml: -Xms512m -Xmx512m
```

### OTel Gateway can't connect to APM Server (TLS errors)
```bash
# The CA cert might not be available yet. Check:
kubectl get secret elasticsearch-es-http-ca-internal -n elastic-system
# If it doesn't exist, wait for Elasticsearch to fully initialize

# Copy the CA cert to the online-boutique namespace:
kubectl get secret elasticsearch-es-http-ca-internal -n elastic-system \
  -o jsonpath='{.data.ca\.crt}' | base64 -d > /tmp/elastic-ca.crt
kubectl create secret generic elasticsearch-es-http-ca-internal \
  --from-file=ca.crt=/tmp/elastic-ca.crt \
  -n online-boutique
```

### Network Policies blocking traffic
```bash
# If services can't talk to each other after applying network policies:
# Temporarily remove them to verify:
kubectl delete -f infrastructure/network-policies/network-policy.yaml

# Then re-apply once you've confirmed the app works without them
```

### Port-forward dies
```bash
# Port-forwards drop on idle. Restart them:
kubectl port-forward svc/kibana-kb-http -n elastic-system 5601:5601 &
kubectl port-forward svc/frontend -n online-boutique 8080:80 &
kubectl port-forward svc/apm-server-apm-http -n elastic-system 8200:8200 &
```

### Check resource usage
```bash
# Node-level
kubectl top nodes

# Pod-level (sorted by memory)
kubectl top pods -n elastic-system --sort-by=memory
kubectl top pods -n online-boutique --sort-by=memory
```

### Stop everything (save battery/RAM)
```bash
minikube stop
# Restart later with: minikube start
```

### Delete everything and start over
```bash
minikube delete
# Then start from Phase 2
```

---

## Quick Reference

| Service | Access | Credentials |
|---------|--------|-------------|
| Kibana | https://localhost:5601 | elastic / `kubectl get secret elasticsearch-es-elastic-user -n elastic-system -o jsonpath='{.data.elastic}' \| base64 -d` |
| Frontend | http://localhost:8080 | none |
| APM Server | https://localhost:8200 | Bearer token from apm-token secret |
| Elasticsearch | https://localhost:9200 | elastic / same as Kibana |
| PostgreSQL | postgresql:5432 | postgres / assessment123 |
| Redis | redis-cart:6379 | none |

| Command | What it does |
|---------|-------------|
| `minikube start` | Start the cluster |
| `minikube stop` | Stop (preserves state) |
| `minikube delete` | Destroy everything |
| `minikube dashboard` | Open Kubernetes dashboard in browser |
| `kubectl get pods -A` | See all pods across all namespaces |
| `kubectl logs <pod> -n <ns>` | Read pod logs |
| `kubectl describe pod <pod> -n <ns>` | Debug pod issues |
