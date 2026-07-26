# HANDOVER — Infrastructure Plugin (Workspace IDE)

Status as of this update: **fully verified end-to-end on a real machine,
including the whole TESTING.md checklist**, PLUS multi-project support
(Active Project dropdown) and a per-project cluster-list dropdown, both
verified against two real projects. A significant bug was found and
fixed in this session: **Kubernetes actions (Refresh Pods/Deploy/Logs)
were not actually scoped to the selected project's cluster** — see
gotcha #12, read it before touching anything in the Kubernetes tab. A
QThread crash was also found and fixed earlier (gotcha #8) — read that
one before touching `ProcessRunner` or `InfrastructureWidget`'s threading.

---

## What this is

A Workspace IDE plugin for local, disposable infrastructure workflows:
k3d (Kubernetes-in-Docker) clusters + Terraform + Helm, driven from a
panel in the right sidebar. Originated from a much broader brainstorm
doc (multi-runtime Kubernetes, Ansible, local registry, a Tilt/Skaffold-
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
├── ProjectDetector.py                         # terraform/helm/k8s detection, tool + daemon checks, scaffold()
├── KubernetesManager.py                       # k3d + kubectl command builders (argv lists only)
├── TerraformManager.py                        # terraform command builders (argv lists only)
├── HelmManager.py                             # helm command builders (argv lists only) - new, unverified
├── InfrastructureWidget.py                    # the UI — tabs + shared console
└── HANDOVER.md                                # this file
README.md (repo root, from the same delivery) # user-facing install/usage doc
```

`KubernetesManager`, `TerraformManager`, and `HelmManager` never call
`subprocess` directly — they only build argv lists. Every actual
execution goes through `ProcessRunner` (async, streams to console) or
`run_quick()` (sync, for fast checks like `docker info` or `kubectl get
pods`, <10s timeout). Keep this separation if you extend it — it's what
keeps the UI thread from locking up on a slow `terraform apply` (or
`helm install`).

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
- Cluster-list dropdown (cluster name field is now an editable combo,
  see gotcha #12 for the bigger fix that came with it) — **confirmed
  working**: existing clusters (`workspace-infrastructure`) showed up
  correctly in the dropdown, selecting one and hitting Delete Cluster
  round-tripped the selected value into the k3d command correctly.
- Context-scoping fix (gotcha #12) — **confirmed working**: selecting an
  empty/not-yet-created project's cluster name and clicking Refresh Pods
  now correctly shows "No cluster named 'k3d-...' reachable - create one
  first" instead of silently showing a different project's pods.
  Switching back to a project with a real running cluster correctly
  showed its actual pods again.

## Built but only logic-tested so far (not yet confirmed on the real machine)

Being straight about this: everything below was written and exercised
against plain-Python unit-style checks in a sandbox with no PyQt6, no
`terraform`/`helm`/`kubectl` binaries, and no real Workspace IDE - not
the "confirmed working... on a real machine" bar the rest of this doc
holds itself to. Don't copy the wording pattern above onto these until
TESTING.md's Parts 6-8 have actually been run.

- Pre-flight validation for empty k8s/terraform dirs —
  `ProjectDetector.has_k8s_manifests()` / `has_terraform_files()` do a
  non-recursive glob (`*.yaml`/`*.yml`, `*.tf`) matching exactly what
  `kubectl apply -f <dir>` / `terraform` itself would pick up, and were
  confirmed correct against real temp directories in a plain script.
  Deploy k8s/ Manifests should hard-block with a clear console message
  and dispatch no kubectl command at all against an empty `k8s/` dir;
  Terraform's `_tf_dir()` should only warn (not block) on an empty
  `.tf` directory. Neither has actually been clicked through in the
  real IDE yet. See TESTING.md Part 6.
- Overview tab scaffold buttons (`+ terraform/`, `+ helm/`, `+ k8s/`,
  `➕ Create All Missing`) — **partially confirmed**: you've verified for
  real that clicking these creates the actual directory and starter
  file (`terraform/main.tf`, `k8s/nginx-example.yaml`) on disk. Still
  open: actually deploying/applying the scaffolded content through the
  UI, confirming the buttons visually disable once their directory
  exists, and "Create All Missing" on a second project. See TESTING.md
  Part 7.
- **Helm tab (new, entirely unverified)** — `HelmManager.py` (argv
  builders for `helm create/upgrade --install/uninstall/list -o json/
  lint/template`, all `--kube-context`-scoped the same way
  `KubernetesManager` is) plus a full Helm tab in the widget: a chart
  directory field (validated the same hard-block way as k8s - missing
  `Chart.yaml` stops the action with a clear message instead of
  Helm's own error), a "+ helm create" button that runs Helm's actual
  scaffold generator (not a hand-rolled starter, unlike terraform/k8s),
  Install/Upgrade using `upgrade --install` so a second click upgrades
  in place instead of erroring "name already in use", Uninstall (with
  confirm dialog), and a Releases list populated via `helm list -o json`.
  `install.sh` now installs `helm` too. **None of this has been run
  against a real cluster.** See TESTING.md Part 8 for the full
  click-through - do that before treating any of it as working.
- **Port Forward toggle (new, entirely unverified)** — a row on the
  Kubernetes tab: service name + local/remote port fields, auto-filled
  by `KubernetesManager.find_service_in_manifests()` actually parsing
  the deployed k8s/ manifest for a Service resource (not hardcoded to
  "nginx" - it picks up whatever's really there, `infra-plugin-test` or
  `infra-plugin-example` or anything else). Start/Stop toggles a
  `kubectl port-forward` that runs on its **own dedicated ProcessRunner
  slot** (`self._pf_runner`), separate from the shared single-command
  slot (`self._runner`) - this had to be split out because
  port-forward is long-running by design (blocks until killed) instead
  of running-to-completion like every other command in this plugin, so
  it can't share that slot's "only one command at a time" bookkeeping
  without either blocking every other action while forwarding, or vice
  versa. `shutdown()` now stops *both* slots, not just one - an orphaned
  port-forward left running after the widget's torn down would silently
  hold its local port open forever. **None of this has been run against
  a real cluster.** See TESTING.md Part 9.

Every path in the original five-part TESTING.md checklist is verified.
The four items just above are not yet - they're new, and only as good
as their sandbox-level testing until proven otherwise on your machine.
If you add further new actions beyond these, add a corresponding
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

12. **Kubernetes actions were not actually scoped to the selected
    project's cluster - a real, significant bug, not cosmetic.** Hit in
    real use: with two projects (`workspace-infrastructure`, cluster
    running with nginx deployed, and `workspace-infrastructure-complex`,
    no cluster yet), switching the Active Project dropdown to the empty
    one and clicking Refresh Pods still showed the FIRST project's nginx
    pod. Root cause: `refresh_pods()`, `deploy_manifests()`, and
    `view_pod_logs()` all called kubectl with no `--context` flag, so
    they silently used whatever kubectl's ambient `current-context`
    happened to be - which only changes when k3d's own `cluster create`
    switches it, NOT when the Active Project dropdown changes. The
    dropdown was only ever affecting directory detection and field
    defaults, never actually re-targeting which cluster commands hit.
    Fix (now in place, don't undo):
    - Every kubectl command builder in `KubernetesManager`
      (`apply_manifests_command`, `get_pods_command`,
      `get_pod_logs_command`, `describe_pod_command`) now takes an
      optional `context` param and prepends `--context <name>`.
    - New `InfrastructureWidget._current_cluster_context()` derives the
      expected context (`k3d-<name>`) from whatever's currently in the
      cluster name combo box, and `deploy_manifests()`/`refresh_pods()`/
      `view_pod_logs()` all pass it through explicitly now instead of
      relying on the ambient context.
    - If the resulting context doesn't exist yet (cluster not created),
      kubectl fails fast and `refresh_pods()` shows a specific message
      naming the missing context, instead of silently falling back to
      whatever was last active.
    If you add any new kubectl-calling action, thread `context` through
    it the same way - do NOT let a new action skip this and quietly
    reintroduce the "wrong project's data shown" bug.

13. **Cluster name field auto-refresh is wired to `activated` +
    `editingFinished`, deliberately NOT `currentTextChanged`.**
    `currentTextChanged` fires on every keystroke in an editable combo
    box - connecting `refresh_pods()` (a blocking call, up to 8s) to that
    would freeze the UI while typing a new cluster name one character at
    a time. `activated` fires when an existing item is picked from the
    dropdown; `editingFinished` fires when typed text is committed
    (Enter or focus loss). `_on_cluster_name_changed()` also de-dupes
    against `_last_refreshed_cluster_name` since both signals can fire
    without the value actually changing.

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
- **Helm** — ~~no Helm tab~~ **added, see "Helm tab (new, unverified)"
  below** - `HelmManager.py` now exists following the same argv-builder
  pattern as `TerraformManager`.
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
- ~~Terraform directory field auto-fills from detection but there's no
  validation beyond "is it a directory"~~ — **closed**: both directions
  now check actual file contents (`has_terraform_files` / `has_k8s_manifests`
  in `ProjectDetector`), with k8s hard-blocking and terraform only
  warning (see "Pre-flight validation" above for why those differ).
- Opening the panel now does several blocking checks in a row at load
  time (`docker info` for the daemon check, `kubectl get pods` for the
  pod list, `k3d cluster list` for the cluster combo) — all via the
  synchronous `run_quick()`, each with its own short timeout. On a slow
  machine or unreachable daemon this could add a few seconds of pause
  when the panel first opens or a project/tab is switched. Not yet
  reported as an actual problem, but if it ever is, the fix is moving
  these onto a background thread rather than synchronous calls.
- The cluster-list dropdown (see gotcha #12/13) is intentionally a
  GLOBAL list of every k3d cluster on the machine, not filtered by
  project — there's no enforced link between a cluster and the project
  that created it beyond the `workspace-<project>` naming suggestion.
  Nothing stops someone selecting an unrelated cluster while a different
  project is active in the Active Project dropdown. Not a bug exactly -
  more a "the two dropdowns don't talk to each other" gap worth knowing.

## Suggested next steps (not started)

1. ~~If Helm support becomes a real need: add `HelmManager.py`...~~ **Done**
   - see "Helm tab (new, unverified)" below. This is genuinely
   unverified though (no real machine, no PyQt6/helm binary in the
   sandbox it was written in) - run TESTING.md Part 8 before trusting
   it.
2. If load-time responsiveness becomes an actual complaint (see rough
   edge above), move the daemon check, pod refresh, and cluster-list
   fetch off the synchronous path.
3. ~~Consider a clearer pre-flight message for "Deploy k8s/ Manifests"
   when the target directory has no `.yaml`/`.yml` files, rather than
   letting kubectl's own error surface as-is.~~ **Done** — see "Pre-flight
   validation" above and TESTING.md Part 6. Note the intentional
   asymmetry if you extend this further: k8s is a hard block (kubectl
   genuinely errors on an empty dir), terraform is a soft warning only
   (terraform genuinely doesn't error - "0 to add" is a valid, successful
   outcome). Don't make terraform block too; that would change real
   behavior for a case that isn't actually broken.
4. Consider whether the cluster-list dropdown should filter/suggest
   clusters matching the currently selected project's naming convention,
   given the "two dropdowns don't talk to each other" rough edge above -
   weigh this against the deliberate choice to show everything honestly
   rather than hide a cluster behind a naming guess.