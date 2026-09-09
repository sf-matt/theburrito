# Raw Kubernetes Admission Webhook

A minimal Kubernetes `ValidatingAdmissionWebhook` built with Python and Flask.
It denies creation of Pods whose names contain `badpod` and allows other Pod
creation requests.

This is an educational demonstration of the admission request and response
flow. It is not a production webhook.

## Prerequisites

- Docker or another OCI-compatible image builder
- A container registry accessible by the cluster
- `kubectl` access to an isolated test cluster
- OpenSSL and a shell with `base64`

The example installs resources in the `default` namespace and registers a
cluster-scoped webhook configuration. Review the manifests before continuing.

## Project Structure

```text
raw-k8s-admission-webhooks/
├── certs/
│   └── generate-certs.sh
├── manifests/
│   ├── bad-pod.yaml
│   ├── deployment.yaml
│   ├── service.yaml
│   └── webhook.yaml
├── server/
│   ├── app.py
│   ├── Dockerfile
│   └── requirements.txt
└── README.md
```

## 1. Generate TLS Certificates

From this directory, run:

```bash
./certs/generate-certs.sh
```

The script creates:

- `server/cert.pem`
- `server/key.pem`
- `ca.crt`

These generated files are ignored by Git. The script also prints the
base64-encoded CA certificate needed by the webhook configuration.

## 2. Build and Push the Image

Choose an image name and immutable tag in a registry your cluster can pull:

```bash
export WEBHOOK_IMAGE="YOUR_REGISTRY/webhook-server:YOUR_TAG"
docker build -t "$WEBHOOK_IMAGE" ./server
docker push "$WEBHOOK_IMAGE"
```

Replace the placeholder image in `manifests/deployment.yaml` with that exact
reference.

## 3. Create the TLS Secret

The Deployment mounts this Secret at `/app/certs`, which matches the paths used
by the Flask server:

```bash
kubectl create secret generic webhook-certs \
  --from-file=cert.pem=server/cert.pem \
  --from-file=key.pem=server/key.pem \
  --namespace default
```

## 4. Deploy the Server

```bash
kubectl apply -f manifests/deployment.yaml
kubectl apply -f manifests/service.yaml
kubectl rollout status deployment/webhook --namespace default
```

## 5. Register the Webhook

Replace `<REPLACE_WITH_BASE64_CA>` in `manifests/webhook.yaml` with the CA value
printed by the certificate script, then run:

```bash
kubectl apply -f manifests/webhook.yaml
```

The configuration uses `failurePolicy: Fail`. If the webhook is registered but
unavailable, matching Pod creation requests can fail. Keep a separate terminal
available for cleanup.

## 6. Verify the Behavior

```bash
kubectl apply -f manifests/bad-pod.yaml
```

Expected result:

```text
Error from server: admission webhook "deny.badpod.webhook.dev" denied the request: Pod name 'badpod-test' is not allowed.
```

Confirm that another Pod name is allowed before treating the demo as verified.

```bash
kubectl run goodpod \
  --image=busybox:1.36.1 \
  --restart=Never \
  -- sleep 3600
kubectl get pod goodpod
```

## Cleanup

Remove the cluster-scoped webhook first so it cannot block later Pod creation:

```bash
kubectl delete -f manifests/webhook.yaml
kubectl delete -f manifests/deployment.yaml
kubectl delete -f manifests/service.yaml
kubectl delete pod goodpod --ignore-not-found
kubectl delete secret webhook-certs --namespace default
```

## Limitations and Security Notes

- The server performs only a small name check and assumes a valid AdmissionReview
  request. Malformed requests can produce an application error.
- TLS material is generated locally and injected through a Kubernetes Secret;
  it is not baked into the container image.
- The current container runs as root and uses Flask's development server.
- The example has no availability design, certificate rotation, metrics,
  resource limits, or hardened Pod security context.
- Deploy only in a disposable or isolated cluster.
