# Kata Microagent Proof of Concept

A small experiment that places a process-monitoring sensor beside a workload in
a Kata Containers Pod and sends observations to a Flask receiver.

This is a proof of concept for exploring visibility inside a sandboxed workload.
It is not an endpoint security agent, runtime security product, or production
detection system.

## How It Works

The Pod in `kata_and_sensor.yaml` enables a shared process namespace:

```text
application container
        │ shared Pod process namespace
        ▼
sensor container ──HTTP events──> receiver Service ──> in-memory event list
```

The sensor polls `/proc`, compares observed processes with a small ruleset and
startup executable baseline, and emits JSON events. The receiver stores recent
events in memory and exposes a basic HTML view and JSON endpoints.

## Prerequisites

- A Kubernetes cluster with a working `kata-qemu` RuntimeClass
- Docker or another OCI-compatible image builder
- A registry accessible by the cluster
- `kubectl`

The manifests use the `kata-demo` namespace.

## Build the Images

Choose immutable image tags, then build and push both components:

```bash
export SENSOR_IMAGE="YOUR_REGISTRY/kata-sensor:YOUR_TAG"
export RECEIVER_IMAGE="YOUR_REGISTRY/kata-receiver:YOUR_TAG"

docker build -t "$SENSOR_IMAGE" ./kata-sensor
docker build -t "$RECEIVER_IMAGE" ./kata-receiver
docker push "$SENSOR_IMAGE"
docker push "$RECEIVER_IMAGE"
```

Update the image references in `kata_and_sensor.yaml` and `receiver.yaml` before
deploying.

## Deploy

Deploy the receiver first because its manifest creates the namespace:

```bash
kubectl apply -f receiver.yaml
kubectl rollout status deployment/kata-receiver --namespace kata-demo
kubectl apply -f kata_and_sensor.yaml
kubectl wait --for=condition=Ready pod/kata-app --namespace kata-demo --timeout=120s
```

Inspect the sensor output:

```bash
kubectl logs kata-app --container sensor --namespace kata-demo
```

Access the receiver without exposing the NodePort beyond the lab host:

```bash
kubectl port-forward service/kata-receiver 8080:80 --namespace kata-demo
```

Then open `http://127.0.0.1:8080/` or query the JSON endpoints:

```bash
curl http://127.0.0.1:8080/events
curl http://127.0.0.1:8080/sensors
```

## Expected Result

The receiver should show a `sensor_started` event followed by periodic
heartbeats. Processes matching the proof-of-concept rules may produce additional
events. Record the actual output and image versions before describing a run as
verified.

## Cleanup

```bash
kubectl delete -f kata_and_sensor.yaml
kubectl delete -f receiver.yaml
```

Deleting `receiver.yaml` also deletes the `kata-demo` namespace and everything
remaining inside it.

## Limitations and Risks

- Detection is based on periodic `/proc` polling and simple string matching, so
  short-lived processes and renamed or unexpected tools may be missed.
- A matching process is context, not proof of malicious activity or causality.
- The sensor depends on Pod process namespace sharing and does not observe other
  Pods or the Kubernetes node.
- The receiver is unauthenticated, uses plain HTTP, and stores data only in
  process memory.
- The checked-in receiver Service is a NodePort and may be reachable beyond the
  intended host depending on cluster networking.
- The existing manifests use moving `latest` image tags. Replace them with
  immutable tags or digests for repeatable experiments.
- The containers do not yet define complete resource limits or hardened
  security contexts.
