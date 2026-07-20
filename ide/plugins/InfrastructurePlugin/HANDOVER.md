# HANDOVER — Infrastructure Plugin (Workspace IDE)

Status as of this update: **fully verified end-to-end on a real machine,
including the whole TESTING.md checklist**, PLUS a new multi-project
feature (Active Project dropdown) verified against two real, separate
projects with isolated clusters — see "Active Project dropdown" below.
A QThread crash was found and fixed along the way (see gotcha #8) — read
that one before touching `ProcessRunner` or `InfrastructureWidget`'s
threading.

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
  kubectl context auto-switches to `k3d-<name>`. Re-confirmed clean
  (no crash) after the QThread parenting fix (gotcha #8).
- Refresh Pods — confirmed real pod list rendered (coredns, traefik,
  metrics-server, local-path-provisioner, etc. — the standard k3d system
  pods), and confirmed for an actual deployed workload (see Deploy k8s/
  Manifests below). Also confirmed auto-populating on panel load and on
  switching to the Kubernetes tab, without needing a manual click first.
- View Logs — confirmed real log output for both a k3d system pod
  (coredns) and a deployed application pod (nginx's own startup output).
- Deploy k8s/ Manifests — **confirmed working end-to-end**, using
  `test-infra-project/k8s/nginx-test.yaml` (see TESTING.md in that
  folder): `kubectl apply` succeeded, the pod appeared via Refresh Pods,
  and its logs rendered correctly via View Logs.
- Delete Cluster — **confirmed working**: clean k3d deletion log ending
  `[exit code 0]`, and Refresh Pods afterward correctly showed "No
  cluster reachable" instead of erroring.
- Terraform tab (init/plan/apply/destroy/validate/fmt) — **confirmed
  working end-to-end**, using `test-infra-project/terraform/main.tf`
  (the `hashicorp/local` provider — no cloud creds/cost). Full sequence
  run and verified: init (provider installed, lock file created) →
  validate (`Success!`) → fmt → plan (`1 to add`) → apply (`1 added`,
  file confirmed on disk via `cat`) → destroy (`1 destroyed`, file
  confirmed GONE via `cat` afterward — not just a "reported success").

Every path in the original TESTING.md checklist is now verified. If you
add new actions (Helm tab, cluster dropdown, etc.), add a corresponding
section to TESTING.md and follow the same "assert the real-world side
effect, not just the console output" pattern used above (e.g. `cat`-ing
the file that was supposedly created/destroyed).

## Active Project dropdown — multi-project support (new)

The Overview tab now has an "🗂 Active Project" dropdown above Scanning
Path, populated from `ide/core/ProjectsPanel.py`'s checked projects
(reached via `self.api.get_main_window().projects_panel` -
`get_active_projects()` / `projects_changed` signal). Picking a project
re-scans THAT project's `terraform/`/`helm`/`k8s/` folders instead of
whatever the IDE considers the single "current" workspace.

**Verified working, real end-to-end test**, not just detection:
- Two separate projects tested side by side: `test-infra-project/` and a
  new `infrastructure/` project (with its own `terraform/`, `helm/`,
  `k8s/` folders created specifically to test this).
- Dropdown correctly listed both from the Projects panel's checkboxes.
- Selecting `infrastructure` correctly re-scanned to show ITS
  directories (not test-infra-project's), and the cluster name field
  re-autofilled to `workspace-infrastructure`.
- Created a separate k3d cluster for it, deployed a manifest into
  `infrastructure/k8s/` (which was initially empty - see note below),
  and **confirmed actual isolation**: `kubectl port-forward` +
  `curl localhost:8080` from a browser rendered nginx's welcome page,
  proving this project's deployment landed in its own cluster
  completely independent of the other project's.
- Confirmed the empty-directory case: deploying against a `k8s/` folder
  with no manifest files in it does nothing useful (`kubectl apply`
  errors with something like "no objects passed to apply") - not a bug,
  just means TESTING.md-style guidance should note "put a manifest in
  there first" for anyone testing against a freshly-created directory.

**Implementation notes for anyone touching this:**
- `InfrastructureWidget._explicit_project_path` is the override. `None`
  means "follow whatever `get_workspace_path()` reports" (old
  single-project behavior); once the user picks a project from the
  dropdown, it's set and wins over `get_workspace_path()` on every
  subsequent `refresh_overview()` call, including tab-switch
  auto-refreshes.
- `InfrastructurePlugin.on_project_opened()` (the IDE's own project-open
  hook) now resets `_explicit_project_path` back to `None` and
  repopulates the dropdown. This matters: without it, opening a
  genuinely different project through the IDE's normal flow would be
  silently ignored while a stale dropdown selection stayed pinned.
- `_get_projects_panel()` reaches into `get_main_window().projects_panel`
  defensively (try/except, falls back to `None`) because this isn't part
  of the plugin API's formal contract, just the current `Workspace`
  class's structure. If `ProjectsPanel` is ever renamed/restructured,
  this degrades gracefully to the old single-project fallback rather
  than crashing - keep that defensive pattern if you touch this again.
- Switching the dropdown selection clears (not just re-autofills) the
  cluster name and Terraform directory fields, so stale values from the
  previously selected project can't linger.

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

8. **QThread destroyed mid-run → hard process abort ("core dumped").**
   Hit in real use: `QThread: Destroyed while thread '' is still
   running` followed by an aborted process. Root cause: `ProcessRunner`
   was constructed with no Qt parent, so its C++ lifetime depended only
   on Python's reference count. If the widget holding it gets torn down
   while a command (e.g. a 30-50s cluster create) is still running, Qt
   destroys the still-running QThread out from under itself — this is a
   hard Qt-level abort, NOT a catchable Python exception. Fix (now in
   place, don't undo):
   - `ProcessRunner.__init__` takes `parent`, and
     `InfrastructureWidget.run_command()` passes `parent=self` — ties
     the thread's C++ lifetime to Qt's ownership tree.
   - `ProcessRunner.cancel()` now escalates: `terminate()` → wait 3s →
     `kill()` if still alive, instead of asking once and giving up.
   - New `InfrastructureWidget.shutdown()` calls `cancel()` then
     *blocks* on `.wait()` before allowing the widget to be destroyed.
     `InfrastructurePlugin.cleanup()` calls this (not a bare
     `_runner.cancel()` anymore), and there's also a `closeEvent`
     override on the widget as a second safety net for teardown paths
     that might skip the plugin's `cleanup()` hook.
   If you ever construct a `ProcessRunner` without going through
   `run_command()`, make sure you still pass a parent and still go
   through a wait-before-destroy path — this bug is easy to
   reintroduce by accident.

9. **`api.get_workspace_path()` can return a path with an un-resolved
   `..` segment.** Seen in practice as
   `/home/davro/workspace/workspace-dev/..`. Harmless for `is_dir()`/
   `exists()` checks (the OS resolves it), but confusing to display
   as-is — this is exactly what happened when a user created a
   `terraform/` folder one level above what they thought was the open
   project, and the plugin's (then nonexistent) debug output couldn't
   tell them why detection "wasn't working." Fix: `_project_path()` now
   calls `.resolve()` before returning, and the Overview tab has a
   dedicated "📍 Scanning Path" box showing the resolved path — keep
   both. If you add other places that display or compare paths from
   `get_workspace_path()`, resolve them too rather than assuming they're
   already clean.

10. **Default cluster name could double up as "workspace-workspace."**
    `ProjectDetector.default_cluster_name()` prepends `workspace-` to the
    project folder's name. If that folder is itself named `workspace`
    (or already starts with it), naively prepending produced
    `workspace-workspace`. Fixed by skipping the prefix when the name
    already starts with `workspace`. Minor, but if you touch this
    function again, keep that guard.

11. **`get_main_window().projects_panel` is not a documented plugin API
    contract - it's just today's `Workspace` class structure.** Used to
    build the Active Project dropdown (see that section above). Works
    today because `Workspace.__init__` sets `self.projects_panel =
    ProjectsPanel(...)`, but nothing guarantees that attribute name or
    the `ProjectsPanel` class stays put. `_get_projects_panel()` wraps
    this in a try/except specifically so a future rename degrades to the
    old single-project fallback instead of crashing the whole panel -
    don't remove that defensiveness to "clean up" the code.

## `test-infra-project/` — keep or discard, your call

A throwaway project (delivered alongside this plugin) with a minimal
`k8s/nginx-test.yaml` and a `terraform/main.tf` using the `hashicorp/local`
provider (no cloud creds/cost) — this is what all the "confirmed working
end-to-end" claims above were actually tested against. It has its own
`TESTING.md` with the exact expected output at each step. Either delete
it now that everything's passed, or keep it around as a permanent
smoke-test fixture for regression-checking future changes — recommended
if you're going to add features like a Helm tab or a cluster-list
dropdown, since it gives you a known-good baseline to re-run.

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
- No handling yet for multiple CLUSTERS existing simultaneously per
  project beyond what's in the single `cluster_name_edit` field — note
  this is distinct from the multi-PROJECT support above (which is done).
  `k3d cluster list` is wired in `KubernetesManager.list_clusters_command()`
  but nothing in the widget surfaces it yet (e.g. a dropdown of existing
  clusters for whichever project is currently selected).
- Terraform directory field auto-fills from detection but there's no
  validation beyond "is it a directory" — no check that it actually
  contains `.tf` files. Same gap on the Kubernetes side: Deploy k8s/
  Manifests against an empty (no `.yaml` files) directory just errors
  from kubectl rather than the plugin catching it with a clearer message
  first (hit in practice - see Active Project dropdown section above).
- Opening the panel now does two blocking checks in a row at load time
  (`docker info` for the daemon check, `kubectl get pods` for the pod
  list) — both via the synchronous `run_quick()`, each with its own
  timeout (5s / 8s). On a slow machine or unreachable daemon this could
  add a few seconds of pause when the panel first opens. Not yet reported
  as an actual problem, but if it ever is, the fix is moving these onto
  a background thread rather than synchronous calls.

## Suggested next steps (not started)

1. Consider a per-project cluster-list dropdown (see rough edge above)
   instead of a free-text name field, using the already-built
   `list_clusters_command()` / `parse_cluster_list()` — natural
   follow-on now that the Active Project dropdown exists.
2. If Helm support becomes a real need: add `HelmManager.py` following
   the exact pattern of `TerraformManager.py`, plus a Helm tab in the
   widget — don't restructure anything else.
3. If load-time responsiveness becomes an actual complaint (see rough
   edge above), move the daemon check and pod refresh off the
   synchronous path.
4. Consider a clearer pre-flight message for "Deploy k8s/ Manifests"
   when the target directory has no `.yaml`/`.yml` files, rather than
   letting kubectl's own error surface as-is.