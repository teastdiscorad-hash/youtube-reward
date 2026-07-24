import os
import sys
import json
import urllib.request
import urllib.error

TOKEN = "rnd_MUKzIywFA7WMyP6bS5oTJy30hxOM"
HOME_ENV = os.path.expanduser("~/.env")

# 1. Save token safely to ~/.env if not already present
env_lines = []
if os.path.exists(HOME_ENV):
    with open(HOME_ENV, "r", encoding="utf-8") as f:
        env_lines = f.readlines()

has_key = any(line.startswith("RENDER_API_KEY=") for line in env_lines)
if not has_key:
    with open(HOME_ENV, "a", encoding="utf-8") as f:
        f.write(f"\nRENDER_API_KEY={TOKEN}\n")
    print("Saved RENDER_API_KEY to ~/.env")

# 2. Query Render API
headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/json",
    "Content-Type": "application/json"
}

def api_get(endpoint):
    url = f"https://api.render.com/v1{endpoint}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"HTTPError: {e.code} - {e.read().decode()}")
        return None

owners = api_get("/owners")
print("Owners:", json.dumps(owners, indent=2))

services = api_get("/services")
print("Services:", json.dumps(services, indent=2))
