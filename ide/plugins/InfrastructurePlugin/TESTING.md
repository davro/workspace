# TESTING.md — Infrastructure Plugin manual test checklist

Status: **all four parts below have passed at least once**, on a real
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

---

## After testing

All four parts above have passed. If you add a new action (Helm tab,
cluster-list dropdown, etc.), add a new "Part N" section here following
the same pattern: concrete expected output at each step, and at least
one "assert the real-world side effect" check (a `cat`, a `curl`, a
`docker ps`) rather than trusting console text alone. Then update
`HANDOVER.md`'s "Verified working" section to match.
