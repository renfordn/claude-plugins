#!/usr/bin/env bash
# Configure git to use the shared hooks in .githooks/
# Run once after cloning: bash scripts/setup-hooks.sh
set -e
git config core.hooksPath .githooks
echo "Git hooks configured → .githooks/"
