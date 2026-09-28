# Raw Kubernetes Admission Webhook

A minimal Kubernetes `ValidatingAdmissionWebhook` built with Python and Flask.
It denies creation of Pods whose names contain `badpod` and allows other Pod
creation requests.

This is an educational demonstration of the admission request and response
flow, not a production webhook.

## Related Walkthrough

- [Control Issues: Tales of Kubernetes Admission](https://cloudsecburrito.com/control-issues-tales-of-kubernetes-admission/)

The article contains the deployment procedure, request-flow explanation,
validation steps, expected results, and cleanup commands. This README documents
the supporting implementation and its safety boundary.

## What Is Here

| Path | Purpose |
| --- | --- |
| `server/app.py` | Handles AdmissionReview requests and returns the allow or deny decision. |
| `server/test_app.py` | Exercises the webhook response contract. |
| `server/Dockerfile` | Packages the Flask webhook server. |
| `certs/generate-certs.sh` | Generates local TLS material for the in-cluster Service name. |
| `manifests/deployment.yaml` | Runs the webhook server in the `default` namespace. |
| `manifests/service.yaml` | Exposes the server to the Kubernetes API server. |
| `manifests/webhook.yaml` | Registers the cluster-scoped validating webhook. |
| `manifests/bad-pod.yaml` | Provides the intentionally denied test resource. |

The published image is
`ghcr.io/sf-matt/raw-k8s-admission-webhook`. Its workflow builds runnable
manifests for `linux/amd64` and `linux/arm64` and publishes an immutable
short-SHA tag alongside `latest`.

## Behavior and Trust Boundary

The webhook handles Pod `CREATE` operations. It returns an AdmissionReview with
the request UID and rejects names containing `badpod`. The registration uses
`failurePolicy: Fail`, so an installed but unavailable webhook can block
matching Pod creation.

Generated certificates and private keys are local artifacts and must remain
untracked. The CA value in the webhook manifest is a placeholder that the
walkthrough replaces for a lab run.

## Risks and Limitations

- The admission rule is only a small name check and is not a meaningful
  production policy.
- Malformed AdmissionReview requests can produce an application error.
- The container runs as root and uses Flask's development server.
- The example has no high-availability design, certificate rotation, metrics,
  resource limits, or hardened Pod security context.
- The resources use the `default` namespace and register a cluster-scoped
  webhook. Use only an isolated or disposable cluster.
- Cleanup must remove the `ValidatingWebhookConfiguration` before the backing
  Deployment, Service, Secret, and test Pod so the fail-closed webhook cannot
  interfere with later Pod creation.
