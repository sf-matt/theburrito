# Basic Flask App

A minimal, reusable Flask container used as supporting infrastructure in
CloudSecBurrito demos and labs. It is deliberately small so another experiment
can depend on an HTTP endpoint without bringing in a larger sample application.

## What Is Here

| Path | Purpose |
| --- | --- |
| `app.py` | Defines the single `GET /` JSON endpoint and `APP_MESSAGE` override. |
| `test_app.py` | Checks the default and configured responses. |
| `Dockerfile` | Packages the app under Gunicorn as a non-root container. |
| `requirements.txt` | Pins the Python runtime dependencies. |
| `.dockerignore` | Keeps local and repository-only files out of the image context. |

## Published Artifact

The repository workflow publishes `ghcr.io/sf-matt/basic-flask-app` for
`linux/amd64` and `linux/arm64`. The default branch produces `latest` and an
immutable short-SHA tag; Git tags can produce version tags.

Treat `latest` as a convenience for short-lived experiments. Use a SHA tag or
image digest when a lab result must remain reproducible.

## Interface and Boundaries

- The only application route is `GET /`.
- `APP_MESSAGE` changes the returned message without changing the image.
- There is no authentication, authorization, persistence, or TLS termination.
- This is demo infrastructure, not a production service or reference
  architecture.

There is no dedicated CloudSecBurrito walkthrough for this utility. Articles
that need a small HTTP workload may reuse it as a supporting artifact.
