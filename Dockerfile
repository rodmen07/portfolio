FROM python:3.14-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PATH="/root/.cargo/bin:${PATH}"

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    build-essential gcc g++ git curl ca-certificates wget \
    libssl-dev pkg-config libpq-dev golang-go jq \
 && rm -rf /var/lib/apt/lists/*

# Install rustup non-interactively and maturin
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y \
 && /bin/bash -lc "source $HOME/.cargo/env && rustup default stable" \
 && pip install --upgrade pip setuptools wheel maturin

WORKDIR /workspace

COPY . /workspace

RUN chmod +x /workspace/run_workspace_tests.sh

CMD ["/workspace/run_workspace_tests.sh"]
