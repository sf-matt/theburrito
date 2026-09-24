# Image Signing and Admission: Unsigned Baseline

This project creates the unsigned control artifact for a future image-signing
and admission lab. It packages a minimal Flask application as
`ghcr.io/sf-matt/image-signing-admission:unsigned` so later phases can compare
signed and unsigned image behavior.

This phase intentionally creates an unsigned control artifact. It does not
generate signing keys, sign the image, or install or configure an admission
controller or policy.

## Prerequisites

- Python 3.13 or newer and `venv` for local tests
- Docker with the Buildx plugin
- A Docker builder capable of building `linux/amd64` and `linux/arm64`
- [`crane`](https://github.com/google/go-containerregistry/tree/main/cmd/crane)
  and `jq` for remote index inspection
- For publication only, permission to publish the target GHCR package and a
  GitHub classic personal access token (PAT) with `write:packages`

The repository workflow is the canonical publisher. After these files reach
`main`, `.github/workflows/publish-image-signing-admission.yml` tests the app,
publishes the `unsigned` and immutable `sha-<commit>` tags with the repository's
`GITHUB_TOKEN`. It also publishes separate `signing-candidate` and immutable
`signing-candidate-sha-<commit>` tags. Both artifacts are unsigned when the
workflow publishes them, and the GHCR package remains connected to this
repository. The workflow can also be started manually with `workflow_dispatch`
after it exists on the default branch.

## Test with Python

Create a local virtual environment, install the pinned dependencies, and run
the unit tests:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest -v
```

## Build and run the native-platform container

From this directory, build the unsigned image for the host platform:

```bash
IMAGE="ghcr.io/sf-matt/image-signing-admission"
UNSIGNED_IMAGE="${IMAGE}:unsigned"

docker build \
  --build-arg DEMO_VARIANT=unsigned \
  --tag "${UNSIGNED_IMAGE}" \
  .

docker run --rm --name image-signing-admission -p 8080:8080 \
  "${UNSIGNED_IMAGE}"
```

In another terminal, exercise the only HTTP route:

```bash
curl --fail --silent --show-error http://localhost:8080/
```

Stop the foreground container with `Ctrl-C` when finished.

## Authenticate to GHCR for a manual publish

Create a classic PAT with `write:packages`. Read it without echoing it, pass it
to Docker through standard input, and remove it from the shell environment:

```bash
read -s GHCR_PAT
printf '%s' "${GHCR_PAT}" | docker login ghcr.io --username sf-matt --password-stdin
unset GHCR_PAT
```

Do not put the PAT in a command argument, file, shell history, image, or Git.

## Manually publish the multi-platform unsigned image

The repository workflow should normally perform the publication. Warning: the
following fallback `--push` command creates or updates an external GHCR package
outside GitHub Actions. Run it only when publication has been explicitly
authorized.

Set the image references, then publish one tag backed by a combined OCI index:

```bash
IMAGE="ghcr.io/sf-matt/image-signing-admission"
UNSIGNED_IMAGE="${IMAGE}:unsigned"

docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --build-arg DEMO_VARIANT=unsigned \
  --tag "${UNSIGNED_IMAGE}" \
  --push \
  .
```

After the push succeeds, resolve the tag to the immutable top-level index
digest and construct its digest-pinned reference:

```bash
UNSIGNED_DIGEST=$(crane digest "${UNSIGNED_IMAGE}")
UNSIGNED_REF="${IMAGE}@${UNSIGNED_DIGEST}"
printf '%s\n' "${UNSIGNED_REF}"
```

Inspect that immutable reference and confirm that its top-level media type is
an OCI image index or Docker manifest list:

```bash
crane manifest "${UNSIGNED_REF}" | jq -r '.mediaType'
```

Then list the runnable platform manifests:

```bash
crane manifest "${UNSIGNED_REF}" | \
  jq -r '
    .manifests[]
    | select(.platform.os == "linux")
    | [.platform.os, .platform.architecture]
    | @tsv
  '
```

The image is multi-platform only after the immutable index reports both
`linux/amd64` and `linux/arm64`. Extra `unknown/unknown` entries can be Buildx
provenance attestations and do not replace either runnable image manifest.

## Prepare the signing candidate

The article preserves `sha-51f4df6` as its unsigned control. The
`signing-candidate` tag identifies a separately built digest intended for the
manual signing exercise. Publishing the candidate does not sign it. Its
`io.cloudsecburrito.cosign-demo=signing-candidate` label also ensures its image
configuration differs from the unsigned control.

After the workflow publishes both artifacts, resolve their tags to immutable
top-level index digests and confirm that they differ:

```bash
cd /Users/mateo/Desktop/theburrito/image-signing-admission

IMAGE="ghcr.io/sf-matt/image-signing-admission"

UNSIGNED_DIGEST=$(crane digest "${IMAGE}:sha-51f4df6")
UNSIGNED_REF="${IMAGE}@${UNSIGNED_DIGEST}"

SIGNED_DIGEST=$(crane digest "${IMAGE}:signing-candidate")
SIGNED_REF="${IMAGE}@${SIGNED_DIGEST}"

printf 'Unsigned control:  %s\n' "${UNSIGNED_REF}"
printf 'Signing candidate: %s\n' "${SIGNED_REF}"

if [ "${SIGNED_DIGEST}" = "${UNSIGNED_DIGEST}" ]; then
  echo "The digests match. Stop before signing."
  exit 1
fi
```

Only the candidate digest should receive a Cosign signature. Keep this signing
step manual so the exercise retains its key-based trust model. Generate the key
pair inside this project directory:

```bash
cosign generate-key-pair
```

`cosign.key` is private key material and must never enter Git. This project's
`.gitignore` excludes it. `cosign.pub` is the public verification key and will
eventually be committed after the signing evidence is captured.

Authenticate without printing or storing the classic PAT, then sign only the
candidate's immutable digest:

```bash
read -s GHCR_PAT
printf '%s' "${GHCR_PAT}" |
  docker login ghcr.io --username sf-matt --password-stdin
unset GHCR_PAT

cosign sign \
  --recursive \
  --key cosign.key \
  "${SIGNED_REF}"
```

Verify the expected contrast:

```bash
cosign verify --key cosign.pub "${SIGNED_REF}"
cosign verify --key cosign.pub "${UNSIGNED_REF}"
```

The candidate verification must succeed, while verification of the preserved
unsigned control must fail. After capturing that evidence, commit only
`image-signing-admission/cosign.pub`; never commit `cosign.key`. Signatures stay
attached to the candidate digest in GHCR rather than being committed here.

## Expected results

The unit tests pass, the native container runs as a non-root user under
Gunicorn, and `GET /` returns:

```json
{"message":"Hello from the unsigned image-signing admission baseline!"}
```

For an authorized publication, `crane digest` returns a `sha256:` digest for
the top-level index and the platform query includes:

```text
linux	amd64
linux	arm64
```

The built image also carries these labels:

```text
io.cloudsecburrito.cosign-demo=unsigned
org.opencontainers.image.source=https://github.com/sf-matt/theburrito
```

## Limitations and risks

- Both workflow-built images are deliberately unsigned at publication; neither
  should be treated as trusted because of its tag or label.
- The workflow contains no signing keys, signatures, admission policies,
  cluster manifests, or signed-image automation.
- A tag is mutable. Use `UNSIGNED_REF` when a later experiment must identify
  the exact published index.
- Publishing changes external GHCR state and may expose the package according
  to the repository or package visibility settings.
- This educational app is not production-ready and has only one unauthenticated
  route.

## Cleanup

Stop a detached local container if one is running, remove the local image, log
out of GHCR, and deactivate the Python environment:

```bash
docker rm --force image-signing-admission 2>/dev/null || true
docker image rm "${UNSIGNED_IMAGE}" 2>/dev/null || true
docker logout ghcr.io
deactivate
```

If an authorized push created a package that should not remain in GHCR, delete
that package or version through GitHub's package settings. That remote deletion
is separate from local cleanup and cannot be undone by deleting this checkout.
