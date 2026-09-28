# Kata Containers on GCP with Kubernetes

Terraform and Kubernetes artifacts for a disposable, single-node GCP lab with
nested virtualization. The environment exists to compare a privileged standard
container with a Kata-backed workload and observe where the isolation boundary
moves.

## Related Walkthrough

- [Kata Containers: When "Container Escape" Stops Working](https://cloudsecburrito.com/kata-containers-when-container-escape-stops-working/)

The article owns the setup sequence, commands, expected output, interpretation,
and cleanup procedure. This README is an inventory and safety boundary for the
files in this directory.

## What Is Here

| Path | Purpose |
| --- | --- |
| `main.tf` | Defines the GCP network, restricted IAP SSH path, disk, and nested-virtualization VM. |
| `variables.tf` | Declares the project, region, zone, machine, image, disk, and SSH-source inputs. |
| `outputs.tf` | Exposes the instance details and generated IAP SSH command. |
| `startup.sh` | Bootstraps containerd, Kubernetes, Flannel, and Helm on the node. |
| `k8s_resources/escape.yaml` | Defines the intentionally privileged standard and Kata comparison workloads. |

## Version and Design Baseline

The checked-in configuration currently targets:

- Ubuntu 22.04 on an `n2-standard-4` GCE VM;
- Kubernetes 1.36.4 with containerd;
- Flannel 0.28.9;
- Helm 4.3.0, verified by its published SHA-256 checksum;
- Kata Containers 4.2.0, installed separately by the walkthrough.

The VM exposes nested virtualization so Kata can reach KVM. Kata is intentionally
not installed during cloud bootstrap: the article compares the node before and
after the runtime is added.

## Requirements and Cost Boundary

The artifacts assume a GCP project with billing, the Compute Engine API, and
permissions for instances, disks, firewall rules, IAP, and OS Login. Terraform
1.5 or newer and an authenticated `gcloud` environment are also assumed by the
walkthrough.

Creating this environment incurs GCP charges until its resources are destroyed.
Read the article's cleanup section before provisioning anything.

## Risks and Limitations

- The Kubernetes workloads are intentionally privileged and use the host PID
  namespace. Run them only in the disposable lab.
- The manifest deliberately avoids mounting the node root because a Kubernetes
  `hostPath` shared into the Kata guest would bypass the filesystem comparison.
- Inbound SSH is restricted to Google's IAP TCP-forwarding range by default.
  The variable rejects `0.0.0.0/0`; any override should be a trusted source.
- The VM retains an ephemeral external IP so bootstrap can reach package,
  Kubernetes, GitHub, and Helm endpoints.
- The Ubuntu `containerd` package follows the selected image's package
  repository rather than an independently pinned containerd build.
- A namespace-pivot comparison demonstrates this specific boundary; it does not
  prove that every VM escape is impossible.
- Static configuration validation does not prove that the cloud bootstrap or
  isolation experiment succeeds.
