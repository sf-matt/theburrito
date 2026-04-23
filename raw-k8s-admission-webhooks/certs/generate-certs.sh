#!/bin/bash

set -euo pipefail

SERVICE="webhook"
NAMESPACE="default"
TMPDIR=certs-tmp
CERTDIR=$(pwd)

mkdir -p "${TMPDIR}"
cd "${TMPDIR}"

# 1. Generate CA
openssl genrsa -out ca.key 2048
openssl req -x509 -new -nodes -key ca.key -subj "/CN=Admission CA" -days 3650 -out ca.crt

# 2. Generate server key and CSR
openssl genrsa -out server.key 2048
cat <<EOF > server.csr.conf
[ req ]
default_bits       = 2048
prompt             = no
default_md         = sha256
req_extensions     = req_ext
distinguished_name = dn

[ dn ]
CN = ${SERVICE}.${NAMESPACE}.svc

[ req_ext ]
subjectAltName = @alt_names

[ alt_names ]
DNS.1 = ${SERVICE}
DNS.2 = ${SERVICE}.${NAMESPACE}
DNS.3 = ${SERVICE}.${NAMESPACE}.svc
EOF

openssl req -new -key server.key -out server.csr -config server.csr.conf

# 3. Sign server cert with CA
cat <<EOF > server.ext
[ server_ext ]
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[ alt_names ]
DNS.1 = ${SERVICE}
DNS.2 = ${SERVICE}.${NAMESPACE}
DNS.3 = ${SERVICE}.${NAMESPACE}.svc
EOF

openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out server.crt -days 3650 -extensions server_ext -extfile server.ext

# Copy certs into server/ for Docker and ca.crt for webhook config
cp server.crt "${CERTDIR}/server/cert.pem"
cp server.key "${CERTDIR}/server/key.pem"
cp ca.crt "${CERTDIR}/ca.crt"

# Output base64 version of CA cert for webhook.yaml
echo ""
echo "Base64-encoded CA cert (for webhook.yaml caBundle):"
cat ca.crt | base64 | tr -d '\n'
echo ""
