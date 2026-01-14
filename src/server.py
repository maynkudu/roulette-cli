import asyncio
import random
import string

import socketio
from aiohttp import web

from game_logic import RouletteEngine

sio = socketio.AsyncServer(async_mode="aiohttp", cors_allowed_origins="*")
app = web.Application()
sio.attach(app)

engine = RouletteEngine()
rooms = {}


async def run_game_cycle(code):
    room = rooms.get(code)
    if not room:
        return

    room["status"] = "betting"
    await sio.emit("round_start", {"duration": 30}, room=code)

    await asyncio.sleep(30)

    room["status"] = "spinning"
    await sio.emit("bets_closed", room=code)

    win_num, win_color = engine.spin()

    results = []
    for sid, bet in room["bets"].items():
        name = room["players"].get(sid, "Unknown")
        payout = engine.calculate_payout(
            bet["type"], bet["choice"], bet["amount"], win_num, win_color
        )
        results.append(
            {
                "name": name,
                "bet": bet["amount"],
                "type": bet["type"],
                "choice": bet["choice"],
                "payout": payout,
            }
        )

    await sio.emit(
        "spin_result",
        {"num": win_num, "color": win_color, "leaderboard": results},
        room=code,
    )

    room["bets"] = {}
    room["status"] = "lobby"
    room["task"] = None


@sio.event
async def create_room(sid, data):
    code = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    rooms[code] = {
        "host": sid,
        "players": {sid: data["username"]},
        "bets": {},
        "status": "lobby",
        "task": None,
    }
    await sio.enter_room(sid, code)
    return {"code": code}


@sio.event
async def join_room(sid, data):
    code = data["code"].upper()
    room = rooms.get(code)

    if not room:
        return {"success": False}

    await sio.enter_room(sid, code)
    room["players"][sid] = data["username"]

    await sio.emit("notification", f"{data['username']} joined", room=code)
    return {"success": True}


@sio.event
async def start_game(sid, data):
    code = data["code"]
    room = rooms.get(code)

    if not room or room["host"] != sid:
        return

    if room["status"] != "lobby" or room["task"]:
        return

    room["task"] = asyncio.create_task(run_game_cycle(code))


@sio.event
async def place_bet(sid, data):
    code = data["code"]
    room = rooms.get(code)

    if not room or room["status"] != "betting":
        return {"success": False, "message": "Betting closed"}

    room["bets"][sid] = data["bet"]

    await sio.emit("notification", f"{room['players'][sid]} placed a bet", room=code)
    return {"success": True}


if __name__ == "__main__":
    print("🚀 Server running on :5000")
    web.run_app(app, port=5000)
