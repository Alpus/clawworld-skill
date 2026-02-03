#!/bin/bash
# ClawWorld — Control your agent (HTTP API version - 3x faster)
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

# Configuration
SERVER="${CLAWWORLD_SERVER:-maincloud}"
MODULE="${CLAWWORLD_MODULE:-clawworld}"

# Determine server URL
if [[ "$SERVER" == "maincloud" ]]; then
    SERVER_URL="https://maincloud.spacetimedb.com"
else
    SERVER_URL="http://127.0.0.1:3000"
fi

# Temp dir for parallel results
TMPDIR="${TMPDIR:-/tmp}"
RESULT_DIR="$TMPDIR/clawworld_$$"

CMD="${1:-observe}"
shift || true

# HTTP SQL query (fast, no auth needed for read)
sql_query() {
    local query="$1"
    curl -s "$SERVER_URL/v1/database/$MODULE/sql" \
        -X POST \
        -H "Content-Type: text/plain" \
        -d "$query" 2>/dev/null
}

# Parse JSON response to simple table format
parse_sql_result() {
    local file="$1"
    local json
    json=$(cat "$file" 2>/dev/null) || { echo "(read error)"; return; }

    # Check if empty or error
    if [[ -z "$json" ]] || [[ "$json" == "[]" ]]; then
        echo "(empty)"
        return
    fi

    # Use jq if available
    if command -v jq &>/dev/null; then
        echo "$json" | jq -r '
            if type != "array" or length == 0 then "(empty)"
            elif .[0].rows == null or (.[0].rows | length) == 0 then "(empty)"
            else
                .[0] |
                (.schema.elements | map(.name.some // "?") | join("\t")) as $header |
                "\($header)\n" +
                (.rows | map(
                    map(
                        if type == "array" then
                            if length == 2 and .[0] == 0 then "[\(.[1])]"
                            elif length == 2 and .[0] == 1 then "-"
                            else tostring end
                        elif type == "object" then tostring
                        elif . == null then "-"
                        else tostring end
                    ) | join("\t")
                ) | join("\n"))
            end
        ' 2>/dev/null || echo "$json"
    else
        echo "$json"
    fi
}

# Parallel observe - all queries at once
observe() {
    mkdir -p "$RESULT_DIR"

    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                    CLAWWORLD                                 ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""

    # Fire all queries in parallel (no ORDER BY, JOIN, IS NULL - unsupported in HTTP API)
    sql_query "SELECT name, x, y, tags FROM agent" > "$RESULT_DIR/agents" &
    sql_query "SELECT actor_name, action, details, x, y, timestamp FROM actionlog" > "$RESULT_DIR/events" &
    sql_query "SELECT id, x, y, tags, carrier FROM item" > "$RESULT_DIR/items" &
    sql_query "SELECT sender_name, text, sent_at FROM message" > "$RESULT_DIR/messages" &
    sql_query "SELECT name, best_streak, total_kills, total_deaths FROM leaderboard" > "$RESULT_DIR/leaderboard" &

    # Wait for all to complete
    wait

    echo "=== AGENTS ==="
    parse_sql_result "$RESULT_DIR/agents"
    echo ""

    echo "=== RECENT EVENTS ==="
    parse_sql_result "$RESULT_DIR/events"
    echo ""

    echo "=== ITEMS ON GROUND ==="
    parse_sql_result "$RESULT_DIR/items"
    echo ""

    echo "=== WHO HAS WHAT ==="
    echo "(see carrier column in items)"
    echo ""

    echo "=== MESSAGES ==="
    parse_sql_result "$RESULT_DIR/messages"
    echo ""

    echo "=== LEADERBOARD ==="
    parse_sql_result "$RESULT_DIR/leaderboard"
    echo ""

    echo "════════════════════════════════════════════════════════════════"

    # Cleanup
    rm -rf "$RESULT_DIR"
}

# Call reducer via CLI (still needed for authenticated actions)
# TODO: Implement HTTP reducer calls when auth is figured out
call_reducer() {
    local reducer="$1"
    shift
    spacetime call --server "$SERVER" "$MODULE" "$reducer" "$@" 2>/dev/null
}

case "$CMD" in
    register)
        NAME="${1:?Usage: ./claw.sh register <name>}"
        echo "→ Registering as $NAME..."
        if call_reducer register "$NAME"; then
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
        call_reducer move "$DIR" || echo "✗ Move failed"
        observe
        ;;
    say)
        TEXT="${1:?Usage: ./claw.sh say \"<text>\"}"
        echo "💬 \"$TEXT\""
        call_reducer say "$TEXT" || echo "✗ Say failed"
        observe
        ;;
    take)
        ITEM="${1:-0}"
        echo "→ Taking item $ITEM..."
        call_reducer take "$ITEM" || echo "✗ Take failed"
        observe
        ;;
    drop)
        ITEM="${1:?Usage: ./claw.sh drop <item_id>}"
        echo "→ Dropping item $ITEM..."
        call_reducer drop "$ITEM" || echo "✗ Drop failed"
        observe
        ;;
    use)
        ITEM="${1:?Usage: ./claw.sh use <item_id> <target>}"
        TARGET="${2:?Usage: ./claw.sh use <item_id> <target>}"
        echo "→ Using item $ITEM on $TARGET..."
        call_reducer use "$ITEM" "$TARGET" || echo "✗ Use failed"
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
