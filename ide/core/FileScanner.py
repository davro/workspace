import os
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal


class FileScannerThread(QThread):
    """Background thread to scan workspace files"""
    files_found = pyqtSignal(list)
    progress = pyqtSignal(str)

    def __init__(self, project_paths, max_files=20000):
        super().__init__()
        self.project_paths = project_paths
        self.max_files = max_files

    def run(self):
        """Scan files in background"""
        files = []

        ignore_dirs = {'.git', '__pycache__', 'node_modules', '.venv', 'venv',
                      'workspace-env', '.idea', '.vscode', 'dist', 'build',
                      '.pytest_cache', '.mypy_cache', 'eggs', '.eggs', 'env',
                      'site-packages', '.tox'}

        ignore_exts = {'.pyc', '.pyo', '.so', '.dylib', '.dll', '.exe', '.o', '.a',
                      '.class', '.jar', '.war', '.log', '.tmp', '.cache'}

        for project_path in self.project_paths:
            project_path = Path(project_path)
            if not project_path.exists():
                continue

            self.progress.emit(f"Scanning {project_path.name}...")

            for root, dirs, filenames in os.walk(project_path):
                if len(files) >= self.max_files:
                    self.progress.emit(f"Reached limit of {self.max_files} files")
                    files.sort()
                    self.files_found.emit(files)
                    return

                dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith('.')]

                for file in filenames:
                    if file.startswith('.') or any(file.endswith(ext) for ext in ignore_exts):
                        continue

                    full_path = Path(root) / file
                    try:
                        if full_path.stat().st_size > 10_000_000:
                            continue

                        rel_path = full_path.relative_to(project_path.parent)
                        files.append((str(rel_path), str(full_path)))
                    except (ValueError, OSError):
                        continue

        files.sort()
        self.files_found.emit(files)
