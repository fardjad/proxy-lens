# Show available top-level workflows.
help:
    @just --list

# Build and validate both Python distributions.
build:
    just --justfile server/justfile --working-directory server build
    just --justfile mitmproxy_addon/justfile --working-directory mitmproxy_addon build

# Upgrade dependency locks for Python projects.
upgrade-python-deps:
    just --justfile server/justfile --working-directory server upgrade
    just --justfile mitmproxy_addon/justfile --working-directory mitmproxy_addon upgrade

# Publish both Python distributions to the selected package index.
publish repository='pypi':
    just --justfile server/justfile --working-directory server publish {{repository}}
    just --justfile mitmproxy_addon/justfile --working-directory mitmproxy_addon publish {{repository}}
