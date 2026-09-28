# Kata Microagent Proof of Concept

A process-monitoring experiment that places a small sensor beside a workload in
a Kata Containers Pod and sends observations to a Flask receiver.

This is a visibility proof of concept, not an endpoint agent, runtime-security
product, or production detection system.

## Related Walkthrough

- [Runtime Security in Kata: Less Visibility, Better Signal](https://cloudsecburrito.com/runtime-security-in-kata-less-visibility-better-signal/)

The article explains the experiment, deployment sequence, attack simulation,
and observed results. This README describes the implementation and its limits.

## Architecture

```text
application container
        | shared Pod process namespace
        v
sensor container -- HTTP events --> receiver Service --> in-memory event list
```

The sensor polls `/proc`, compares processes with a small rule set and startup
executable baseline, and emits JSON events. The receiver keeps recent events in
memory and exposes a small HTML view and JSON endpoints.

## What Is Here

| Path | Purpose |
| --- | --- |
| `kata-sensor/` | Polling sensor, rules, event model, and container definition. |
| `kata-receiver/` | In-memory Flask receiver, UI, API, and container definition. |
| `kata_and_sensor.yaml` | Kata workload and sidecar sensor with a shared process namespace. |
| `receiver.yaml` | Namespace, receiver Deployment, and NodePort Service. |

The manifests assume a cluster with a working `kata-qemu` RuntimeClass and use
the `kata-demo` namespace.

## Detection Boundary

The rules focus on a small group of high-signal behaviors such as unexpected
shells, sensitive-file access, credential discovery, package-manager execution,
newly introduced executables, and remote-execution utilities. A match provides
context for investigation; it does not prove compromise or causality.

## Risks and Limitations

- Polling can miss short-lived processes and does not provide kernel-level
  visibility.
- The sensor sees the shared process namespace for its Pod, not other Pods or
  the Kubernetes node.
- The receiver is unauthenticated, uses plain HTTP, and stores data only in
  memory.
- The checked-in receiver is a NodePort and may be reachable beyond the
  intended host depending on cluster networking.
- The manifests use moving `latest` image tags, lack complete resource limits,
  and do not define hardened security contexts.
- Removing the receiver manifest also removes the `kata-demo` namespace. Review
  the article's cleanup procedure before deploying the lab.
