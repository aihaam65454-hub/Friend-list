from flask import Flask, jsonify
import requests
import json
import time
import urllib3
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from google.protobuf import json_format
import r1_pb2 

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

FREEFIRE_VERSION = "OB52"
FRIEND_URL = "https://clientbp.ggpolarbear.com/GetFriend"

FRIEND_KEY = bytes([89,103,38,116,99,37,68,69,117,104,54,37,90,99,94,56])
FRIEND_IV  = bytes([54,111,121,90,68,114,50,50,69,51,121,99,104,106,77,37])

def encrypt_friend_payload(hex_data: str) -> bytes:
    raw = bytes.fromhex(hex_data)
    cipher = AES.new(FRIEND_KEY, AES.MODE_CBC, FRIEND_IV)
    return cipher.encrypt(pad(raw, AES.block_size))


def api_response(friends_list, my_info):
    return jsonify({
        "friends_count": len(friends_list),
        "friends_list": friends_list,
        "my_info": my_info,
        "Credit": "S1X AMINE",
        "status": "success",
        "timestamp": int(time.time())
    })

@app.route("/")
def home():
    return jsonify({
        "usage": "/<JWT>",
        "status": "online"
    })


@app.route("/<path:jwt>", methods=["GET"])
def friend_list(jwt):

    if not jwt or jwt.count(".") != 2:
        return jsonify({
            "status": "error",
            "message": "Invalid JWT"
        }), 400

    headers = {
        "Expect": "100-continue",
        "Authorization": f"Bearer {jwt}",
        "X-Unity-Version": "2018.4.11f1",
        "X-GA": "v1 1",
        "ReleaseVersion": FREEFIRE_VERSION,
        "Content-Type": "application/octet-stream",
        "User-Agent": "Dalvik/2.1.0 (Linux; Android 11)",
        "Connection": "Keep-Alive",
        "Accept-Encoding": "gzip"
    }

    payload_hex = "080110011001"
    encrypted_payload = encrypt_friend_payload(payload_hex)

    try:
        r = requests.post(
            FRIEND_URL,
            headers=headers,
            data=encrypted_payload,
            timeout=15,
            verify=False
        )

        if r.status_code != 200:
            return jsonify({
                "status": "error",
                "message": "Free Fire server error",
                "code": r.status_code
            }), 502

        pb = r1_pb2.Friends()
        pb.ParseFromString(r.content)

        parsed = json.loads(
            json_format.MessageToJson(pb)
        )

        raw_list = []
        for entry in parsed.get("field1", []):
            uid = str(entry.get("ID", "unknown"))
            name = "unknown"

            for k, v in entry.items():
                if isinstance(v, str) and k != "ID":
                    name = v
                    break

            raw_list.append({
                "uid": uid,
                "name": name
            })

        if not raw_list:
            return api_response([], None)

        my_info = raw_list[-1] 
        friends_list = raw_list[:-1] 

        return api_response(friends_list, my_info)

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": "Friend list failed",
            "details": str(e)
        }), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)