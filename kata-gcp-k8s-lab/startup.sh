#!/usr/bin/env bash
set -euxo pipefail

USERNAME="${username}"
K8S_VERSION="v1.32"
POD_CIDR="10.244.0.0/16"

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y \
  apt-transport-https \
  ca-certificates \
  curl \
  gpg \
  jq \
  git \
  vim \
  software-properties-common

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

apt-get update
apt-get install -y containerd

mkdir -p /etc/containerd
containerd config default >/etc/containerd/config.toml
sed -i 's/SystemdCgroup = false/SystemdCgroup = true/' /etc/containerd/config.toml

systemctl daemon-reload
systemctl enable containerd
systemctl restart containerd

mkdir -p /etc/apt/keyrings
curl -fsSL "https://pkgs.k8s.io/core:/stable:/$K8S_VERSION/deb/Release.key" \
  | gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg

cat >/etc/apt/sources.list.d/kubernetes.list <<EOF
deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/$K8S_VERSION/deb/ /
EOF

apt-get update
apt-get install -y kubelet kubeadm kubectl
apt-mark hold kubelet kubeadm kubectl

systemctl enable kubelet

PRIVATE_IP="$(hostname -I | awk '{print $1}')"
ADVERTISE_IP="$PRIVATE_IP"

kubeadm init \
  --pod-network-cidr="$POD_CIDR" \
  --apiserver-advertise-address="$ADVERTISE_IP" \
  --cri-socket=unix:///run/containerd/containerd.sock

mkdir -p /root/.kube
cp /etc/kubernetes/admin.conf /root/.kube/config

if id "$USERNAME" >/dev/null 2>&1; then
  mkdir -p "/home/$USERNAME/.kube"
  cp /etc/kubernetes/admin.conf "/home/$USERNAME/.kube/config"
  chown -R "$USERNAME:$USERNAME" "/home/$USERNAME/.kube"
fi

export KUBECONFIG=/etc/kubernetes/admin.conf

kubectl taint nodes --all node-role.kubernetes.io/control-plane- || true
kubectl apply -f https://github.com/flannel-io/flannel/releases/latest/download/kube-flannel.yml

sleep 30

curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash