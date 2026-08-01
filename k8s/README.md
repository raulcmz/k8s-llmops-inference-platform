# Kubernetes manifests (lab)

## Apply order

```bash
# 1) Point the cluster at Ollama on the Windows host (edit IP first)
kubectl apply -f k8s/ollama-backend/service.yaml
kubectl apply -f k8s/ollama-backend/endpoints.yaml

# 2) Gateway config + workload
kubectl apply -f k8s/gateway/configmap.yaml
kubectl apply -f k8s/gateway/deployment.yaml
kubectl apply -f k8s/gateway/service.yaml

# Optional: only if Prometheus Operator is installed
# kubectl apply -f k8s/gateway/servicemonitor.yaml
```

## Probes

| Probe | Path | Effect when failing |
|---|---|---|
| liveness | `/health` | Restart container |
| readiness | `/ready` | Remove pod from Service |

## Image caveat

`deployment.yaml` references `rcabe005/llm-gateway:0.1.1`. That image must include the `/ready` endpoint (T1). If probes fail with 404, rebuild/push an image from current `main` and update the tag.
