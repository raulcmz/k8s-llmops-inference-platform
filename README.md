# K8s LLMOps Inference Platform

A production-oriented LLMOps platform running on Kubernetes.

## Goal

This project demonstrates how to expose LLM backends through an internal gateway running on Kubernetes.

The initial backend is Ollama running outside the cluster. The gateway abstracts the backend so the platform can later support vLLM, SGLang, or cloud-hosted LLM providers.

## Initial Architecture

```text
Client
  ↓
Internal LLM Gateway
  ↓
External Ollama Backend
  ↓
Local LLM
```

## Current Backend

- Backend: Ollama
- Host: Windows machine
- Model examples:
- mistral:7b
- granite3.1-moe:3b
- nomic-embed-text

## Future Work

- Add FastAPI gateway
- Add Prometheus metrics
- Add MLflow benchmark tracking
- Add MinIO-backed benchmark artifacts
- Add vLLM backend