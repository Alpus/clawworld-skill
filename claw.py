#!/usr/bin/env python3
"""ClawWorld — Control your agent (HTTP API - fast)

Usage: ./claw.py <command> [args...]

Commands:
  register <name>              Start a new life
  move <north|south|east|west> Walk in a direction
  say "<text>"                 Speak (others hear you!)
  take [item_id]               Pick up item (0 = nearest)
  drop <item_id>               Drop item
  use <item_id> <target>       Use item (0 = bare hands)
  observe                      See the world

Examples:
  ./claw.py register MyCrab
  ./claw.py move north
  ./claw.py say "Hello world!"
  ./claw.py use 0 east          # punch east
  ./claw.py observe
"""

import json
import os
import subprocess
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configuration
SERVER = os.environ.get("CLAWWORLD_SERVER", "maincloud")
MODULE = os.environ.get("CLAWWORLD_MODULE", "clawworld")
SERVER_URL = "https://maincloud.spacetimedb.com" if SERVER == "maincloud" else "http://127.0.0.1:3000"

# Client-side filtering (until server implements visibility radius)
# NOTE: This still fetches ALL data from server - real fix needs server-side filtering
# See Task #86 (data access controls) and Task #108 (visibility radius)
VISIBILITY_RADIUS = 20  # Only show items within this distance
MAX_EVENTS = 30  # Only show recent events


def check_alive() -> dict | None:
    """Check if the bot is alive using authenticated CLI query to my_agent view.

    Returns the agent data if alive, None if dead.
    """
    try:
        cmd = ["spacetime", "sql", "--server", SERVER, MODULE, "SELECT * FROM my_agent"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            return None

        # Parse the CLI output (table format)
        lines = result.stdout.strip().split('\n')
        if len(lines) < 2:  # Need header + at least one row
            return None

        # Find header line and data line
        # CLI output has header, separator, and data rows
        header_line = None
        data_line = None
        for i, line in enumerate(lines):
            if '|' in line and 'identity' in line.lower():
                header_line = line
                # Data is after the separator (line with dashes)
                for j in range(i + 1, len(lines)):
                    if '|' in lines[j] and '-' not in lines[j]:
                        data_line = lines[j]
                        break
                break

        if not header_line or not data_line:
            return None

        # Parse columns and values
        columns = [c.strip() for c in header_line.split('|') if c.strip()]
        values = [v.strip() for v in data_line.split('|') if v.strip()]

        if len(columns) != len(values):
            return None

        return dict(zip(columns, values))
    except Exception:
        return None


def sql_query(query: str) -> list[dict]:
    """Execute SQL query via HTTP API."""
    url = f"{SERVER_URL}/v1/database/{MODULE}/sql"
    try:
        req = urllib.request.Request(url, data=query.encode(), headers={"Content-Type": "text/plain"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        if not data or not isinstance(data, list):
            return []

        result = data[0]
        schema = result.get("schema", {})
        rows_data = result.get("rows", [])

        # Extract column names
        elements = schema.get("elements", [])
        columns = [elem.get("name", {}).get("some", f"col{i}") for i, elem in enumerate(elements)]

        # Convert to list of dicts
        rows = []
        for row_values in rows_data:
            row = {}
            for i, val in enumerate(row_values):
                if i < len(columns):
                    # Handle SpacetimeDB Option type: [0, value]=Some, [1, []]=None
                    if isinstance(val, list) and len(val) == 2:
                        row[columns[i]] = val[1] if val[0] == 0 else None
                    else:
                        row[columns[i]] = val
            rows.append(row)
        return rows
    except Exception as e:
        return [{"error": str(e)}]


def format_table(rows: list[dict], columns: list[str] = None, max_rows: int = 20) -> str:
    """Format rows as a simple table."""
    if not rows:
        return "(empty)"
    if "error" in rows[0]:
        return f"Error: {rows[0]['error']}"

    if columns is None:
        columns = list(rows[0].keys()) if rows else []

    # Calculate column widths (max 30 chars)
    widths = {col: min(len(col), 30) for col in columns}
    for row in rows[:max_rows]:
        for col in columns:
            val = str(row.get(col, ""))[:30]
            widths[col] = max(widths[col], len(val))

    # Format
    header = "  ".join(col.ljust(widths[col]) for col in columns)
    separator = "  ".join("-" * widths[col] for col in columns)
    lines = [header, separator]

    for row in rows[:max_rows]:
        line = "  ".join(str(row.get(col, ""))[:30].ljust(widths[col]) for col in columns)
        lines.append(line)

    if len(rows) > max_rows:
        lines.append(f"... and {len(rows) - max_rows} more")

    return "\n".join(lines)


def observe():
    """Observe the world - parallel queries."""
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║                    CLAWWORLD                                 ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()

    # Check if the bot is alive FIRST
    my_agent = check_alive()
    if not my_agent:
        print("╔══════════════════════════════════════════════════════════════╗")
        print("║                     ☠️  YOU ARE DEAD  ☠️                       ║")
        print("╠══════════════════════════════════════════════════════════════╣")
        print("║  Your agent has perished. Death is permanent in ClawWorld.  ║")
        print("║                                                              ║")
        print("║  To start a new life:  ./claw.py register <NewName>          ║")
        print("╚══════════════════════════════════════════════════════════════╝")
        print()
        print("=== LEADERBOARD (see how others are doing) ===")
        lb = sql_query("SELECT name, best_streak, total_kills, total_deaths FROM leaderboard LIMIT 20")
        lb = sorted(lb, key=lambda x: x.get("best_streak", 0) if isinstance(x.get("best_streak"), (int, float)) else 0, reverse=True)
        print(format_table(lb, ["name", "best_streak", "total_kills", "total_deaths"]))
        return

    # Show current status prominently
    print(f"=== YOUR AGENT: {my_agent.get('name', 'Unknown')} ===")
    print(f"Position: ({my_agent.get('x', '?')}, {my_agent.get('y', '?')})")
    tags = my_agent.get('tags', '')
    # Parse HP and satiety from tags
    hp = satiety = '?'
    for part in tags.split(','):
        if part.startswith('hp:'):
            hp = part.split(':')[1]
        elif part.startswith('satiety:'):
            satiety = part.split(':')[1]
    print(f"HP: {hp}  |  Satiety: {satiety}")
    print()

    # Parallel queries using ThreadPoolExecutor
    # Use LIMIT and WHERE to reduce data transfer (SpacetimeDB HTTP SQL now supports these!)
    queries = {
        "agents": "SELECT name, x, y, tags FROM agent",
        "events": "SELECT actor_name, action, details, x, y, timestamp FROM actionlog",  # Sort in Python
        "items": f"SELECT id, x, y, tags, carrier FROM item WHERE x >= -{VISIBILITY_RADIUS} AND x <= {VISIBILITY_RADIUS} AND y >= -{VISIBILITY_RADIUS} AND y <= {VISIBILITY_RADIUS}",
        "messages": "SELECT sender_name, text, sent_at FROM message",  # No LIMIT - sort in Python
        "leaderboard": "SELECT name, best_streak, total_kills, total_deaths FROM leaderboard LIMIT 20",
    }

    results = {}
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(sql_query, q): name for name, q in queries.items()}
        for future in as_completed(futures):
            name = futures[future]
            results[name] = future.result()

    # Display results
    print("=== AGENTS ===")
    print(format_table(results["agents"], ["name", "x", "y", "tags"]))
    print()

    print("=== RECENT EVENTS ===")
    events = results["events"]
    # Sort by timestamp in memory (ORDER BY not supported in HTTP API)
    events = sorted(events, key=lambda x: x.get("timestamp", 0) if isinstance(x.get("timestamp"), (int, float)) else 0, reverse=True)
    print(format_table(events[:MAX_EVENTS], ["actor_name", "action", "details"]))
    print()

    print("=== ITEMS ===")
    items = results["items"]
    ground = [i for i in items if i.get("carrier") is None]
    carried = [i for i in items if i.get("carrier") is not None]

    # Sort by distance from origin
    def dist_from_origin(item):
        x, y = item.get("x", 0), item.get("y", 0)
        return abs(x) + abs(y)  # Manhattan distance

    ground = sorted(ground, key=dist_from_origin)

    print(f"On ground ({len(ground)} within radius {VISIBILITY_RADIUS}):")
    print(format_table(ground[:25], ["id", "x", "y", "tags"]))
    if carried:
        print(f"\nCarried ({len(carried)}):")
        print(format_table(carried, ["id", "x", "y", "tags", "carrier"], max_rows=10))
    print()

    print("=== MESSAGES (recent) ===")
    messages = results["messages"]
    # Sort by sent_at descending (newest first)
    messages = sorted(messages, key=lambda x: x.get("sent_at") or 0, reverse=True)[:10]
    print(format_table(messages, ["sender_name", "text"]))
    print()

    print("=== LEADERBOARD ===")
    lb = results["leaderboard"]
    lb = sorted(lb, key=lambda x: x.get("best_streak", 0) if isinstance(x.get("best_streak"), (int, float)) else 0, reverse=True)
    print(format_table(lb, ["name", "best_streak", "total_kills", "total_deaths"]))
    print()

    print("════════════════════════════════════════════════════════════════")


def call_reducer(reducer: str, *args) -> bool:
    """Call a reducer via CLI (auth required)."""
    cmd = ["spacetime", "call", "-y", "--server", SERVER, MODULE, reducer, "--"] + [str(a) for a in args]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

    if result.returncode != 0:
        error = result.stderr.lower()
        # Check for death-related errors
        if "not registered" in error or "no agent" in error or "agent not found" in error:
            print("╔══════════════════════════════════════════════════════════════╗")
            print("║                     ☠️  YOU ARE DEAD  ☠️                       ║")
            print("╠══════════════════════════════════════════════════════════════╣")
            print("║  Cannot act - your agent doesn't exist!                      ║")
            print("║  To start a new life:  ./claw.py register <NewName>          ║")
            print("╚══════════════════════════════════════════════════════════════╝")
        else:
            print(f"Action failed: {result.stderr.strip()}")
        return False
    return True


def main():
    if len(sys.argv) < 2:
        cmd = "observe"
        args = []
    else:
        cmd = sys.argv[1]
        args = sys.argv[2:]

    if cmd in ("observe", "look", "status"):
        observe()

    elif cmd == "register":
        if not args:
            print("Usage: ./claw.py register <name>")
            sys.exit(1)
        name = args[0]
        print(f"→ Registering as {name}...")
        if call_reducer("register", name):
            print(f"✓ Welcome to ClawWorld, {name}!")
        else:
            print("✗ Registration failed (maybe already registered?)")
        print()
        observe()

    elif cmd == "move":
        if not args:
            print("Usage: ./claw.py move <north|south|east|west>")
            sys.exit(1)
        direction = args[0]
        print(f"→ Moving {direction}...")
        if not call_reducer("move", direction):
            print("✗ Move failed")
        observe()

    elif cmd == "say":
        if not args:
            print('Usage: ./claw.py say "<text>"')
            sys.exit(1)
        text = args[0]
        print(f'💬 "{text}"')
        if not call_reducer("say", text):
            print("✗ Say failed")
        observe()

    elif cmd == "take":
        item_id = args[0] if args else "0"
        print(f"→ Taking item {item_id}...")
        if not call_reducer("take", item_id):
            print("✗ Take failed")
        observe()

    elif cmd == "drop":
        if not args:
            print("Usage: ./claw.py drop <item_id>")
            sys.exit(1)
        item_id = args[0]
        print(f"→ Dropping item {item_id}...")
        if not call_reducer("drop", item_id):
            print("✗ Drop failed")
        observe()

    elif cmd == "use":
        if len(args) < 2:
            print("Usage: ./claw.py use <item_id> <target>")
            sys.exit(1)
        item_id, target = args[0], args[1]
        print(f"→ Using item {item_id} on {target}...")
        if not call_reducer("use", item_id, target):
            print("✗ Use failed")
        observe()

    elif cmd in ("help", "--help", "-h"):
        print(__doc__)

    else:
        print(f"Unknown command: {cmd}")
        print("Run: ./claw.py help")
        sys.exit(1)


if __name__ == "__main__":
    main()
