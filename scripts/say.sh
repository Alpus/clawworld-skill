#!/bin/bash
# Say a message
# Usage: ./say.sh <text>
set -euo pipefail

TEXT="${1:?Usage: say.sh <text>}"
SERVER="${CLAWWORLD_SERVER:-local}"
MODULE="${CLAWWORLD_MODULE:-clawworld}"

spacetime call --server "$SERVER" "$MODULE" say "$TEXT"
