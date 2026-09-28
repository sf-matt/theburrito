# Repository Instructions

## Purpose and Scope

- This repository contains educational CloudSecBurrito labs, experiments, and
  small reusable utilities. It is not production-ready software.
- Preserve intentionally vulnerable behavior when it is part of a lab, but make
  the risk and expected outcome explicit in the nearest README.
- Keep projects self-contained in their own directories. Avoid shared machinery
  unless at least two projects genuinely need it.

## Safety and Claims

- Never add credentials, tokens, private keys, generated certificates,
  kubeconfigs, Terraform state, or captured sensitive data.
- Treat manifests, scripts, container images, and external input as untrusted.
- Do not describe a lab as tested or verified unless its commands were run in
  the relevant environment during the current work.
- Do not imply that namespace, pod, process, image, or timestamp overlap proves
  causality without deterministic evidence.
- Keep warnings beside intentionally unsafe resources such as privileged
  containers, host mounts, public firewall rules, or unauthenticated services.

## Documentation

- Keep repository documentation separate from the educational walkthroughs.
  Project READMEs should describe purpose, checked-in artifacts, dependencies,
  design boundaries, limitations, risks, and cleanup implications.
- Do not duplicate a blog article's setup sequence, executable commands,
  terminal transcript, expected output, or step-by-step validation in a project
  README. Put that material in the related CloudSecBurrito article.
- Link a project to every CloudSecBurrito article that directly uses it when the
  article exists. Verify the public URL; do not invent article URLs or lab
  evidence.
- Keep safety-critical warnings close to the affected artifact even when the
  detailed cleanup procedure lives in the article.
- Keep the root README's project inventory and maturity descriptions current.
- Preserve the author's conversational voice. Prefer factual, scoped edits over
  style-only rewrites.

## AI Attribution

- Keep the root README's OpenAI Codex acknowledgment intact.
- When Codex materially contributes to a change, disclose that assistance in
  the pull request summary and describe the work it helped perform.
- Keep authorship and responsibility accurate: the maintainer owns architecture,
  review, validation, publication, and release decisions.

## Dependencies and Reproducibility

- Pin dependencies, container images, downloaded manifests, and tools when
  reproducibility or security depends on the exact version.
- Prefer immutable container tags or digests in Kubernetes manifests. Use
  `latest` only when a lab explicitly demonstrates moving behavior.
- Do not pipe remote scripts into a shell without documenting and pinning the
  source and integrity expectations.

## Validation

- Run the narrowest relevant checks before presenting a change.
- Python: run the project's unit tests and build its container when applicable.
- Terraform: run `terraform fmt -check` and `terraform validate` when the
  required providers are available.
- Kubernetes: validate YAML structure and, when authorized infrastructure is
  available, confirm the behavior in an isolated cluster.
- Always run `git diff --check` and report environment limitations separately
  from code or content failures.

## Version Control and Publication

- Work on a feature branch and preserve unrelated user changes.
- Show a reviewable diff before committing.
- Do not commit, push, merge, publish a container, or change public content
  without explicit approval.
- Before an approved commit or push, verify the exact changed files and rerun
  the relevant checks.

## Code Review Rules

- Flag undocumented dangerous defaults, secret material, unpinned remote
  execution, missing cleanup steps, and claims that exceed demonstrated lab
  evidence.
- Distinguish an intentional lab vulnerability from an accidental exposure.
- Prefer a safe path or specific remediation with each security finding.
