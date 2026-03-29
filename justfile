# Show available top-level workflows.
help:
    @just --list

# Build and validate both Python distributions for local development.
build:
    just --justfile server/justfile --working-directory server build
    just --justfile mitmproxy_addon/justfile --working-directory mitmproxy_addon build

# Upgrade dependency locks for Python projects.
upgrade-python-deps:
    just --justfile server/justfile --working-directory server upgrade
    just --justfile mitmproxy_addon/justfile --working-directory mitmproxy_addon upgrade

# Install repository pre-commit hooks.
pre-commit-install:
    env -u VIRTUAL_ENV uvx pre-commit install

# Run repository pre-commit hooks.
pre-commit-run *args='--all-files':
    env -u VIRTUAL_ENV uvx pre-commit run {{args}}

# Check or sync package versions from VERSION.txt.
sync-version *args='':
    env -u VIRTUAL_ENV uv run python hack/sync_version.py {{args}}

# Publish the only Python distribution released to the selected package index.
publish repository='pypi':
    just --justfile mitmproxy_addon/justfile --working-directory mitmproxy_addon publish {{repository}}
