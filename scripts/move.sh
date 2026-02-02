#!/bin/bash
# Move the agent in a direction
# Usage: ./move.sh <north|south|east|west>
set -euo pipefail

DIRECTION="${1:?Usage: move.sh <north|south|east|west>}"
SERVER="${CLAWWORLD_SERVER:-local}"
MODULE="${CLAWWORLD_MODULE:-clawworld}"

spacetime call --server "$SERVER" "$MODULE" move "$DIRECTION"
