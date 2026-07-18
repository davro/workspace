# HANDOVER — Infrastructure Plugin (Workspace IDE)

Status as of this baseline: **working, manually verified end-to-end on a real
machine** (not just "compiles"). Read this before touching the code — it
covers *why* things are shaped this way, not just what they do.

---

## What this is

A Workspace IDE plugin for local, disposable infrastructure workflows:
k3d (Kubernetes-in-Docker) clusters + Terraform, driven from a panel in
the right sidebar. Originated from a much broader brainstorm doc
(multi-runtime Kubernetes, Helm, Ansible, local registry, a Tilt/Skaffold-
style "Develop" loop) that was deliberately scoped WAY down for a laptop /
small dev server. See "Deliberately cut from scope" below before adding
any of that back — it was cut for reasons, not by accident.

## File layout

```
ide/plugins/InfrastructurePlugin.py           # plugin entry point, metadata, hooks
ide/plugins/InfrastructurePlugin/
├── __init__.py
├── install.sh                                # system dependency installer (see below)
├── ProcessRunner.py                           # QThread command runner + run_quick() sync helper
├── ProjectDetector.py                         # terraform/helm/k8s detection, tool + daemon checks
├── KubernetesManager.py                       # k3d + kubectl command builders (argv lists only)
├── TerraformManager.py                        # terraform command builders (argv lists only)
├── InfrastructureWidget.py                    # the UI — tabs + shared console
└── HANDOVER.md                                # this file
README.md (repo root, from the same delivery) # user-facing install/usage doc
```

`KubernetesManager` and `TerraformManager` never call `subprocess` directly
— they only build argv lists. Every actual execution goes through
`ProcessRunner` (async, streams to console) or `run_quick()` (sync, for
fast checks like `docker info` or `kubectl get pods`, <10s timeout). Keep
this separation if you extend it — it's what keeps the UI thread from
locking up on a slow `terraform apply`.

## Verified working (manually, by the user, on their own machine)

- `./ide.sh install` / `install.sh` standalone — installs k3d, kubectl,
  terraform, docker.io via apt, enables the docker service, adds user to
  docker group.
- Create Cluster (k3d) — confirmed full successful cluster creation log,
  kubectl context auto-switches to `k3d-<name>`.
- Refresh Pods — confirmed real pod list rendered (coredns, traefik,
  metrics-server, local-path-provisioner, etc. — the standard k3d system
  pods).
- View Logs — confirmed real log output streamed for a selected pod.
- Delete Cluster — not yet exercised by the user as of this baseline
  (they said "didn't tear it down yet"). Should still work — same
  argv-builder pattern as create — but hasn't been visually confirmed.
- Deploy k8s/ Manifests — NOT yet exercised (no project with a `k8s/`
  folder tested against yet).
- Terraform tab (init/plan/apply/destroy/validate/fmt) — NOT yet
  exercised against a real Terraform config. Command-building logic is
  straightforward and mirrors the Kubernetes side, but treat as
  lower-confidence than the Kubernetes tab until someone runs it.

## Real gotchas hit during setup (don't re-litigate these — just know them)

1. **`pip install` vs system binaries.** k3d/kubectl/terraform/docker are
   NOT pip packages. They don't belong in `ide.sh`'s `REQUIREMENTS` array.
   This is why `install.sh` exists as a separate, non-Python installer.

2. **Plugin install.sh discovery convention.** `ide.sh` now has an
   `install_plugin_dependencies()` function that scans
   `ide/plugins/*/install.sh` and runs any it finds, called on first-run
   auto-install, `./ide.sh install`, and `./ide.sh update`. If you add a
   new plugin with system dependencies, follow this pattern — don't
   invent a new mechanism.

3. **`QLabel` + `"&nbsp;"` bug.** `QLabel.setText()` only parses HTML
   entities once Qt's rich-text heuristic detects an actual tag (e.g.
   `<br>`) in the string. A plain string with only `&nbsp;` in it renders
   literally. Fix used: real Unicode NBSP characters (`\u00A0`) instead
   of the HTML entity, so it renders correctly regardless of whether Qt
   treats the label as rich text.

4. **Docker group membership needs a NEW SESSION, not just a new
   command.** `usermod -aG docker $USER` doesn't affect the shell/process
   that's already running — including the IDE process itself if it was
   already open when the install ran. This tripped the user up multiple
   times: they kept retrying inside the *same running IDE instance*,
   which still had the old group membership baked into its process
   environment. **The fix is always: fully quit the IDE, confirm `docker
   info` works cleanly in the terminal you're about to launch from, THEN
   relaunch.** `newgrp docker` works too but only for that one terminal
   and whatever's launched from it afterward — it does NOT retroactively
   fix an already-running process. A full logout/login or reboot is the
   reliable fix if the IDE is normally launched from a desktop icon
   rather than a terminal.

5. **Don't `sudo bash install.sh` directly.** Running the whole script as
   root adds `root` to the docker group, not your actual user. Always run
   it as your normal user — sudo is invoked internally only for the
   specific commands (`apt`, `usermod`, etc.) that need it.

6. **Two distinct daemon failure modes**, and the plugin now tells them
   apart (`ProjectDetector.container_runtime_status()` /
   `daemon_start_hint()`):
   - `daemon_running: False` + no permission string → daemon genuinely
     not started → "start docker" hint.
   - `permission_denied: True` (detected via `"permission denied"` in the
     `docker info` output) → group membership not active in this
     session yet → "log out and back in / newgrp" hint.
   Don't collapse these back into one generic "docker isn't working"
   message — the fix is different for each and users will spin in
   circles otherwise (see gotcha #4).

7. **Overview tab has two visually similar boxes that check DIFFERENT
   things** — "This Project's Infra Directories" (does the open project
   have a `terraform/`/`helm/`/`k8s/` folder — pure filesystem check) vs
   "Installed CLI Tools" (is k3d/kubectl/terraform/docker on PATH, plus
   daemon reachability). These were originally worded ambiguously
   ("Terraform: not found" in both a project-content sense and looking
   like a tool-missing message) and confused the user. Current wording
   was deliberately changed to disambiguate — don't revert the wording
   without preserving that distinction some other way.

## Deliberately cut from scope (don't add back without a real reason)

From the original brainstorm, NOT implemented, on purpose:

- **kind / minikube / microk8s** — k3d is the only runtime wired up.
  It's the lightest Kubernetes-in-Docker option; kind has heavier
  per-node memory, minikube needs a full VM/driver stack. Both are
  overkill for "disposable local cluster on a laptop." If a real need
  comes up, `KubernetesManager` would need a `runtime` parameter threaded
  through its command builders, plus a runtime selector in the widget —
  not a huge lift, just not done yet.
- **Helm** — no Helm tab. `kubectl apply -f k8s/` covers the deploy loop
  without another CLI dependency. Would need a `HelmManager` following
  the same argv-builder pattern.
- **Ansible** — not touched at all.
- **Local image registry** — implies a permanently-running registry
  container. Explicitly avoided to keep this "on-demand action" rather
  than "background daemon you didn't ask for."
- **Tilt/Skaffold-style "Develop" loop** (build → push → helm upgrade →
  tail logs on file change) — implies a file watcher running
  continuously. Same reasoning as the registry.
- **AI integration** (explain Terraform modules, diagnose failing pods,
  generate manifests) — mentioned in the original brainstorm, not
  started.

## Known rough edges / likely next issues

- `terraform apply`/`destroy` in `TerraformManager` always pass
  `-auto-approve` (the widget's confirm dialog is the only gate). If this
  plugin is ever pointed at anything beyond local/disposable dev infra,
  reconsider whether auto-approve is still appropriate, or add a plan-
  preview step before the confirm dialog.
- `refresh_pods()` and the pod list don't auto-refresh — it's a manual
  button. Fine for now; would need a QTimer or a k3d/kubectl watch if
  live updates are ever wanted.
- No handling yet for multiple clusters existing simultaneously beyond
  what's in the single `cluster_name_edit` field — `k3d cluster list` is
  wired in `KubernetesManager.list_clusters_command()` but nothing in the
  widget surfaces it yet (e.g. a dropdown of existing clusters).
- Terraform directory field auto-fills from detection but there's no
  validation beyond "is it a directory" — no check that it actually
  contains `.tf` files.

## Suggested next steps (not started)

1. Exercise Delete Cluster and the full Terraform tab against a real
   project, since those are still lower-confidence than what's been
   manually verified.
2. Consider a cluster-list dropdown instead of a free-text name field,
   using the already-built `list_clusters_command()` /
   `parse_cluster_list()`.
3. If Helm support becomes a real need: add `HelmManager.py` following
   the exact pattern of `TerraformManager.py`, plus a Helm tab in the
   widget — don't restructure anything else.
