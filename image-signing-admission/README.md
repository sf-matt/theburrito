# Image Signing and Admission Lab Artifacts

Supporting application, public verification key, and Kubernetes policies for a
CloudSecBurrito image-signing and admission-control lab.

The directory preserves two distinct artifact roles: an intentionally unsigned
control and a separately built signing candidate. Keeping their digests
different is essential to the experiment.

## Related Walkthrough

- [Image Signing Redux](https://cloudsecburrito.com/image-signing-redux/)

The article owns the build, signing, verification, admission-test, and cleanup
procedures. This README records the repository artifacts and trust boundary.

## What Is Here

| Path | Purpose |
| --- | --- |
| `app.py` | Provides the single HTTP endpoint used by the demo images. |
| `test_app.py` | Checks the application response. |
| `Dockerfile` | Builds the non-root Gunicorn image and distinguishes demo variants. |
| `requirements.txt` | Pins the Python runtime dependencies. |
| `cosign.pub` | Public key used to verify the separately signed candidate. |
| `k8s/kyverno-image-policy.yaml` | Key-based Kyverno image-verification policy. |
| `k8s/sigstore-image-policy.yaml` | Sigstore policy-controller verification policy. |

## Published Artifact Model

The repository workflow publishes
`ghcr.io/sf-matt/image-signing-admission:unsigned` and an immutable
`sha-<commit>` tag as one multi-platform OCI index for `linux/amd64` and
`linux/arm64`.

That workflow is the canonical publisher for the unsigned control. It does not
build or sign the candidate. The signing candidate is deliberately published
and signed as a separate digest so verification and admission tests retain a
real negative control.

## Trust and Secret Boundary

- `cosign.pub` is public verification material and is intentionally tracked.
- `cosign.key` is private signing material, is ignored by Git, and must never be
  committed, copied into an image, or added to automation.
- A tag, OCI label, or successful image pull does not prove that an image is
  signed.
- The unsigned control must remain unsigned. Signing its digest destroys the
  comparison the lab is designed to make.
- Admission enforcement requires both a signed-allow result and an unsigned-deny
  result; signature verification alone is not admission evidence.

## Risks and Limitations

- The application is demo infrastructure, not a production service.
- The key-based flow depends on protecting the private key outside this
  repository.
- The policy manifests are examples for isolated lab clusters and require the
  matching controller and public key configuration described by the article.
- Registry tags can move. Use the immutable digest recorded during a specific
  walkthrough when reproducing evidence.
