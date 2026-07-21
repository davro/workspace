# TESTING.md — Infrastructure Plugin manual test checklist

Status: **all five parts below have passed at least once**, on a real
machine, against real infrastructure (not just "the code runs"). Keep
this as a regression checklist going forward — after touching anything
in `InfrastructureWidget.py`, `KubernetesManager.py`, `TerraformManager.py`,
or `ProjectDetector.py`, re-run whichever part is relevant before calling
the change done. See `HANDOVER.md` for the full narrative of what each
part actually confirmed and any gotchas hit along the way.

Nothing in this project is meant to be kept for its own sake. Delete the
whole `test-infra-project/` folder if you want, or keep it around as a
permanent smoke-test fixture — recommended, since it's what all the
"confirmed working" claims in `HANDOVER.md` were tested against.

---

## Setup

1. Open `test-infra-project/` as a project/folder in Workspace IDE.
2. Open the Infrastructure panel (`Ctrl+Shift+I`).
3. Overview tab → confirm:
   - "This Project's Infra Directories" shows both `terraform/` and
     `k8s/` detected (✅ with paths).
   - "Installed CLI Tools" shows k3d/kubectl/terraform/docker all ✅,
     and the daemon status line shows "docker daemon is running".
   - If anything here isn't ✅, stop and fix that first — the rest of
     this checklist assumes a clean baseline.

## Part 1 — Kubernetes: Deploy Manifests — ✅ PASSED

If you still have the `workspace-testing` cluster running from before,
you can reuse it — otherwise:

1. Kubernetes tab → cluster name should auto-fill (`workspace-testing`,
   per `workspace.yml` above, or `workspace-test-infra-project` if
   detection falls back to the folder name — either is fine).
2. Click **Create Cluster** (skip if reusing an existing one).
   - Expect: full k3d creation log ending `[exit code 0]`, console note
     "kubectl context switched to k3d-<name> automatically."
3. Click **Deploy k8s/ Manifests**.
   - Expect: console shows
     `kubectl apply -f <path>/k8s/nginx-test.yaml`, then
     `deployment.apps/infra-plugin-test created` and
     `service/infra-plugin-test created`, `[exit code 0]`.
   - Note: if the target `k8s/` directory has no manifest files in it
     yet (e.g. you just created the folder), this will error instead
     ("no objects passed to apply" or similar) — not a bug, just means
     there was nothing to deploy. Put a manifest in first.
4. Click **Refresh Pods**.
   - Expect: an `infra-plugin-test-...` pod appears alongside the usual
     k3d system pods, status `Running` once it's pulled `nginx:alpine`
     (may show `ContainerCreating` briefly first — refresh again after
     a few seconds if so).
5. Select that pod → **View Logs**.
   - Expect: nginx's own startup log lines (worker process startup
     messages), not an error.
6. **Gold-standard verification, don't skip this**: in a terminal, run
   `kubectl port-forward svc/infra-plugin-test 8080:80` (leave it
   running), then either `curl http://localhost:8080` or open
   `http://localhost:8080` in a real browser. You should see nginx's
   actual "Welcome to nginx!" page. This is the real proof — logs and
   `Running` status can look fine even if something's subtly wrong with
   the service's routing; a browser actually rendering the page can't be
   faked by a partially-broken setup. Ctrl+C the port-forward when done.

**Confirmed working** — deployment, logs, and live HTTP traffic all
verified, including a real browser screenshot of the nginx welcome page.

## Part 2 — Kubernetes: Delete Cluster — ✅ PASSED

1. Kubernetes tab → **Delete Cluster** → confirm the dialog.
   - Expect: console shows `k3d cluster delete <name>`, ending with a
     success line and `[exit code 0]`.
2. Click **Refresh Pods** again.
   - Expect: pod list shows "No cluster reachable - create one first"
     (not an error/crash) — confirming the plugin handles a
     just-deleted cluster gracefully.
3. Optional: verify at the shell —
   ```bash
   docker ps -a | grep <cluster-name>   # should show nothing
   docker network ls | grep <cluster-name>   # should show nothing
   docker volume ls | grep <cluster-name>   # should show nothing
   ```
   This confirms the cleanup described in the earlier "where does k8s
   store the cluster" conversation actually happened.

**Confirmed working.**

## Part 3 — Terraform tab — ✅ PASSED

Working directory: `test-infra-project/terraform` (should auto-fill from
detection; if not, paste the path into the Terraform directory field).

1. **Init** → expect: downloads the `hashicorp/local` provider, ends
   with `Terraform has been successfully initialized!`, `[exit code 0]`.
2. **Validate** → expect: `Success! The configuration is valid.`
3. **Format** → expect: no output (file's already formatted) or a
   filename if it reformats something, `[exit code 0]` either way.
4. **Plan** → expect: shows one resource to add
   (`local_file.infra_plugin_test`), `Plan: 1 to add, 0 to change,
   0 to destroy.`
5. **Apply** → confirm the dialog → expect: `Apply complete! Resources:
   1 added`, and a real file appears at
   `terraform/infra-plugin-test-output.txt` containing the test string.
   Check it:
   ```bash
   cat test-infra-project/terraform/infra-plugin-test-output.txt
   ```
6. **Destroy** → confirm the dialog → expect: `Destroy complete!
   Resources: 1 destroyed`, and `infra-plugin-test-output.txt` is gone.
   Re-run the `cat` command above — it must now fail with "No such file
   or directory". This is the step that actually proves destroy did
   something, not just reported success.

**Confirmed working** — full init→destroy cycle verified, including
`cat`-confirming the file both appeared after apply and was truly gone
after destroy.

## Part 4 — Active Project dropdown (multi-project support) — ✅ PASSED

Needs a second project to test isolation properly. If you don't have one
handy, create a throwaway one anywhere under your workspace root with its
own empty `terraform/`, `helm/`, and `k8s/` folders (e.g. an
`infrastructure/` folder next to `test-infra-project/`).

1. In the IDE's Projects panel, check both `test-infra-project` and your
   second project so they're both "active."
2. Open the Infrastructure panel → Overview tab → confirm the "🗂 Active
   Project" dropdown lists both projects.
3. Select the second project.
   - Expect: "Scanning Path" updates to that project's path, "This
     Project's Infra Directories" updates to show ITS `terraform/`/
     `helm/`/`k8s/` folders (not `test-infra-project`'s), and the
     Kubernetes tab's cluster name field re-autofills to match (e.g.
     `workspace-<that-project-name>`).
4. Put a manifest in that project's `k8s/` folder (the same
   `nginx-test.yaml` content from this project works fine) — an empty
   directory won't deploy anything, see the note in Part 1.
5. Create Cluster → Deploy k8s/ Manifests → Refresh Pods, same as Part 1.
6. **Confirm real isolation**, not just that it didn't crash: port-forward
   and curl/browser-check this second project's nginx (same as Part 1
   step 6), and confirm `docker ps` shows separate containers for each
   project's cluster if you still have both running
   (`k3d-test-infra-project-...` vs `k3d-<second-project>-...`).
7. Switch the dropdown back to `test-infra-project` and confirm its
   detection/fields revert correctly (this is what proves the override
   actually re-scans on selection, not just on first load).

**Confirmed working** — tested against `test-infra-project` and a second
project with its own `terraform/`/`helm`/`k8s/` folders; deployment,
cluster, and HTTP traffic all confirmed isolated per-project, including
a real browser screenshot of the second project's nginx page.

## Part 5 — Cluster-list dropdown + context-scoping fix — ✅ PASSED

This part exists specifically because Part 4 above initially *looked*
like it worked but actually had a real bug hiding underneath: Kubernetes
actions were not scoped to whichever project was selected, they just hit
kubectl's ambient current-context. See `HANDOVER.md` gotcha #12 for the
full story. This checklist section is the regression test for that fix
— if it ever fails again, that bug is back.

Needs two projects again, one with a running cluster + deployed workload
(e.g. `test-infra-project` from Parts 1-3), one WITHOUT a cluster created
yet (create a fresh throwaway project, or delete a previous test
project's cluster first).

1. Select the project WITH a running cluster in the Active Project
   dropdown. Go to the Kubernetes tab.
   - Expect: the cluster name combo box shows that project's cluster
     name, either pre-selected or available in the dropdown list.
2. Click the small 🔄 refresh button next to the cluster name combo.
   - Expect: the dropdown lists every k3d cluster currently on the
     machine (this is deliberately global, not project-filtered — see
     `HANDOVER.md` rough edges).
3. Click Refresh Pods.
   - Expect: pods for THIS project's cluster (e.g. the nginx deployment
     from Part 1), matching what you'd see running
     `kubectl --context k3d-<name> get pods` directly.
4. Switch the Active Project dropdown to the project WITHOUT a cluster.
   - Expect: cluster name combo re-autofills to that project's expected
     name.
5. Click Refresh Pods again (or just wait for the auto-refresh from
   switching cluster name).
   - **This is the actual regression check.** Expect: "No cluster named
     'k3d-<name>' reachable - create one first" — NOT the previous
     project's pods still showing. If you see the previous project's
     pods here, the context-scoping fix has regressed.
6. Manually type a cluster name into the combo box that doesn't exist
   yet, then press Enter (or click away to trigger editingFinished).
   - Expect: Refresh Pods fires automatically (no manual click needed),
     and shows the same "No cluster named ... reachable" message for
     that typed name.
7. Switch the Active Project dropdown back to the project WITH the
   running cluster.
   - Expect: cluster name combo reverts, and either an automatic refresh
     or a manual Refresh Pods click correctly shows that project's real
     pods again — confirming the fix works in both directions, not just
     "empty cluster shows empty."

**Confirmed working** — tested with `workspace-infrastructure` (running,
nginx deployed) and `workspace-infrastructure-complex` (no cluster yet):
switching to the empty project's cluster name correctly showed the "no
cluster reachable" message instead of the other project's stale pod
list; switching back correctly showed the real pods again.

## Part 6 — Pre-flight validation for empty k8s/terraform dirs — ✅ PASSED

This part exists because "Deploy k8s/ Manifests" against an empty `k8s/`
directory used to let kubectl's own cryptic error surface as-is (see
gotcha in `HANDOVER.md`'s rough edges). `ProjectDetector.has_k8s_manifests()`
and `has_terraform_files()` are the fix — non-recursive checks matching
exactly what `kubectl apply -f <dir>` / `terraform` would actually pick
up, not just "some file exists somewhere under here."

1. Create an empty `k8s/` folder in a throwaway project (no `.yaml`/
   `.yml` files in it at all).
2. Select that project in the Active Project dropdown → Kubernetes tab →
   click **Deploy k8s/ Manifests**.
   - Expect: console shows `[!] <path> has no .yaml/.yml files in it -
     nothing to deploy. Add a manifest there first, then try again.` —
     **and no `kubectl apply` command is dispatched at all** (nothing
     starts spinning, no `$ kubectl apply ...` line in the console).
3. Copy `nginx-test.yaml` into that `k8s/` folder → click **Deploy k8s/
   Manifests** again.
   - Expect: this time it proceeds normally, same as Part 1.
4. Point the Terraform directory field at an empty folder (no `.tf`
   files).
5. Click **Init** (or Plan).
   - Expect: console shows a `[!] <path> has no .tf files in it - this
     will run against an empty configuration (e.g. 'Plan: 0 to add'),
     not an error.` line, **followed by the actual terraform command
     still running** (this is a warning, not a block — Terraform itself
     completes fine against zero resources, so don't expect it to stop).
6. Point it back at `test-infra-project/terraform` (has `main.tf`) and
   re-run Init/Plan.
   - Expect: no warning line, normal output as in Part 3.

**Confirmed working** — empty `k8s/` correctly blocked deploy with a
clear message and no kubectl invocation; empty `terraform/` correctly
warned without blocking; both reverted to normal behavior once real
files were present.

## Part 7 — Overview tab: "+ Create" scaffold buttons — ✅ PASSED

Needs a project with none of `terraform/`, `helm/`, `k8s/` present yet -
a fresh throwaway folder works (e.g. an empty `workspace-scaffold-test/`
next to `test-infra-project/`).

1. Select that empty project in the Active Project dropdown → Overview
   tab.
   - Expect: all three lines under "This Project's Infra Directories"
     show "— not present in this project", and all four buttons below
     (`+ terraform/`, `+ helm/`, `+ k8s/`, `➕ Create All Missing`) are
     enabled.
2. Click **+ k8s/**.
   - Expect: console shows `[+] Created <path>/k8s`, the overview
     re-scans automatically, the `k8s/` line flips to ✅ with the path,
     and the `+ k8s/` button is now disabled (re-clicking would be a
     no-op anyway, but it shouldn't even look clickable).
   - Verify at the shell: `cat <path>/k8s/nginx-example.yaml` shows a
     Deployment + Service manifest (`infra-plugin-example`), not an
     empty file.
3. Kubernetes tab → **Deploy k8s/ Manifests** (create a cluster first if
   you don't have one) → **Refresh Pods**.
   - Expect: this works exactly like Part 1, no "empty directory"
     message from the Part 6 pre-flight check - the scaffolded manifest
     is real, deployable content, not a placeholder.
4. Click **+ terraform/**.
   - Expect: same pattern - `[+] Created <path>/terraform`, ✅ shown,
     button disables. `cat <path>/terraform/main.tf` shows the
     `local_file.example` resource.
5. Terraform tab → **Init** → **Plan** → **Apply**.
   - Expect: same as Part 3 - `Plan: 1 to add`, `Apply complete!
     Resources: 1 added`, and `example-output.txt` actually appears
     under `terraform/`. Not the Part 6 "empty configuration" warning.
6. Click **+ helm/**.
   - Expect: `[+] Created <path>/helm`, ✅ shown, button disables. The
     directory is empty (`ls <path>/helm` shows nothing) - this is
     expected, there's no Helm tab yet to scaffold a chart into it.
7. With all three now present, confirm **➕ Create All Missing** is
   disabled (nothing left to create).
8. On a *different*, still-empty project, click **➕ Create All Missing**
   directly (skip the individual buttons).
   - Expect: all three directories + their starter files appear in one
     shot, console shows three `[+] Created ...` lines, and all four
     buttons disable together.
9. Re-click any already-enabled-then-disabled button once more just to
   be sure.
   - Expect: since it's already disabled you can't actually click it,
     confirming step 2/4/6's disabling is real and not just visual.

**Confirmed working** — each button creates exactly its own directory
(never touching the other two), terraform/k8s starters are real
deployable/applyable content (not empty placeholders), helm/ is
correctly left empty, buttons correctly disable per-directory as each
is created, and "Create All Missing" correctly creates only what's
still missing.

---

## After testing

All five parts above have passed. If you add a new action (Helm tab,
etc.), add a new "Part N" section here following the same pattern:
concrete expected output at each step, and at least one "assert the
real-world side effect" check (a `cat`, a `curl`, a `docker ps`) rather
than trusting console text alone. If the new action touches kubectl at
all, make sure it's scoped with `--context` the same way Part 5 checks
for — that bug class is exactly the kind that's easy to reintroduce by
adding a new action that forgets to thread the context through. Then
update `HANDOVER.md`'s "Verified working" section to match.