# 🌯 CloudSecBurrito Labs

Hands-on security labs, infrastructure, and small utilities that support
[CloudSecBurrito](https://cloudsecburrito.com/) articles and experiments.

The goal is simple:

> Do fun stuff, show the real commands, and verify what actually happens.

## What's Here

| Project | Purpose | Status | Risk |
| --- | --- | --- | --- |
| [`basic-flask-app`](./basic-flask-app/) | Reusable one-route Flask container for demos | Local scaffold; GHCR publishing is prepared but not live | Low |
| [`kata-gcp-k8s-lab`](./kata-gcp-k8s-lab/) | Create a single-node Kubernetes and Kata Containers lab on GCP | Experimental lab | High: creates billable cloud resources and exposes intentionally unsafe workloads |
| [`kata-microagent`](./kata-microagent/) | Explore lightweight process monitoring beside a Kata workload | Proof of concept | High: unauthenticated receiver and heuristic detections |
| [`raw-k8s-admission-webhooks`](./raw-k8s-admission-webhooks/) | Build a validating admission webhook without a policy framework | Educational demo | Medium: cluster-wide admission behavior |

Each project is self-contained. Read its README before creating infrastructure
or applying Kubernetes manifests.

## Repository Philosophy

This is not a production-ready best-practices repository. It is a collection of
small, inspectable experiments designed to answer questions such as:

- What actually happens when this control is deployed?
- What security boundary does it provide?
- Where does it fail or create an observability gap?

That means the repository favors minimal abstractions, real commands,
reproducible outcomes, and honest documentation of limitations.

## Safety

Some labs intentionally include privileged containers, host mounts, exposed
services, permissive networking, or other unsafe configurations. These are part
of the experiment, not recommended defaults.

- Do not run these examples in production.
- Use an isolated test account, project, or cluster.
- Review manifests and scripts before running them.
- Never commit credentials, kubeconfigs, generated certificates, or Terraform
  state.
- Follow each project's cleanup instructions to avoid lingering access or cloud
  charges.

## Container Images

The [`basic-flask-app`](./basic-flask-app/) includes a GitHub Actions workflow
that will publish the following image after the workflow is committed to the
default branch and completes successfully:

```text
ghcr.io/sf-matt/basic-flask-app
```

Prefer immutable SHA tags or image digests in repeatable labs. Treat `latest`
as a convenience for short-lived experiments only.

## Blog Relationship

These projects support writing at [CloudSecBurrito](https://cloudsecburrito.com/).
Lab results should only be described as verified when the corresponding commands
were run and their observed behavior was recorded. Project READMEs should link
to the related article when one is available.

## Development and AI Assistance

This repository is maintained by Mateo and developed with assistance from
[OpenAI Codex](https://openai.com/codex/). The maintainer defines project
direction and architecture, reviews and tests changes, and owns all releases
and published claims.

Repository-specific instructions for coding agents live in
[`AGENTS.md`](./AGENTS.md).

## License

Licensed under the [MIT License](./LICENSE).

---

If it only works in a slide deck, it doesn't count.

If it works in a cluster and breaks in an interesting way—now we're talking.
