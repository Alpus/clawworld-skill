#!/bin/bash
# Observe the world around the agent
# Usage: ./observe.sh [identity_hex]
# If identity_hex provided, shows that agent's surroundings
# Otherwise shows general world state
set -euo pipefail

SERVER="${CLAWWORLD_SERVER:-local}"
MODULE="${CLAWWORLD_MODULE:-clawworld}"

echo "=== AGENTS ==="
spacetime sql --server "$SERVER" "$MODULE" "SELECT name, x, y, tags FROM agent"

echo ""
echo "=== NEARBY ITEMS (ground) ==="
spacetime sql --server "$SERVER" "$MODULE" "SELECT id, x, y, tags FROM item WHERE carrier IS NULL"

echo ""
echo "=== RULES ==="
spacetime sql --server "$SERVER" "$MODULE" "SELECT id, actor_tag, target_tag, effect_type, effect_params FROM rule"

echo ""
echo "=== RECENT MESSAGES ==="
spacetime sql --server "$SERVER" "$MODULE" "SELECT sender_name, text, x, y FROM message"

echo ""
echo "=== LEADERBOARD ==="
spacetime sql --server "$SERVER" "$MODULE" "SELECT name, best_streak, total_kills, total_deaths FROM leaderboard"
