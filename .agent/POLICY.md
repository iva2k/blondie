# Blondie Self-Policy

## Autonomy Gates

git-merge: allow        # Self-merge OK during bootstrap
deploy-docker: allow    # Self-deploy OK
install-binary: prompt  # apt installs need review
add-package: allow      # pip requirements OK

## Commands

install: pip install -e .
test: pytest tests/ -v
build: python -m build
