# verify_apple_token_once.py
import json, base64, requests, jwt
from jwt import algorithms

TOKEN = """<вставь id_token>"""
AUD = "com.adconcept.snapai.ios"
ISS = "https://appleid.apple.com"

def b64url(json_bytes):  # helper для красивого принта
    return json.loads(base64.urlsafe_b64decode(json_bytes + "=" * (-len(json_bytes) % 4)))

h,p,_ = TOKEN.split(".")
header = b64url(h)
payload = b64url(p)
print("header:", header)
print("payload.aud:", payload.get("aud"))
print("payload.iss:", payload.get("iss"))

jwks = requests.get(f"{ISS}/auth/keys", timeout=10).json()
key = next((k for k in jwks["keys"] if k["kid"] == header["kid"]), None)
assert key, f"JWKS key not found for kid={header['kid']}"
pub = algorithms.RSAAlgorithm.from_jwk(json.dumps(key))

try:
    claims = jwt.decode(
        TOKEN, key=pub, algorithms=["RS256"],
        audience=AUD, issuer=ISS, leeway=300
    )
    print("OK, claims verified:", claims.keys())
except Exception as e:
    print("DECODE ERROR:", type(e).__name__, str(e))
