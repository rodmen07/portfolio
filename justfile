# Portfolio workspace task runner.
#
# `just` lists all available recipes. Recipes wrap the most common workflows
# so contributors don't need to remember bash vs. PowerShell variants.

# Default recipe: list available recipes.
default:
    @just --list

# Initialize / refresh git submodules.
init:
    git submodule update --init --recursive

# Update all submodules to their latest configured commits.
update:
    git submodule update --remote --recursive

# Show submodule status.
status:
    git submodule status --recursive

# Run the cross-repo workspace tests.
test:
    bash ./run_workspace_tests.sh

# Run pre-commit hooks on all files. Requires pre-commit installed locally.
lint:
    pre-commit run --all-files

# Run pre-commit hooks on staged changes only.
lint-staged:
    pre-commit run

# Build the Docker image used by CI for cross-repo tests.
build-runner-image:
    docker build -t portfolio-runner:dev .

# Print key environment variables a contributor likely needs to set.
env-help:
    @echo "Required for most local Rust tests:"
    @echo "  AUTH_JWT_SECRET=dev-insecure-secret-change-me"
    @echo "  TEST_DATABASE_URL=sqlite::memory:"
    @echo "See .env.example for the full list."

# Run cargo tests for a single Rust microservice.
# Usage: just rust-test reporting-service
rust-test service:
    cd microservices/{{service}} && \
        AUTH_JWT_SECRET=dev-insecure-secret-change-me \
        TEST_DATABASE_URL=sqlite::memory: \
        cargo test
