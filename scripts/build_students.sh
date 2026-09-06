#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

docker compose run --rm sandbox
docker compose build jupyter
docker compose up -d jupyter

docker compose ps
