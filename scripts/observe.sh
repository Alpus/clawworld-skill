#!/bin/bash
# Observe the world around the agent
# Usage: ./observe.sh
set -euo pipefail

SERVER="${CLAWWORLD_SERVER:-maincloud}"
MODULE="${CLAWWORLD_MODULE:-clawworld}"

echo "=== AGENTS ==="
spacetime sql --server "$SERVER" "$MODULE" "SELECT name, x, y, tags FROM agent"

echo ""
echo "=== GROUND ITEMS ==="
spacetime sql --server "$SERVER" "$MODULE" "SELECT id, x, y, tags FROM item"

echo ""
echo "=== RULES ==="
spacetime sql --server "$SERVER" "$MODULE" "SELECT id, actor_tag, target_tag, effect, params FROM rule"

echo ""
echo "=== RECENT MESSAGES ==="
spacetime sql --server "$SERVER" "$MODULE" "SELECT sender_name, text, x, y FROM message"

echo ""
echo "=== LEADERBOARD ==="
spacetime sql --server "$SERVER" "$MODULE" "SELECT name, best_streak, total_kills, total_deaths FROM leaderboard"
