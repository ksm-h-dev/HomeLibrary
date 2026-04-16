import http.client
import json

conn = http.client.HTTPConnection("localhost", 8000)
body = json.dumps({"path": "C:\\Book"})
headers = {"Content-Type": "application/json"}
conn.request("POST", "/api/setup/save-path", body=body, headers=headers)
resp = conn.getresponse()
print(f"Status: {resp.status}")
print(f"Body: {resp.read().decode()}")
conn.close()
