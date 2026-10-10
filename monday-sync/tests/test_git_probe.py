"""git_probe.sh against temp repos with a bare origin (POSIX sh, read-only)."""
import json
import os
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBE = os.path.join(ROOT, "hooks", "git_probe.sh")
ENV = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
           GIT_COMMITTER_EMAIL="t@t", GIT_CONFIG_NOSYSTEM="1", HOME=os.environ.get("HOME", "/tmp"))
BRANCH = "claude/x"


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True,
                          text=True, env=ENV).stdout.strip()


def probe(repo, branch=BRANCH, pushed_head=None):
    args = ["sh", PROBE, str(repo), branch] + ([pushed_head] if pushed_head else [])
    proc = subprocess.run(args, capture_output=True, text=True, env=ENV, timeout=20)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


@pytest.fixture
def repos(tmp_path):
    origin, work, other = tmp_path / "origin.git", tmp_path / "work", tmp_path / "other"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True, env=ENV)
    subprocess.run(["git", "clone", "-q", str(origin), str(work)], check=True, env=ENV,
                   capture_output=True)
    git(work, "checkout", "-q", "-b", "main")
    git(work, "commit", "-q", "--allow-empty", "-m", "init")
    git(work, "push", "-q", "origin", "main")
    git(work, "remote", "set-url", "origin", "git@github.com:o/r.git")
    git(work, "config", "remote.origin.pushurl", str(origin))
    git(work, "config", "remote.origin.fetchurl", str(origin))
    subprocess.run(["git", "clone", "-q", str(origin), str(other)], check=True, env=ENV, capture_output=True)
    return {"origin": origin, "work": work, "other": other}


def fetch(work, origin):
    git(work, "fetch", "-q", "--prune", str(origin), "+refs/heads/*:refs/remotes/origin/*")


def branch_with_commit(work, origin, push=True):
    git(work, "checkout", "-q", "-b", BRANCH)
    git(work, "commit", "-q", "--allow-empty", "-m", "feature work")
    if push:
        git(work, "push", "-q", str(origin), BRANCH)
        fetch(work, origin)
    git(work, "checkout", "-q", "main")
    return git(work, "rev-parse", BRANCH)


def merge_in_other(other, subject):
    git(other, "fetch", "-q", "origin")
    git(other, "merge", "-q", "--no-ff", "-m", subject, f"origin/{BRANCH}")
    git(other, "push", "-q", "origin", "HEAD:main")


def test_unpushed_branch(repos):
    head = branch_with_commit(repos["work"], repos["origin"], push=False)
    out = probe(repos["work"])
    assert (out["on_origin"], out["ahead"], out["merged"], out["head"]) == (False, 1, False, head)
    assert out["origin_url"] == "git@github.com:o/r.git" and out["branch"] == BRANCH


def test_pushed_unmerged_branch(repos):
    head = branch_with_commit(repos["work"], repos["origin"])
    out = probe(repos["work"])
    assert (out["on_origin"], out["ahead"], out["merged"], out["head"]) == (True, 1, False, head)


def test_zero_commits_ahead_is_not_merged(repos):
    w = repos["work"]
    git(w, "branch", BRANCH)
    git(w, "push", "-q", str(repos["origin"]), BRANCH)
    fetch(w, repos["origin"])
    out = probe(w, pushed_head=git(w, "rev-parse", "main"))
    assert (out["on_origin"], out["ahead"], out["merged"]) == (True, 0, False)


def test_merged_via_merge_commit_subject(repos):
    branch_with_commit(repos["work"], repos["origin"])
    merge_in_other(repos["other"], f"Merge pull request #7 from o/{BRANCH}")
    fetch(repos["work"], repos["origin"])
    out = probe(repos["work"])
    assert out["merged"] is True and out["merge_subject"] == f"Merge pull request #7 from o/{BRANCH}"


def test_reused_branch_name_after_old_merge_is_not_merged(repos):
    w = repos["work"]
    branch_with_commit(w, repos["origin"])
    merge_in_other(repos["other"], f"Merge pull request #7 from o/{BRANCH}")
    fetch(w, repos["origin"])
    git(w, "branch", "-q", "-D", BRANCH)
    git(w, "push", "-q", str(repos["origin"]), "--delete", BRANCH)
    git(w, "branch", "-q", BRANCH, "origin/main")
    git(w, "push", "-q", str(repos["origin"]), BRANCH)
    fetch(w, repos["origin"])
    assert probe(w)["merged"] is False


def test_deleted_branch_merged_via_pushed_head(repos):
    w = repos["work"]
    head = branch_with_commit(w, repos["origin"])
    merge_in_other(repos["other"], "Merge branch 'something-else'")
    git(w, "push", "-q", str(repos["origin"]), "--delete", BRANCH)
    git(w, "branch", "-q", "-D", BRANCH)
    fetch(w, repos["origin"])
    assert probe(w)["merged"] is False
    out = probe(w, pushed_head=head)
    assert (out["on_origin"], out["merged"]) == (False, True)
    assert out["merge_subject"] == "Merge branch 'something-else'"


def test_stale_origin_main_is_not_merged(repos):
    head = branch_with_commit(repos["work"], repos["origin"])
    merge_in_other(repos["other"], f"Merge pull request #7 from o/{BRANCH}")
    out = probe(repos["work"], pushed_head=head)          # no fetch: origin/main is stale
    assert (out["on_origin"], out["ahead"], out["merged"]) == (True, 1, False)


def test_missing_repo_is_unknown(tmp_path):
    out = probe(tmp_path / "nope")
    assert out["merged"] == "unknown" and out["on_origin"] == "unknown" and out["ahead"] == "unknown"


def test_merge_subject_with_quotes_backslash_and_utf8_is_valid_json(repos):
    head = branch_with_commit(repos["work"], repos["origin"])
    subject = 'Merge "quoted" \\ back café ' + f"from o/{BRANCH}"
    merge_in_other(repos["other"], subject)
    fetch(repos["work"], repos["origin"])
    out = probe(repos["work"], pushed_head=head)
    assert out["merged"] is True and out["merge_subject"] == subject


def test_probe_is_valid_json_under_a_utf8_locale(repos):
    head = branch_with_commit(repos["work"], repos["origin"])
    merge_in_other(repos["other"], f"Merge café from o/{BRANCH}")
    fetch(repos["work"], repos["origin"])
    env = dict(ENV, LC_ALL="C.UTF-8", LANG="C.UTF-8")
    proc = subprocess.run(["sh", PROBE, str(repos["work"]), BRANCH, head], capture_output=True,
                          text=True, env=env, timeout=20)
    assert json.loads(proc.stdout)["merge_subject"] == f"Merge café from o/{BRANCH}"
