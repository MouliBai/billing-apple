"""
git_sync.py â€” Push the local SQLite DB to a private GitHub repo
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
Fill in GITHUB_REPO_URL and GITHUB_TOKEN below (auth is hard-coded here
per your setup â€” nothing is read from env vars or prompts).

Behaviour:
  â€¢ Only the .db file is ever added / committed / pushed.
  â€¢ Commit message = current date & time, e.g. "2026-07-01 14:32:07".
  â€¢ Runs on a background QThread so the UI never freezes.
  â€¢ Called automatically right after a brand-new DB is created
    (see MainWindow._after_master in evoaura_app.py).

Requires: the `git` command line tool to be installed and on PATH.
"""

import os
import shutil
import datetime
import subprocess

from PyQt6.QtCore import QThread, pyqtSignal

# â”€â”€ FILL THESE IN â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
GITHUB_REPO_URL = "https://github.com/<your-username>/<your-repo>.git"  # existing PRIVATE repo, HTTPS clone URL
GITHUB_TOKEN    = ""            # personal access token, "repo" scope
GITHUB_BRANCH   = "main"        # branch to push to
GIT_USER_NAME   = "EvoAura Sync"
GIT_USER_EMAIL  = "sync@evoaura.local"
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

# Hidden working folder that acts as the git checkout. Only the DB
# file ever lives here â€” nothing else from the app is copied in.
SYNC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".db_sync")


def _run(args, cwd):
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, **kwargs)


def _authed_remote_url() -> str:
    if GITHUB_TOKEN and GITHUB_REPO_URL.startswith("https://"):
        return GITHUB_REPO_URL.replace("https://", f"https://{GITHUB_TOKEN}@", 1)
    return GITHUB_REPO_URL


def _ensure_repo():
    if not GITHUB_REPO_URL or "<your-" in GITHUB_REPO_URL:
        return False, "GITHUB_REPO_URL is not set in git_sync.py"
    if not GITHUB_TOKEN:
        return False, "GITHUB_TOKEN is not set in git_sync.py"

    os.makedirs(SYNC_DIR, exist_ok=True)

    if not os.path.isdir(os.path.join(SYNC_DIR, ".git")):
        r = _run(["git", "init"], SYNC_DIR)
        if r.returncode != 0:
            return False, f"git init failed: {r.stderr.strip()}"
        _run(["git", "config", "user.name", GIT_USER_NAME], SYNC_DIR)
        _run(["git", "config", "user.email", GIT_USER_EMAIL], SYNC_DIR)
        _run(["git", "remote", "add", "origin", _authed_remote_url()], SYNC_DIR)
    else:
        _run(["git", "remote", "set-url", "origin", _authed_remote_url()], SYNC_DIR)

    # Try to line up with whatever's already on the remote branch first,
    # so we don't clobber history that already exists on GitHub.
    _run(["git", "fetch", "origin", GITHUB_BRANCH], SYNC_DIR)
    r = _run(["git", "checkout", "-B", GITHUB_BRANCH, f"origin/{GITHUB_BRANCH}"], SYNC_DIR)
    if r.returncode != 0:
        _run(["git", "checkout", "-B", GITHUB_BRANCH], SYNC_DIR)

    return True, ""


def push_db_to_github(db_path: str):
    """
    Copy db_path into the sync folder, commit with the current
    date/time as the message, and push to GitHub.
    Returns (success: bool, message: str).
    """
    try:
        ok, err = _ensure_repo()
        if not ok:
            return False, err

        db_name = os.path.basename(db_path)
        dest = os.path.join(SYNC_DIR, db_name)
        shutil.copy2(db_path, dest)

        r = _run(["git", "add", "--", db_name], SYNC_DIR)
        if r.returncode != 0:
            return False, f"git add failed: {r.stderr.strip()}"

        commit_msg = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        r = _run(["git", "commit", "-m", commit_msg], SYNC_DIR)
        if r.returncode != 0:
            combined = (r.stdout + r.stderr).lower()
            if "nothing to commit" in combined:
                return True, "DB already up to date on GitHub â€” nothing to push."
            return False, f"git commit failed: {r.stderr.strip()}"

        r = _run(["git", "push", "-u", "origin", GITHUB_BRANCH], SYNC_DIR)
        if r.returncode != 0:
            return False, f"git push failed: {r.stderr.strip()}"

        return True, f"Synced '{db_name}' to GitHub (commit \"{commit_msg}\")."
    except Exception as ex:
        return False, f"Sync error: {ex}"


class GitSyncWorker(QThread):
    """Runs push_db_to_github() off the UI thread."""
    finished_sync = pyqtSignal(bool, str)

    def __init__(self, db_path: str, parent=None):
        super().__init__(parent)
        self._db_path = db_path

    def run(self):
        ok, msg = push_db_to_github(self._db_path)
        self.finished_sync.emit(ok, msg)


