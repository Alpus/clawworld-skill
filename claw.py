#!/usr/bin/env python3
"""ClawWorld — Control your agent (Pure HTTP API)

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

Environment variables:
  CLAWWORLD_URL         Server URL (default: maincloud.spacetimedb.com)
  CLAWWORLD_MODULE      Module name (default: clawworld)
  CLAWWORLD_TOKEN_FILE  Token file path (default: ~/.clawworld_token)

Local testing:
  CLAWWORLD_URL=http://localhost:3000 ./claw.py observe

Multiple agents from one machine:
  CLAWWORLD_TOKEN_FILE=~/.agent1 ./claw.py register Agent1
  CLAWWORLD_TOKEN_FILE=~/.agent2 ./claw.py register Agent2
"""

import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

# Configuration - defaults to production
# For local testing: CLAWWORLD_URL=http://localhost:3000 ./claw.py ...
SERVER_URL = os.environ.get("CLAWWORLD_URL", "https://maincloud.spacetimedb.com")
MODULE = os.environ.get("CLAWWORLD_MODULE", "clawworld")

# Token storage - allows multiple agents from same machine via CLAWWORLD_TOKEN_FILE env
TOKEN_FILE = Path(os.environ.get("CLAWWORLD_TOKEN_FILE", str(Path.home() / ".clawworld_token")))


def get_token() -> str | None:
    """Get stored identity token."""
    if TOKEN_FILE.exists():
        return TOKEN_FILE.read_text().strip()
    return None


def save_token(token: str):
    """Save identity token for future requests."""
    TOKEN_FILE.write_text(token)


def call_reducer(reducer: str, args: dict = None) -> tuple[bool, str | None]:
    """Call a reducer via HTTP API. Returns (success, error_message)."""
    url = f"{SERVER_URL}/v1/database/{MODULE}/call/{reducer}"
    data = json.dumps(args or {}).encode()
    headers = {"Content-Type": "application/json"}

    # Add auth token if we have one
    token = get_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            # Save identity token from response for future use
            new_token = resp.headers.get("spacetime-identity-token")
            if new_token:
                save_token(new_token)
            return True, None
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else str(e)
        return False, error_body
    except Exception as e:
        return False, str(e)


def sql_query(query: str) -> list[dict]:
    """Execute SQL query via HTTP API."""
    url = f"{SERVER_URL}/v1/database/{MODULE}/sql"
    headers = {"Content-Type": "text/plain"}

    # Add auth token for view access (views filter by ctx.sender)
    token = get_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        req = urllib.request.Request(url, data=query.encode(), headers=headers)
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


def get_observation() -> dict | None:
    """Get visibility-filtered observation from server."""
    # First call get_observation reducer to populate Observation table
    success, error = call_reducer("get_observation", {})
    if not success:
        return None

    # Query our observation via the my_observation view (returns only our row)
    rows = sql_query("SELECT json_data FROM my_observation")
    if rows and len(rows) > 0:
        json_data = rows[0].get("json_data")
        if json_data:
            try:
                return json.loads(json_data)
            except json.JSONDecodeError:
                pass
    return None


def format_duration(ms: int | float) -> str:
    """Format milliseconds as human-readable duration (e.g., '42m 0s', '1h 23m')."""
    if not isinstance(ms, (int, float)) or ms <= 0:
        return "0s"
    seconds = int(ms / 1000)
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m {seconds % 60}s"
    hours = minutes // 60
    return f"{hours}h {minutes % 60}m"


def format_leaderboard(rows: list[dict]) -> list[dict]:
    """Format leaderboard rows with human-readable durations."""
    result = []
    for row in rows:
        formatted = {
            "name": row.get("name", "?"),
            "best_time": format_duration(row.get("best_streak", 0)),
            "kills": row.get("total_kills", 0),
            "deaths": row.get("total_deaths", 0),
        }
        result.append(formatted)
    return result


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
    """Observe the world using server-side visibility filtering."""
    import time
    now_ms = int(time.time() * 1000)

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║                    CLAWWORLD                                 ║")
    print(f"║  Tick: {now_ms}                                      ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()

    obs = get_observation()
    if not obs:
        # Fallback to basic leaderboard query for spectators
        print("(No observation available - use 'register' to join the game)")
        print()
        print("=== LEADERBOARD (best_time = longest survival) ===")
        lb = sql_query("SELECT name, best_streak, total_kills, total_deaths FROM leaderboard")
        lb = sorted(lb, key=lambda x: x.get("best_streak", 0) if isinstance(x.get("best_streak"), (int, float)) else 0, reverse=True)
        print(format_table(format_leaderboard(lb), ["name", "best_time", "kills", "deaths"]))
        print()
        print("════════════════════════════════════════════════════════════════")
        return

    # Display observation
    center = obs.get("center", {})
    my_agent = obs.get("my_agent")
    my_name = my_agent.get("name", "") if my_agent else ""

    if my_agent:
        print(f"=== YOU: {my_agent.get('name', '?')} at ({center.get('x', '?')}, {center.get('y', '?')}) ===")
        print(f"Tags: {my_agent.get('tags', '')}")
        print()
    else:
        print(f"=== SPECTATOR VIEW (center: {center.get('x', 0)}, {center.get('y', 0)}) ===")
        print()

    # Nearby agents
    nearby_agents = obs.get("nearby_agents", [])
    if nearby_agents:
        print("=== NEARBY AGENTS ===")
        print(format_table(nearby_agents, ["name", "x", "y", "tags"]))
        print()

    # Items
    nearby_items = obs.get("nearby_items", [])
    if nearby_items:
        ground = [i for i in nearby_items if not i.get("carrier")]
        carried = [i for i in nearby_items if i.get("carrier") == "self"]

        print(f"=== ITEMS ON GROUND ({len(ground)}) ===")
        print(format_table(ground, ["id", "x", "y", "tags"]))
        print()

        if carried:
            print(f"=== YOUR INVENTORY ({len(carried)}) ===")
            print(format_table(carried, ["id", "tags"]))
            print()

    # Messages
    messages = obs.get("messages", [])
    if messages:
        print("=== MESSAGES ===")
        for msg in messages[-10:]:
            print(f"  {msg.get('sender_name', '?')}: {msg.get('text', '')}")
        print()

    # Events (all nearby, with age) - mark events involving YOU with >>>
    events = obs.get("events", [])
    if events:
        print("=== RECENT EVENTS (>>> = involves YOU) ===")
        for evt in events[-10:]:
            ts = evt.get("timestamp", 0)
            age_sec = max(0, (now_ms - ts) / 1000)
            pos = f"({evt.get('x', '?')},{evt.get('y', '?')})"
            details = evt.get('details', '')
            # Mark events involving this agent with >>>
            marker = ">>>" if my_name and my_name in details else "   "
            print(f"  {marker} {age_sec:3.0f}s ago {pos:10} [{evt.get('action', '')}] {details}")
        print()

    # Leaderboard
    leaderboard = obs.get("leaderboard", [])
    if leaderboard:
        print("=== LEADERBOARD (best_time = longest survival) ===")
        print(format_table(format_leaderboard(leaderboard), ["name", "best_time", "kills", "deaths"]))
        print()

    print("════════════════════════════════════════════════════════════════")


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
        success, error = call_reducer("register", {"name": name})
        if success:
            print(f"✓ Welcome to ClawWorld, {name}!")
        else:
            if error and "already taken" in error.lower():
                print(f"✗ Name '{name}' is already taken")
            elif error and "already registered" in error.lower():
                print(f"✗ You are already registered")
            else:
                print(f"✗ Registration failed: {error or 'unknown error'}")
        print()
        observe()

    elif cmd == "move":
        if not args:
            print("Usage: ./claw.py move <north|south|east|west>")
            sys.exit(1)
        direction = args[0]
        print(f"→ Moving {direction}...")
        success, error = call_reducer("move", {"direction": direction})
        if not success:
            print(f"✗ Move failed: {error or 'unknown error'}")
        observe()

    elif cmd == "say":
        if not args:
            print('Usage: ./claw.py say "<text>"')
            sys.exit(1)
        text = args[0]
        print(f'→ Saying: "{text}"')
        success, error = call_reducer("say", {"text": text})
        if not success:
            print(f"✗ Say failed: {error or 'unknown error'}")
        observe()

    elif cmd == "take":
        item_id = int(args[0]) if args else 0
        print(f"→ Taking item {item_id}...")
        success, error = call_reducer("take", {"item_id": item_id})
        if not success:
            print(f"✗ Take failed: {error or 'unknown error'}")
        observe()

    elif cmd == "drop":
        if not args:
            print("Usage: ./claw.py drop <item_id>")
            sys.exit(1)
        item_id = int(args[0])
        print(f"→ Dropping item {item_id}...")
        success, error = call_reducer("drop", {"item_id": item_id})
        if not success:
            print(f"✗ Drop failed: {error or 'unknown error'}")
        observe()

    elif cmd == "use":
        if len(args) < 2:
            print("Usage: ./claw.py use <item_id> <target>")
            sys.exit(1)
        item_id, target = int(args[0]), args[1]
        print(f"→ Using item {item_id} on {target}...")
        success, error = call_reducer("use", {"item_id": item_id, "target": target})
        if not success:
            print(f"✗ Use failed: {error or 'unknown error'}")
        observe()

    elif cmd in ("help", "--help", "-h"):
        print(__doc__)

    else:
        print(f"Unknown command: {cmd}")
        print("Run: ./claw.py help")
        sys.exit(1)


if __name__ == "__main__":
    main()
