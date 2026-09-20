FROM python:3.11-slim AS python-base

# Install Node.js 20 for agent-cache-plugin tests
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /repo

COPY . .

# Python test deps
RUN pip install --no-cache-dir pytest

# Configure a git identity (some hooks run real git operations in temp repos)
RUN git config --global user.email "test@example.com" \
    && git config --global user.name "Docker Test Runner"

# Node deps for agent-cache-plugin
RUN cd agent-cache-plugin && npm ci --ignore-scripts

# Default: run all Python tests then Node tests
CMD bash -c "python -m pytest agent-isdd agent-tdd agent-nelly plugin-orchestrator shared agent-ux code-reviewer -q && cd agent-cache-plugin && npm test"
