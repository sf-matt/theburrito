# 🌯 CloudSecBurrito 

This repo contains hands-on security scenarios, infrastructure, and experiments built to support blog posts on the [cloud sec burrito](https://cloudsecburrito.com/).

The goal is simple:

> Do fun stuff.

---

## What This Repo Is

A collection of **interesting security scenarios** across domains such as:

* Kubernetes runtime security
* Admission control & prevention
* Container isolation (Kata, gVisor, etc.)
* Detection engineering (Falco, KubeArmor)
* Cloud + AI workload security 

---

## Example Focus: Kata Containers

The Kata examples explore:

* VM-based container isolation
* Differences vs standard containers
* What “container escape” looks like (or doesn’t)
* Observability gaps and tradeoffs

---

## Philosophy

This is not a “best practices” repo. It’s a **“what actually happens when you try this?”** repo.

That means:

* Minimal abstractions
* Real commands
* Verifiable outcomes
* Lots of mistakes

---

## 🧵 Blog + Content Tie-In

Most scenarios map directly to posts from: *CloudSecBurrito*

---

## Disclaimer

This repo intentionally includes:

* Vulnerable configurations
* Exploit scenarios
* Unsafe defaults

Do **not** run this in production environments.

---

## 🍻 Closing Thought

If it only works in a slide deck, it doesn’t count.

If it works in a cluster and breaks in an interesting way — now we’re talking.
