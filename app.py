from flask import Flask, jsonify
import aiohttp
import asyncio
import json
from byte import encrypt_api, Encrypt_ID
from visit_count_pb2 import Info

app = Flask(__name__)

def load_tokens(server_name):
    try:
        if server_name == "IND":
            path = "token_ind.json"
        elif server_name in {"BR", "US", "SAC", "NA"}:
            path = "token_br.json"
        else:
            path = "token_id.json"

        with open(path, "r") as f:
            data = json.load(f)

        tokens = [
            item["token"]
            for item in data
            if "token" in item and item["token"] not in ("", "N/A")
        ]
        return tokens
    except Exception as e:
        app.logger.error(f"Token load error {server_name}: {e}")
        return []

def get_url(server_name):
    if server_name == "IND":
        return "https://client.ind.freefiremobile.com/GetPlayerPersonalShow"
    elif server_name in {"BR", "US", "SAC", "NA"}:
        return "https://client.us.freefiremobile.com/GetPlayerPersonalShow"
    else:
        return "https://clientbp.ggblueshark.com/GetPlayerPersonalShow"

def parse_protobuf_response(response_data):
    try:
        info = Info()
        info.ParseFromString(response_data)

        return {
            "uid": info.AccountInfo.UID or 0,
            "nickname": info.AccountInfo.PlayerNickname or "",
            "likes": info.AccountInfo.Likes or 0,
            "region": info.AccountInfo.PlayerRegion or "",
            "level": info.AccountInfo.Levels or 0
        }
    except Exception as e:
        app.logger.error(f"Protobuf error: {e}")
        return None

async def visit(session, url, token, data):
    headers = {
        "ReleaseVersion": "OB51",
        "X-GA": "v1 1",
        "Authorization": f"Bearer {token}",
        "Host": url.replace("https://", "").split("/")[0]
    }

    try:
        async with session.post(url, headers=headers, data=data, ssl=False) as resp:
            if resp.status == 200:
                return True, await resp.read()
            return False, None
    except Exception:
        return False, None

async def send_until_success(tokens, uid, server, target_success):
    url = get_url(server)
    connector = aiohttp.TCPConnector(limit=0)

    total_success = 0
    total_sent = 0
    player_info = None
    first_response = None

    encrypted = encrypt_api("08" + Encrypt_ID(str(uid)) + "1801")
    data = bytes.fromhex(encrypted)

    async with aiohttp.ClientSession(connector=connector) as session:
        while total_success < target_success:
            batch = min(10000, target_success - total_success)

            tasks = [
                asyncio.create_task(
                    visit(session, url, tokens[(total_sent + i) % len(tokens)], data)
                )
                for i in range(batch)
            ]

            results = await asyncio.gather(*tasks)

            if not first_response:
                for ok, res in results:
                    if ok and res:
                        first_response = res
                        player_info = parse_protobuf_response(res)
                        break

            success_batch = sum(1 for ok, _ in results if ok)
            total_success += success_batch
            total_sent += batch

    return total_success, total_sent, player_info

@app.route("/<string:server>/<int:uid>", methods=["GET"])
def send_visits(server, uid):
    server = server.upper()
    tokens = load_tokens(server)
    target_success = 10000

    if not tokens:
        return jsonify({"error": "No valid tokens"}), 500

    total_success, total_sent, player_info = asyncio.run(
        send_until_success(tokens, uid, server, target_success)
    )

    if not player_info:
        return jsonify({"error": "Player info not found"}), 500

    response = {
        "uid": player_info.get("uid", 0),
        "nickname": player_info.get("nickname", ""),
        "level": player_info.get("level", 0),
        "likes": player_info.get("likes", 0),
        "region": player_info.get("region", ""),
        "success": total_success,
        "fail": target_success - total_success,
        "credit": "@RapzzGege"
    }

    return jsonify(response), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
