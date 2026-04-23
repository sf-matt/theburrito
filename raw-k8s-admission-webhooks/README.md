# raw-k8s-admission-webhooks

This project contains a minimal, working Kubernetes **Validating Admission Webhook**, built from scratch using Python (Flask) and served over HTTPS.

The webhook denies any pod whose name contains the string `badpod`. It's designed to demonstrate how Kubernetes admission control works without relying on higher-level tools like Kyverno or Gatekeeper.

---

## Project Structure

```
raw-k8s-admission-webhooks/
├── certs/                  # TLS generation script
│   └── generate-certs.sh
├── server/                 # Webhook server code and Dockerfile
│   ├── app.py
│   ├── requirements.txt
│   └── Dockerfile
├── manifests/              # Kubernetes resources
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── webhook.yaml
│   ├── test-pod.yaml
├── ca.crt                  # Base64-encoded into webhook config
└── README.md               # You're here
```

---

## Getting Started

### 1. Generate TLS Certificates

Run the following script:

```bash
chmod +x certs/generate-certs.sh
./certs/generate-certs.sh
```

This will generate TLS certs for `webhook.default.svc` and place them into:
- `server/cert.pem`
- `server/key.pem`
- `ca.crt` (used for `caBundle`)


### 2. Build and Push Docker Image

Build the image (if not using Dockerhub just use your registry):

```bash
docker build -t docker.io/<your-username/webhook-server/<your-username>/webhook-server:latest ./server
docker push docker.io/<your-username>/webhook-server:latest
```

Update the image reference in `manifests/deployment.yaml`.


### 3. Create the TLS Secret in Kubernetes

```bash
kubectl create secret generic webhook-certs \
  --from-file=cert.pem=server/cert.pem \
  --from-file=key.pem=server/key.pem \
  -n default
```

### 4. Deploy the Webhook

Apply the deployment and service:

```bash
kubectl apply -f manifests/deployment.yaml
kubectl apply -f manifests/service.yaml
```

Confirm the pod is running:

```bash
kubectl get pods -l app=webhook
```


### 5. Register the Admission Webhook

Edit `manifests/webhook.yaml` and replace:

```yaml
caBundle: <REPLACE_WITH_BASE64_CA>
```

with the base64 output printed by the cert script. Then apply:

```bash
kubectl apply -f manifests/webhook.yaml
```


### 6. Test It

Apply the test pod:

```bash
kubectl apply -f manifests/test-pod.yaml
```

You should see:

```bash
Error from server: admission webhook "deny.badpod.webhook.dev" denied the request: Pod name 'badpod-test' is not allowed.
```

---

## Security Notes

- The image **mounts TLS certs from a Secret** instead of baking them in
- Flask runs under a non-root user (`USER webhook` in Dockerfile)
- No secrets are committed to Git

---

## Next Ideas

- Add a **Mutating Admission Webhook**
- Extend logic to match labels, namespaces, or container images
- Visualize webhook flow in a diagram
