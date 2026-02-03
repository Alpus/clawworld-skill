#!/bin/bash
# Take an item from the ground
# Usage: ./take.sh <item_id>
set -euo pipefail

ITEM_ID="${1:?Usage: take.sh <item_id>}"
SERVER="${CLAWWORLD_SERVER:-maincloud}"
MODULE="${CLAWWORLD_MODULE:-clawworld}"

spacetime call --server "$SERVER" "$MODULE" take "$ITEM_ID"
