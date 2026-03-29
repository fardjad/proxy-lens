# Show available top-level workflows.
help:
    @just --list

# Ensure project dependencies are installed before running maintainer workflows.
_install-deps:
    cd server && env -u VIRTUAL_ENV uv sync --dev
    cd mitmproxy_addon && env -u VIRTUAL_ENV uv sync --dev
    cd ui && bun install

# Ensure package versions match VERSION.txt before release workflows.
_check-version-sync:
    env -u VIRTUAL_ENV uv run python hack/sync_version.py --check

# Build and validate both Python distributions for local development.
build: _install-deps
    just --justfile server/justfile --working-directory server build
    just --justfile mitmproxy_addon/justfile --working-directory mitmproxy_addon build

# Run all repository tests.
test: _install-deps
    just --justfile server/justfile --working-directory server test
    just --justfile mitmproxy_addon/justfile --working-directory mitmproxy_addon test
    cd ui && bun test

# Upgrade dependency locks for Python projects and the UI.
upgrade-deps: _install-deps
    just --justfile server/justfile --working-directory server upgrade
    just --justfile mitmproxy_addon/justfile --working-directory mitmproxy_addon upgrade
    cd ui && bun update --latest

# Install repository pre-commit hooks.
pre-commit-install:
    env -u VIRTUAL_ENV uvx pre-commit install

# Run repository pre-commit hooks.
pre-commit-run *args='--all-files':
    env -u VIRTUAL_ENV uvx pre-commit run {{args}}

# Check or sync package versions from VERSION.txt.
sync-version *args='':
    env -u VIRTUAL_ENV uv run python hack/sync_version.py {{args}}

# Publish the mitmproxy addon and optionally the runtime Docker image.
publish repository='pypi' image='fardjad/proxylens': build _check-version-sync
    just --justfile mitmproxy_addon/justfile --working-directory mitmproxy_addon publish {{repository}}
    if [ -n "{{image}}" ]; then \
        version="$(tr -d '\n' < VERSION.txt)"; \
        docker build -t "{{image}}:${version}" -t "{{image}}:latest" .; \
        docker push "{{image}}:${version}"; \
        docker push "{{image}}:latest"; \
    fi
