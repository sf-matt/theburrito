#!/usr/bin/env bash
set -Eeuo pipefail

KUBERNETES_MINOR="v1.36"
KUBERNETES_PACKAGE_VERSION="1.36.4-1.1"
FLANNEL_VERSION="v0.28.9"
HELM_VERSION="v4.3.0"
HELM_SHA256="86584a54def73570558f66f5111cc53dfed56689637ae32c1201205d494f54fb"
POD_CIDR="10.244.0.0/16"

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y \
  apt-transport-https \
  ca-certificates \
  containerd \
  curl \
  git \
  gpg \
  jq

swapoff -a
sed -i '/ swap / s/^/#/' /etc/fstab || true

cat >/etc/modules-load.d/k8s.conf <<'EOF'
overlay
br_netfilter
EOF

modprobe overlay
modprobe br_netfilter

cat >/etc/sysctl.d/99-kubernetes-cri.conf <<'EOF'
net.bridge.bridge-nf-call-iptables = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward = 1
EOF

sysctl --system

mkdir -p /etc/containerd
containerd config default >/etc/containerd/config.toml
sed -i 's/SystemdCgroup = false/SystemdCgroup = true/' /etc/containerd/config.toml

systemctl enable --now containerd

mkdir -p /etc/apt/keyrings
curl -fsSL "https://pkgs.k8s.io/core:/stable:/${KUBERNETES_MINOR}/deb/Release.key" \
  | gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg

cat >/etc/apt/sources.list.d/kubernetes.list <<EOF
deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/${KUBERNETES_MINOR}/deb/ /
EOF

apt-get update
apt-get install -y \
  kubeadm="${KUBERNETES_PACKAGE_VERSION}" \
  kubectl="${KUBERNETES_PACKAGE_VERSION}" \
  kubelet="${KUBERNETES_PACKAGE_VERSION}"
apt-mark hold kubeadm kubectl kubelet

systemctl enable kubelet

ADVERTISE_IP="$(curl -fsS \
  -H 'Metadata-Flavor: Google' \
  'http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/ip')"

kubeadm init \
  --kubernetes-version="v${KUBERNETES_PACKAGE_VERSION%-1.1}" \
  --pod-network-cidr="${POD_CIDR}" \
  --apiserver-advertise-address="${ADVERTISE_IP}" \
  --cri-socket=unix:///run/containerd/containerd.sock

mkdir -p /root/.kube
install -m 0600 /etc/kubernetes/admin.conf /root/.kube/config
export KUBECONFIG=/etc/kubernetes/admin.conf

kubectl taint nodes --all node-role.kubernetes.io/control-plane- || true
kubectl apply -f "https://github.com/flannel-io/flannel/releases/download/${FLANNEL_VERSION}/kube-flannel.yml"
kubectl rollout status daemonset/kube-flannel-ds \
  --namespace kube-flannel \
  --timeout=5m
kubectl wait --for=condition=Ready node --all --timeout=5m

HELM_TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${HELM_TMP_DIR}"' EXIT
HELM_ARCHIVE="${HELM_TMP_DIR}/helm.tar.gz"

curl -fsSL \
  "https://get.helm.sh/helm-${HELM_VERSION}-linux-amd64.tar.gz" \
  -o "${HELM_ARCHIVE}"
printf '%s  %s\n' "${HELM_SHA256}" "${HELM_ARCHIVE}" | sha256sum --check --status
tar -xzf "${HELM_ARCHIVE}" -C "${HELM_TMP_DIR}"
install -m 0755 "${HELM_TMP_DIR}/linux-amd64/helm" /usr/local/bin/helm

kubectl version
helm version
