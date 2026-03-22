#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <image>" >&2
  exit 1
fi

IMAGE="$1"
MONITORING_NAMESPACE="monitoring"
SMOKE_NAMESPACE="smoke"
SMOKE_POD_NAME="bad-image"
SMOKE_IMAGE="does-not-exist.invalid/example:latest"
POLL_ATTEMPTS="${POLL_ATTEMPTS:-12}"
POLL_SLEEP_SECONDS="${POLL_SLEEP_SECONDS:-10}"

kubectl create namespace "${MONITORING_NAMESPACE}" >/dev/null 2>&1 || true
kubectl apply -f deploy/00-roles.yaml
kubectl apply -f deploy/01-config.yaml
sed "s#ghcr.io/taihen/kubernetes-event-exporter:latest#${IMAGE}#" deploy/02-deployment.yaml | kubectl apply -f -
kubectl -n "${MONITORING_NAMESPACE}" rollout status deployment/event-exporter --timeout=300s

kubectl create namespace "${SMOKE_NAMESPACE}" >/dev/null 2>&1 || true
kubectl -n "${SMOKE_NAMESPACE}" delete pod "${SMOKE_POD_NAME}" --ignore-not-found=true >/dev/null 2>&1 || true
kubectl -n "${SMOKE_NAMESPACE}" run "${SMOKE_POD_NAME}" --image="${SMOKE_IMAGE}" --restart=Never

for ((attempt=1; attempt<=POLL_ATTEMPTS; attempt++)); do
  logs="$(kubectl -n "${MONITORING_NAMESPACE}" logs deployment/event-exporter --tail=400 2>/dev/null || true)"
  while IFS= read -r line; do
    if [[ "${line}" == *'"namespace":"smoke"'* && "${line}" == *'"name":"bad-image"'* ]]; then
      printf '%s\n' "${line}"
      exit 0
    fi
  done <<< "${logs}"
  sleep "${POLL_SLEEP_SECONDS}"
done

echo "smoke test failed: exporter never logged the smoke pod event" >&2
kubectl -n "${SMOKE_NAMESPACE}" get events --sort-by=.lastTimestamp || true
kubectl -n "${MONITORING_NAMESPACE}" logs deployment/event-exporter --tail=400 || true
exit 1
