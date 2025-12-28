from flask import Flask, jsonify
import aiohttp
import asyncio
import json
from byte import encrypt_api, Encrypt_ID
from visit_count_pb2 import Info

app = Flask(__name__)

def load_tokens(server):
    try:
        if server == "IND":
            path = "token_ind.json"
        elif server in {"BR", "US", "SAC", "NA"}:
            path = "token_br.json"
        else:
            path = "token_id.json"

        with open(path) as f:
            data = json.load(f)

        return [i["token"] for i in data if i.get("token")]
    except:
        return []

def get_url(server):
    if server == "IND":
        return "https://client.ind.freefiremobile.com/GetPlayerPersonalShow"
    elif server in {"BR", "US", "SAC", "NA"}:
        return "https://client.us.freefiremobile.com/GetPlayerPersonalShow"
    return "https://clientbp.ggblueshark.com/GetPlayerPersonalShow"

def parse_player(res):
    try:
        info = Info()
        info.ParseFromString(res)
        return {
            "uid": info.AccountInfo.UID or 0,
            "nickname": info.AccountInfo.PlayerNickname or "",
            "likes": info.AccountInfo.Likes or 0,
            "region": info.AccountInfo.PlayerRegion or "",
            "level": info.AccountInfo.Levels or 0
        }
    except:
        return None

async def visit(session, url, token, data):
    headers = {
        "ReleaseVersion": "OB51",
        "Authorization": f"Bearer {token}",
        "Host": url.split("//")[1].split("/")[0]
    }
    try:
        async with session.post(url, headers=headers, data=data, ssl=False) as r:
            if r.status == 200:
                return True, await r.read()
    except:
        pass
    return False, None

async def run(tokens, uid, server, target):
    url = get_url(server)
    success = 0
    sent = 0
    player = None

    payload = bytes.fromhex(
        encrypt_api("08" + Encrypt_ID(str(uid)) + "1801")
    )

    async with aiohttp.ClientSession() as session:
        while success < target:
            tasks = [
                asyncio.create_task(
                    visit(session, url, tokens[(sent + i) % len(tokens)], payload)
                )
                for i in range(target - success)
            ]

            results = await asyncio.gather(*tasks)

            for ok, res in results:
                if ok:
                    success += 1
                    if not player and res:
                        player = parse_player(res)
            sent += len(tasks)

    return success, sent, player

@app.route("/<string:server>/<int:uid>")
def main(server, uid):
    server = server.upper()
    tokens = load_tokens(server)
    target = 4

    if not tokens:
        return jsonify({"error": "token kosong"}), 500

    success, sent, player = asyncio.run(
        run(tokens, uid, server, target)
    )

    if not player:
        return jsonify({"error": "player not found"}), 500

    return jsonify({
        "uid": player.get("uid", 0),
        "nickname": player.get("nickname", ""),
        "level": player.get("level", 0),
        "likes": player.get("likes", 0),
        "region": player.get("region", ""),
        "success": success,
        "fail": target - success,
        "credit": "@RapzzGege"
    }), 200

if __name__ == "__main__":
    app.run()
