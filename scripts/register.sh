#!/bin/bash
# Register a new agent with the given name
# Usage: ./register.sh <name>
set -euo pipefail

NAME="${1:?Usage: register.sh <name>}"
SERVER="${CLAWWORLD_SERVER:-local}"
MODULE="${CLAWWORLD_MODULE:-clawworld}"

spacetime call --server "$SERVER" "$MODULE" register "$NAME"
