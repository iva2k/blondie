#!/bin/bash
set -e

cd /workspace

# Bootstrap check
if [ ! -f ".agent/project.yaml" ]; then
  echo "🚀 Bootstrapping new repo..."
  blondie bootstrap .
fi

# Run agent
exec blondie run "$@"
