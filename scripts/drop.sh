#!/bin/bash
# Drop an item from inventory
# Usage: ./drop.sh <item_id>
set -euo pipefail

ITEM_ID="${1:?Usage: drop.sh <item_id>}"
SERVER="${CLAWWORLD_SERVER:-maincloud}"
MODULE="${CLAWWORLD_MODULE:-clawworld}"

spacetime call --server "$SERVER" "$MODULE" drop "$ITEM_ID"
