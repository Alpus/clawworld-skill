#!/bin/bash
# Use an item on a target
# Usage: ./use.sh <item_id> <target>
# target: self | here | north | south | east | west
set -euo pipefail

ITEM_ID="${1:?Usage: use.sh <item_id> <target>}"
TARGET="${2:?Usage: use.sh <item_id> <target>}"
SERVER="${CLAWWORLD_SERVER:-maincloud}"
MODULE="${CLAWWORLD_MODULE:-clawworld}"

spacetime call --server "$SERVER" "$MODULE" use "$ITEM_ID" "$TARGET"
