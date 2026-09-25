FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /repo

COPY . .

# Python test deps
RUN pip install --no-cache-dir pytest

# Configure a git identity (some hooks run real git operations in temp repos)
RUN git config --global user.email "test@example.com" \
    && git config --global user.name "Docker Test Runner"

# One pytest process per plugin (see README "Running tests")
CMD bash -c "for p in agent-isdd agent-tdd agent-nelly shared code-reviewer; do python -m pytest \$p -q || exit 1; done"
