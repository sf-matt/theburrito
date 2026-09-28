# 🌯 CloudSecBurrito Labs

Hands-on security labs, infrastructure, and small utilities that support
[CloudSecBurrito](https://cloudsecburrito.com/) articles and experiments.

The split is intentional:

> The repository holds the artifacts. The blog tells the story and walks
> through the lab.

## What's Here

| Project | Purpose | Status | Risk |
| --- | --- | --- | --- |
| [`basic-flask-app`](./basic-flask-app/) | Reusable one-route Flask container for demos | Published to GHCR for AMD64 and ARM64 | Low |
| [`image-signing-admission`](./image-signing-admission/) | Establish an unsigned control image for image-signing and admission experiments | Experimental unsigned baseline | Low: intentionally unsigned artifact |
| [`kata-gcp-k8s-lab`](./kata-gcp-k8s-lab/) | Create a single-node Kubernetes and Kata Containers lab on GCP | Experimental lab | High: creates billable cloud resources and exposes intentionally unsafe workloads |
| [`kata-microagent`](./kata-microagent/) | Explore lightweight process monitoring beside a Kata workload | Proof of concept | High: unauthenticated receiver and heuristic detections |
| [`raw-k8s-admission-webhooks`](./raw-k8s-admission-webhooks/) | Build a validating admission webhook without a policy framework | Educational demo | Medium: cluster-wide admission behavior |

Each project README describes the checked-in artifacts, dependencies, and risk
boundary. When a project has a hands-on walkthrough, the README points to the
related CloudSecBurrito article instead of duplicating its procedure.

## Repository Philosophy

This is not a production-ready best-practices repository. It is a collection of
small, inspectable experiments designed to answer questions such as:

- What actually happens when this control is deployed?
- What security boundary does it provide?
- Where does it fail or create an observability gap?

That means the repository favors minimal abstractions, inspectable artifacts,
reproducible inputs, and honest documentation of limitations.

## Safety

Some labs intentionally include privileged containers, host mounts, exposed
services, permissive networking, or other unsafe configurations. These are part
of the experiment, not recommended defaults.

- Do not run these examples in production.
- Use an isolated test account, project, or cluster.
- Review manifests and scripts before running them.
- Never commit credentials, kubeconfigs, generated certificates, or Terraform
  state.
- Read the related walkthrough's cleanup section before creating resources so
  you do not leave access, cluster-wide controls, or cloud charges behind.

## Container Images

The [`basic-flask-app`](./basic-flask-app/) publishes a multi-architecture image
for `linux/amd64` and `linux/arm64` at:

```text
ghcr.io/sf-matt/basic-flask-app
```

The admission webhook publishes the same architectures at:

```text
ghcr.io/sf-matt/raw-k8s-admission-webhook
```

Prefer immutable SHA tags or image digests in repeatable labs. Treat `latest`
as a convenience for short-lived experiments only.

## Blog Relationship

These projects support writing at [CloudSecBurrito](https://cloudsecburrito.com/).
The blog owns setup instructions, command sequences, expected output, and the
educational narrative. This repository documents what each artifact is, why it
exists, and the risks or limitations that remain.

Lab results should only be described as verified when the corresponding commands
were run and their observed behavior was recorded. Project READMEs link to the
related article when one is available.

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
