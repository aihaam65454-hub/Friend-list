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

# مفاتيح التشفير الرسمية
FRIEND_KEY = bytes([89,103,38,116,99,37,68,69,117,104,54,37,90,99,94,56])
FRIEND_IV  = bytes([54,111,121,90,68,114,50,50,69,51,121,99,104,106,77,37])

def encrypt_friend_payload(data_bytes: bytes) -> bytes:
    cipher = AES.new(FRIEND_KEY, AES.MODE_CBC, FRIEND_IV)
    return cipher.encrypt(pad(data_bytes, AES.block_size))

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
        "usage": "/<JWT>/<TARGET_ID>",
        "status": "online"
    })

@app.route("/<path:jwt>/<target_id>", methods=["GET"])
def friend_list(jwt, target_id):
    # التأكد من صحة التوكن
    if not jwt or jwt.count(".") != 2:
        return jsonify({"status": "error", "message": "Invalid JWT"}), 400

    headers = {
        "Expect": "100-continue",
        "Authorization": f"Bearer {jwt}",
        "X-Unity-Version": "2018.4.11f1",
        "ReleaseVersion": FREEFIRE_VERSION,
        "Content-Type": "application/octet-stream",
        "User-Agent": "Dalvik/2.1.0 (Linux; Android 11)",
        "Connection": "Keep-Alive"
    }

    try:
        # --- التعديل الجوهري هنا ---
        # نقوم ببناء طلب البروتوبوف باستخدام ID الشخص المطلوب
        # نفترض أن الحقل الأول هو ID في ملف r1_pb2
        request_pb = r1_pb2.Friends() 
        # ملاحظة: إذا كان اسم الحقل في ملفك ليس ID، قم بتغييره هنا
        try:
            # تحويل الـ ID من الرابط إلى رقم
            target_uid = int(target_id)
            # بناء الـ Payload الرسمي (البيانات الخام)
            # ملاحظة: 0801100112 هي البادئة الثابتة لطلبات الأصدقاء في النسخ الحالية
            # ثم يتبعها طول الـ ID والـ ID نفسه بصيغة Varint
            payload_hex = "0801100112"
            
            # طريقة ذكية لتحويل الـ ID لـ Hex يقبله السيرفر
            def to_varint(n):
                res = []
                while n > 127:
                    res.append((n & 0x7f) | 0x80)
                    n >>= 7
                res.append(n)
                return bytes(res)
            
            uid_varint = to_varint(target_uid)
            full_payload = bytes.fromhex(payload_hex) + bytes([len(uid_varint)]) + uid_varint
            
            # تشفير البيانات النهائية
            encrypted_payload = encrypt_friend_payload(full_payload)
            
        except ValueError:
            return jsonify({"status": "error", "message": "Target ID must be a number"}), 400

        # إرسال الطلب للسيرفر
        r = requests.post(
            FRIEND_URL,
            headers=headers,
            data=encrypted_payload,
            timeout=15,
            verify=False
        )

        if r.status_code != 200:
            return jsonify({"status": "error", "message": "Free Fire server error", "code": r.status_code}), 502

        # فك تشفير النتيجة القادمة من السيرفر
        pb = r1_pb2.Friends()
        pb.ParseFromString(r.content)
        parsed = json.loads(json_format.MessageToJson(pb))

        raw_list = []
        for entry in parsed.get("field1", []):
            uid = str(entry.get("ID", "unknown"))
            name = "unknown"
            for k, v in entry.items():
                if isinstance(v, str) and k != "ID":
                    name = v
                    break
            raw_list.append({"uid": uid, "name": name})

        if not raw_list:
            return api_response([], None)

        # في حال جلب أصدقاء شخص آخر، الحساب المطلوب يكون هو آخر عنصر غالباً
        my_info = raw_list[-1] 
        friends_list = raw_list[:-1] 

        return api_response(friends_list, my_info)

    except Exception as e:
        return jsonify({"status": "error", "message": "Request failed", "details": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
