# InfrastructurePlugin/ProcessRunner.py

"""
ProcessRunner - runs shell commands off the Qt main thread.

Every infra command (k3d, kubectl, terraform, docker) can take anywhere
from a fraction of a second to several minutes. Running any of that on
the GUI thread would freeze the whole IDE, so everything goes through
this QThread wrapper. Output streams back line-by-line via a signal so
the widget can show live progress instead of a spinner.
"""

import subprocess
from PyQt6.QtCore import QThread, pyqtSignal


class ProcessRunner(QThread):
    """
    Runs a single command in a background thread and streams its output.

    Signals:
        line_ready(str):   emitted for every line of combined stdout/stderr
        finished_ok(int):  emitted once, with the process return code
    """

    line_ready = pyqtSignal(str)
    finished_ok = pyqtSignal(int)

    def __init__(self, command, cwd=None, env=None, label=None, parent=None):
        """
        Args:
            command: list[str] - argv, e.g. ["k3d", "cluster", "create", "dev"]
            cwd: working directory for the command
            env: optional dict to override/extend the process environment
            label: optional human-readable label, useful for logging
            parent: Qt parent (typically the widget dispatching the
                command). Passing this matters: without a Qt parent, this
                QThread's C++ lifetime is tied only to Python's reference
                count on it. If the owning widget is garbage-collected
                while the thread is still running (e.g. the panel closes
                mid-command), Qt destroys the thread object out from under
                the still-running OS thread and hard-aborts the whole
                process ("QThread: Destroyed while thread is still
                running") - not a catchable Python exception. With a
                parent set, Qt's ownership tree keeps it alive until it's
                explicitly cleaned up (see cancel()/wait() in the widget).
        """
        super().__init__(parent)
        self.command = command
        self.cwd = str(cwd) if cwd else None
        self.env = env
        self.label = label or " ".join(command)
        self._process = None
        self._killed = False

    def run(self):
        import os

        full_env = os.environ.copy()
        if self.env:
            full_env.update(self.env)

        try:
            self._process = subprocess.Popen(
                self.command,
                cwd=self.cwd,
                env=full_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except FileNotFoundError:
            self.line_ready.emit(
                f"[error] command not found: {self.command[0]} "
                f"(is it installed and on PATH?)"
            )
            self.finished_ok.emit(127)
            return
        except Exception as e:
            self.line_ready.emit(f"[error] failed to start: {e}")
            self.finished_ok.emit(1)
            return

        try:
            for line in self._process.stdout:
                self.line_ready.emit(line.rstrip("\n"))
        except Exception as e:
            self.line_ready.emit(f"[error] reading output: {e}")

        return_code = self._process.wait()
        if self._killed:
            self.line_ready.emit(f"[{self.label}] cancelled")
        self.finished_ok.emit(return_code)

    def cancel(self):
        """
        Ask the running process to stop. Tries a graceful terminate()
        first; if the process is still alive shortly after, escalates to
        kill(). Either way, this only *requests* a stop - it does NOT
        wait for run() to actually finish. Callers that need the thread
        fully stopped before proceeding (e.g. before the widget holding
        it is destroyed) must still call `.wait()` afterward - see
        InfrastructureWidget.shutdown().
        """
        self._killed = True
        if not self._process or self._process.poll() is not None:
            return
        try:
            self._process.terminate()
            self._process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            try:
                self._process.kill()
            except Exception:
                pass
        except Exception:
            pass


def run_quick(command, cwd=None, timeout=5):
    """
    Synchronous helper for cheap, fast checks (e.g. `which k3d`, `docker info`).
    Only use this for calls expected to return in well under a second -
    anything that provisions or destroys infrastructure must go through
    ProcessRunner instead so it doesn't block the UI.

    Returns (returncode, output) - returncode is -1 if the binary is missing
    or the call times out.
    """
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, (result.stdout + result.stderr).strip()
    except FileNotFoundError:
        return -1, ""
    except subprocess.TimeoutExpired:
        return -1, "timed out"