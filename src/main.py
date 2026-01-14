import asyncio

import socketio
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import IntPrompt, Prompt
from rich.table import Table

console = Console()
sio = socketio.AsyncClient()

state = {
    "balance": 500,
    "room_code": None,
    "username": "",
    "is_host": False,
    "in_round": False,
    "has_bet": False,
}

ui_state = {
    "players": {},  # name -> {balance, status}
    "logs": [],
    "status": "Lobby",
}


# -------------------------
# Async-safe prompt wrapper
# -------------------------
async def ask_prompt(func, *args, **kwargs):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: func(*args, **kwargs))


# -------------------------
# UI Rendering
# -------------------------
def render_ui():
    layout = Layout()

    header = Panel(
        f"🎰 CLI Roulette | Room: {state['room_code']} | You: {state['username']} | Balance: ${state['balance']}",
        style="bold magenta",
    )

    players_table = Table(title="Players", expand=True)
    players_table.add_column("Name")
    players_table.add_column("Balance")
    players_table.add_column("Status")

    if ui_state["players"]:
        for name, pdata in ui_state["players"].items():
            players_table.add_row(
                name, f"${pdata.get('balance', 0)}", pdata.get("status", "idle")
            )
    else:
        players_table.add_row("(no data)", "-", "-")

    players_panel = Panel(players_table, title="Players")

    status_panel = Panel(ui_state["status"], title="Game Status")

    log_panel = Panel(
        "\n".join(ui_state["logs"][-12:]) or "(no activity yet)", title="Log"
    )

    layout.split_column(
        Layout(header, size=3),
        Layout(name="middle"),
        Layout(log_panel, size=10),
    )

    layout["middle"].split_row(
        Layout(players_panel),
        Layout(status_panel),
    )

    return layout


# -------------------------
# Socket Events
# -------------------------
@sio.event
def notification(data):
    ui_state["logs"].append(f"> {data}")


@sio.event
async def round_start(data):
    state["in_round"] = True
    state["has_bet"] = False
    ui_state["status"] = f"BETTING OPEN ({data['duration']}s)"
    ui_state["logs"].append("Round started")


@sio.event
async def bets_closed():
    ui_state["status"] = "BETTING CLOSED"
    ui_state["logs"].append("Betting closed")


@sio.event
async def spin_result(data):
    with Progress(SpinnerColumn(), TextColumn("Spinning..."), transient=True) as p:
        p.add_task("spin", total=None)
        await asyncio.sleep(2)

    num, color = data["num"], data["color"]
    ui_state["logs"].append(f"Result: {num} {color.upper()}")

    payout = 0
    for r in data["leaderboard"]:
        if r["name"] == state["username"]:
            payout = r["payout"]

    state["balance"] += payout
    state["in_round"] = False
    ui_state["status"] = "Lobby"
    ui_state["logs"].append(f"Your payout: {payout:+}")


# -------------------------
# Game Logic
# -------------------------
async def betting_process():
    if state["has_bet"]:
        return

    amount = await ask_prompt(IntPrompt.ask, "Bet amount (0 to skip)", default=0)

    if amount == 0:
        state["has_bet"] = True
        return

    if amount > state["balance"]:
        ui_state["logs"].append("Insufficient funds")
        return

    bet_type = await ask_prompt(Prompt.ask, "Type", choices=["number", "color"])

    if bet_type == "number":
        choice = await ask_prompt(IntPrompt.ask, "Pick number (0-36)")
        if not 0 <= choice <= 36:
            ui_state["logs"].append("Invalid number")
            return
    else:
        choice = await ask_prompt(Prompt.ask, "Pick color", choices=["red", "black"])

    res = await sio.call(
        "place_bet",
        {
            "code": state["room_code"],
            "bet": {"type": bet_type, "choice": choice, "amount": amount},
        },
    )

    if not isinstance(res, dict):
        ui_state["logs"].append("Invalid response from server")
        return

    if res["success"]:
        ui_state["logs"].append("Bet placed")
        state["has_bet"] = True
    else:
        ui_state["logs"].append(f"Bet failed: {res.get('message', 'unknown')}")


async def game_loop():
    while True:
        if state["is_host"] and not state["in_round"]:
            action = await ask_prompt(
                Prompt.ask,
                "Action",
                choices=["start", "wait", "quit"],
                default="wait",
            )

            if action == "start":
                await sio.emit("start_game", {"code": state["room_code"]})
                ui_state["logs"].append("You started the round")
            elif action == "quit":
                break

        if state["in_round"]:
            await betting_process()

        await asyncio.sleep(0.2)


# -------------------------
# Main
# -------------------------
async def main():
    try:
        await sio.connect("http://localhost:5000")
    except Exception:
        console.print("[red]Server not reachable[/]")
        return

    state["username"] = await ask_prompt(Prompt.ask, "Username")
    action = await ask_prompt(Prompt.ask, "Do you want to", choices=["create", "join"])

    if action == "create":
        res = await sio.call("create_room", {"username": state["username"]})
        if not isinstance(res, dict):
            console.print("[red]Invalid server response[/]")
            return
        state["room_code"] = res["code"]
        state["is_host"] = True
        ui_state["logs"].append(f"Room created: {state['room_code']}")
    else:
        code = await ask_prompt(Prompt.ask, "Room Code")
        res = await sio.call("join_room", {"username": state["username"], "code": code})
        if not isinstance(res, dict) or not res.get("success"):
            console.print("[red]Room not found[/]")
            return
        state["room_code"] = code.upper()
        ui_state["logs"].append(f"Joined room: {state['room_code']}")

    # Fake player list for now (until server sends real updates)
    ui_state["players"] = {
        state["username"]: {"balance": state["balance"], "status": "online"}
    }

    with Live(render_ui(), refresh_per_second=10, screen=True) as live:

        async def ui_refresher():
            while True:
                live.update(render_ui())
                await asyncio.sleep(0.1)

        await asyncio.gather(
            game_loop(),
            ui_refresher(),
        )

    await sio.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
