# Development

Before AI bot can pick it up, we do it the old-fashion way.

## Random Thoughts

1. Task selection and claiming is complex and intervowen process. We rely on `tasks.get_next_task()` to find next task but then we use `tasks.claim_task()` to create new branch by calling `git branch` when coordination method is git-branch. When the method is different, 2nd `git branch` after `tasks.claim_task()` would fail. We can't remove the 2nd call to `git branch` for other coordination methods. Need to interweave the involved code in different modules.

2. When debugging, and something fails, we need an ability to rerun the agent and `tasks.claim_task()`, but it has to be aware to keep going with previous task, since branch may already been pushed to the remote. We can use presence of the local branch to detect that it is our already claimed task. We need claim_task to probe both local and remote repos for the branch presence.

3. In production it is still useful to be able to restart the agent and continue working on an already started task, so we should check local branches. Agent should pull main branch only, check local branches to find a task is in progress, and pick it up.

## Local Dev Setup

To simulate a remote environment locally (so `git push` works), use the setup script:

```bash
poetry run python scripts/setup_dev_repo.py
```

This creates `_tmp/repo` (working dir) and `_tmp/remote.git` (bare origin).

Add this to `pyproject.toml` for convenience:

```toml
[tool.poe.tasks]
setup-dev = "python scripts/setup_dev_repo.py"
```
