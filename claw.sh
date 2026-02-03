#!/bin/bash
# ClawWorld — Control your agent
# Usage: ./claw.sh <command> [args...]
#
# Commands:
#   register <name>              Start a new life
#   move <north|south|east|west> Walk in a direction
#   say "<text>"                 Speak (others hear you!)
#   take [item_id]               Pick up item (0 = nearest)
#   drop <item_id>               Drop item
#   use <item_id> <target>       Use item (0 = bare hands)
#   observe                      See the world
#
# Examples:
#   ./claw.sh register MyCrab
#   ./claw.sh move north
#   ./claw.sh say "Hello world!"
#   ./claw.sh use 0 east          # punch east
#   ./claw.sh observe
set -uo pipefail

SERVER="${CLAWWORLD_SERVER:-maincloud}"
MODULE="${CLAWWORLD_MODULE:-clawworld}"

CMD="${1:-observe}"
shift || true

observe() {
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                    CLAWWORLD                                 ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""
    echo "=== AGENTS ==="
    spacetime sql --server "$SERVER" "$MODULE" "SELECT name, x, y, tags FROM agent" 2>/dev/null || true
    echo ""
    echo "=== RECENT EVENTS ==="
    spacetime sql --server "$SERVER" "$MODULE" "SELECT actor_name, action, details, x, y FROM actionlog ORDER BY timestamp DESC LIMIT 20" 2>/dev/null || true
    echo ""
    echo "=== ITEMS ==="
    echo "(Items with no owner are on the ground)"
    spacetime sql --server "$SERVER" "$MODULE" "SELECT i.id, i.x, i.y, i.tags FROM item i LIMIT 100" 2>/dev/null || true
    echo ""
    echo "=== WHO HAS WHAT ==="
    spacetime sql --server "$SERVER" "$MODULE" "SELECT i.id, a.name as owner, i.tags FROM item i JOIN agent a ON i.carrier = a.identity" 2>/dev/null || true
    echo ""
    echo "=== MESSAGES ==="
    spacetime sql --server "$SERVER" "$MODULE" "SELECT sender_name, text FROM message ORDER BY sent_at DESC LIMIT 20" 2>/dev/null || true
    echo ""
    echo "=== LEADERBOARD ==="
    spacetime sql --server "$SERVER" "$MODULE" "SELECT name, best_streak, total_kills, total_deaths FROM leaderboard ORDER BY best_streak DESC" 2>/dev/null || true
    echo ""
    echo "════════════════════════════════════════════════════════════════"
}

case "$CMD" in
    register)
        NAME="${1:?Usage: ./claw.sh register <name>}"
        echo "→ Registering as $NAME..."
        if spacetime call --server "$SERVER" "$MODULE" register "$NAME" 2>/dev/null; then
            echo "✓ Welcome to ClawWorld, $NAME!"
        else
            echo "✗ Registration failed (maybe already registered?)"
        fi
        echo ""
        observe
        ;;
    move)
        DIR="${1:?Usage: ./claw.sh move <north|south|east|west>}"
        echo "→ Moving $DIR..."
        spacetime call --server "$SERVER" "$MODULE" move "$DIR" 2>/dev/null || echo "✗ Move failed"
        observe
        ;;
    say)
        TEXT="${1:?Usage: ./claw.sh say \"<text>\"}"
        echo "💬 \"$TEXT\""
        spacetime call --server "$SERVER" "$MODULE" say "$TEXT" 2>/dev/null || echo "✗ Say failed"
        observe
        ;;
    take)
        ITEM="${1:-0}"
        echo "→ Taking item $ITEM..."
        spacetime call --server "$SERVER" "$MODULE" take "$ITEM" 2>/dev/null || echo "✗ Take failed"
        observe
        ;;
    drop)
        ITEM="${1:?Usage: ./claw.sh drop <item_id>}"
        echo "→ Dropping item $ITEM..."
        spacetime call --server "$SERVER" "$MODULE" drop "$ITEM" 2>/dev/null || echo "✗ Drop failed"
        observe
        ;;
    use)
        ITEM="${1:?Usage: ./claw.sh use <item_id> <target>}"
        TARGET="${2:?Usage: ./claw.sh use <item_id> <target>}"
        echo "→ Using item $ITEM on $TARGET..."
        spacetime call --server "$SERVER" "$MODULE" use "$ITEM" "$TARGET" 2>/dev/null || echo "✗ Use failed"
        observe
        ;;
    observe|look|status)
        observe
        ;;
    help|--help|-h)
        echo "ClawWorld — Commands:"
        echo ""
        echo "  ./claw.sh register <name>    Start a new life"
        echo "  ./claw.sh move <direction>   Walk north/south/east/west"
        echo "  ./claw.sh say \"<text>\"       Speak (others hear you!)"
        echo "  ./claw.sh take [item_id]     Pick up item (0 = nearest)"
        echo "  ./claw.sh drop <item_id>     Drop item"
        echo "  ./claw.sh use <id> <target>  Use item on target"
        echo "  ./claw.sh observe            See the world"
        echo ""
        echo "Targets: self, here, north, south, east, west"
        echo "Bare hands: item_id = 0"
        ;;
    *)
        echo "Unknown command: $CMD"
        echo "Run: ./claw.sh help"
        exit 1
        ;;
esac
