import urllib.request
import urllib.parse
import os
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

INVIDIOUS_INSTANCES = [
    "https://invidious.privacyredirect.com",
    "https://inv.tux.pizza",
    "https://invidious.jing.rocks",
    "https://invidious.nerdvpn.de",
    "https://vid.pugices.pt",
    "https://invidious.fdn.fr"
]

def download_via_invidious_proxy(video_id: str, output_path: str):
    for base in INVIDIOUS_INSTANCES:
        # itag=18 is 360p mp4, itag=22 is 720p mp4
        for itag in [22, 18]:
            proxy_url = f"{base}/latest_version?id={video_id}&itag={itag}&local=true"
            print(f"Trying {proxy_url}")
            try:
                req = urllib.request.Request(proxy_url, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
                })
                with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
                    if resp.getcode() == 200:
                        print(f"Success! Found stream on {base} with itag {itag}")
                        # Read 1MB to test
                        chunk = resp.read(1024 * 1024)
                        if chunk:
                            print(f"Downloaded {len(chunk)} bytes. It works!")
                            return True
            except Exception as e:
                print(f"Failed {base} itag={itag}: {str(e)[:100]}")
    return False

if __name__ == "__main__":
    download_via_invidious_proxy("X1ENbQarvM0", "test.mp4")
