"""실습 5 : 토큰에 따라 API 응답이 어떻게 달라지나 (401 vs 403)

먼저 다른 터미널에서 : uvicorn 04_resource_server:app --port 8011
실행: python 05_call_api.py
"""
import httpx

from common import BATCH_JOB, OIDC, login_steps

API = "http://localhost:8011"
alice = login_steps("alice", "alice")[0]["access_token"]      # user 역할
bob = login_steps("bob", "bob")[0]["access_token"]            # user + admin 역할
batch = httpx.post(f"{OIDC}/token", data={"grant_type": "client_credentials",
                   "client_id": BATCH_JOB[0], "client_secret": BATCH_JOB[1]}).json()["access_token"]

# alice 토큰의 가운데(payload)를 admin 으로 바꿔 쳐본다 (서명은 그대로)
import base64, json
h, p, s = alice.split(".")
payload = json.loads(base64.urlsafe_b64decode(p + "=" * (-len(p) % 4)))
payload["realm_access"]["roles"].append("admin")
fake_p = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
forged = f"{h}.{fake_p}.{s}"

cases = [("토큰 없음", None, "/me"), ("토큰 없음", None, "/public"),
         ("alice (user)", alice, "/me"), ("alice (user)", alice, "/admin"),
         ("bob (admin)", bob, "/admin"), ("batch-job (service)", batch, "/me"),
         ("alice 토큰을 admin 으로 위조", forged, "/admin")]
print(f"{'누구':<28}{'경로':<10}{'응답'}")
for who, tok, path in cases:
    r = httpx.get(API + path, headers={"Authorization": f"Bearer {tok}"} if tok else {})
    print(f"{who:<28}{path:<10}{r.status_code} {r.json()}")
