# Kata Containers on GCP with Kubernetes

This project creates a disposable, single-node Kubernetes lab for the
[Kata Containers isolation walkthrough](https://cloudsecburrito.com/kata-containers-when-container-escape-stops-working/).
The GCE VM exposes nested virtualization so a Kata runtime can launch its guest
VMs with KVM.

The bootstrap installs:

- Ubuntu 22.04 on an `n2-standard-4` VM;
- Kubernetes 1.36.4 with containerd;
- Flannel 0.28.9;
- Helm 4.3.0, verified with its published SHA-256 checksum.

Kata is installed separately and pinned to 4.2.0 so that you can inspect the
Kubernetes node before changing its container runtime configuration.

## Prerequisites

- Terraform 1.5 or newer;
- a GCP project with billing and the Compute Engine API enabled;
- `gcloud` authenticated to that project;
- permission to create Compute Engine instances, disks, and firewall rules;
- permission to connect with Identity-Aware Proxy (IAP) and OS Login.

The firewall allows SSH only from Google's IAP TCP-forwarding range by default.
If you do not use IAP, override `ssh_source_ranges` with a trusted `/32` address.
The variable rejects `0.0.0.0/0`.

## Create the Lab

From this directory:

```bash
terraform init
terraform apply -var="project_id=YOUR_GCP_PROJECT_ID"
```

This creates billable GCP resources. Review the plan before approving it.

Connect through IAP using the generated command:

```bash
terraform output -raw ssh_command
```

Run the printed command. If the startup script is still running, inspect it
with:

```bash
sudo journalctl -u google-startup-scripts.service --no-pager
```

## Validate the Node

Configure `kubectl` for your OS Login user:

```bash
mkdir -p "$HOME/.kube"
sudo cp /etc/kubernetes/admin.conf "$HOME/.kube/config"
sudo chown "$(id -u):$(id -g)" "$HOME/.kube/config"
```

Then confirm that Kubernetes is healthy and KVM is available:

```bash
kubectl get nodes -o wide
kubectl get pods -A
kubectl version
containerd --version
ls -l /dev/kvm
helm version
```

Do not continue unless the node is `Ready` and `/dev/kvm` exists.

## Install Kata Containers

Clone this repository onto the node so the pinned Helm values and test manifest
are available:

```bash
git clone https://github.com/sf-matt/theburrito.git
cd theburrito/kata-gcp-k8s-lab
```

Install helm:

```bash
KATA_VERSION="4.2.0"
KATA_CHART="oci://ghcr.io/kata-containers/kata-deploy-charts/kata-deploy"

helm install kata-deploy "${KATA_CHART}" \
  --version "${KATA_VERSION}"
```

Wait for the installer and confirm that the expected runtime class exists:

```bash
kubectl rollout status daemonset/kata-deploy --timeout=10m
kubectl get runtimeclass kata-qemu-runtime-rs
kubectl get pods -A
```

## Compare the Isolation Boundaries

The test workloads are intentionally privileged and use the host PID namespace.
Run them only on this disposable node. They do **not** mount the node root: Kata
normally shares Kubernetes `hostPath` files into the guest, which would bypass
the filesystem boundary this comparison is meant to examine.

Apply the two deployments:

```bash
kubectl apply -f k8s_resources/escape.yaml
kubectl rollout status deployment/normal-escape --timeout=5m
kubectl rollout status deployment/kata-escape --timeout=5m

NORMAL_POD=$(kubectl get pod -l app=normal-escape -o jsonpath='{.items[0].metadata.name}')
KATA_POD=$(kubectl get pod -l app=kata-escape -o jsonpath='{.items[0].metadata.name}')
```

In the standard container, PID 1 belongs to the Kubernetes node. Enter its
namespaces and compare the kernel identity:

```bash
kubectl exec -it "${NORMAL_POD}" -- /bin/bash
uname -a
nsenter --target 1 --mount --uts --ipc --net --pid
uname -a
exit
exit
```

In the Kata container, the visible kernel and PID 1 belong to the guest VM:

```bash
kubectl exec -it "${KATA_POD}" -- /bin/bash
uname -a
nsenter --target 1 --mount --uts --ipc --net --pid
```

The Kata command is expected to report that `/bin/sh` does not exist. That does
not mean `nsenter` was denied: it targeted PID 1 in the guest and then could not
find the default shell in the guest root filesystem. The different guest kernel
is the important boundary evidence. This is a namespace-pivot comparison, not
proof that every possible VM escape is impossible.

## Cleanup

Remove the workloads and Kata installation while still connected:

```bash
kubectl delete -f k8s_resources/escape.yaml
helm uninstall kata-deploy
```

Then return to the Terraform directory on your workstation and destroy the GCP
resources:

```bash
terraform destroy -var="project_id=YOUR_GCP_PROJECT_ID"
```

Confirm the destroy plan before approving it.

## Limitations

- This is an educational, single-node lab, not a production architecture.
- The VM keeps an ephemeral external IP so startup can reach Ubuntu, Kubernetes,
  GitHub, and Helm repositories; inbound SSH remains restricted by the firewall.
- The Ubuntu `containerd` package follows the selected image's package repository
  rather than an independently pinned containerd build.
- Configuration validation does not prove the cloud bootstrap or isolation test
  succeeds. Record verified versions only after running the complete lab.
