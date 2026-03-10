#!/usr/bin/env bash
set -e

if [ -f requirements.txt ]; then
  echo "Installing runtime dependencies..."
  pip install -r requirements.txt
fi
