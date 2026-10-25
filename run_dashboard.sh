#!/usr/bin/env bash
# Run the demo dashboard — six-page Streamlit app over the curated package.
#
# Usage:
#   ./run_dashboard.sh                  # opens in your browser
#   ./run_dashboard.sh --server.port 8637 --server.headless true
#
# Any extra args are passed through to streamlit.
set -euo pipefail
cd "$(dirname "$0")"
exec uv run --group demo streamlit run dashboard/app.py "$@"
