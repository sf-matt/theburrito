# Kata on GCP with K3s

This Terraform creates a single GCE VM suitable for a Kata lab:
- nested virtualization enabled
- Intel Haswell minimum CPU platform
- Ubuntu 22.04
- K8s installed at boot
- Helm installed at boot

## Usage

```bash
terraform init
terraform apply -var="project_id=YOUR_GCP_PROJECT_ID"
```

## On the node

Hook up:

```bash
mkdir -p $HOME/.kube
sudo cp /etc/kubernetes/admin.conf $HOME/.kube/config
sudo chown $(id -u):$(id -g) $HOME/.kube/config
```

Validate the substrate:

```bash
ls -l /dev/kvm
kubectl get nodes
kubectl get pods -A
```

Install Kata:

```bash
export VERSION=$(curl -sSL https://api.github.com/repos/kata-containers/kata-containers/releases/latest | jq .tag_name | tr -d '"')
export CHART="oci://ghcr.io/kata-containers/kata-deploy-charts/kata-deploy"
helm install kata-deploy "${CHART}" --version "${VERSION}"
kubectl get runtimeclass #to validate
```

Test escape scenarios:

```bash
kubectl apply -f k8s_resources/escape.yaml
...
```

## Notes

- This is intentionally a single-node lab.
- The point is to configure a basic Kata test bed.
