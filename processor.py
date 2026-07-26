import os
import re
import subprocess
import logging
import json
import urllib.request
import urllib.parse
import urllib.error
import yt_dlp
import traceback
from proxy_manager import proxy_manager
try:
    from pytubefix import YouTube
    PYTUBEFIX_AVAILABLE = True
except ImportError:
    PYTUBEFIX_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("processor")

MOBILE_USER_AGENTS = [
    'Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1'
]

def find_cookie_file() -> str:
    possible_paths = [
        os.path.join(os.path.dirname(__file__), "cookies.txt"),
        os.path.join(os.getcwd(), "cookies.txt"),
    ]
    for p in possible_paths:
        if os.path.isfile(p) and os.path.getsize(p) > 0:
            return p
    return None

def extract_youtube_id(url: str) -> str:
    match = re.search(r'(?:v=|\/|be\/|shorts\/)([a-zA-Z0-9_-]{11})', url)
    return match.group(1) if match else None

def _http_get_json(url: str, timeout: int = 10) -> dict:
    req = urllib.request.Request(url, headers={
        'User-Agent': MOBILE_USER_AGENTS[0],
        'Accept': 'application/json'
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode('utf-8'))

def get_video_info(youtube_url: str):
    """
    جلب معلومات المقطع بسرعة وبأعلى دقة
    """
    video_id = extract_youtube_id(youtube_url)

    # 1. YouTube oEmbed الرسمية (سرعة خاطفة)
    try:
        oembed_url = f"https://www.youtube.com/oembed?url={urllib.parse.quote(youtube_url)}&format=json"
        data = _http_get_json(oembed_url, timeout=5)
        thumb = data.get('thumbnail_url') or (f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg" if video_id else "")
        return {
            'id': video_id or "youtube_video",
            'title': data.get('title', 'مقطع يوتيوب'),
            'duration': 90,
            'duration_string': 'مقطع يوتيوب',
            'thumbnail': thumb
        }
    except Exception as e:
        logger.warning(f"oEmbed failed: {e}")

    # 2. Pytubefix (حل جذري ومضمون لجلب المعلومات متجاوزاً حماية البوتات)
    if PYTUBEFIX_AVAILABLE:
        try:
            from pytubefix import YouTube
            yt = YouTube(youtube_url, client='WEB')
            return {
                'id': video_id or "youtube_video",
                'title': yt.title,
                'duration': yt.length,
                'duration_string': f"{int(yt.length // 60)} دقيقة و {int(yt.length % 60)} ثانية" if yt.length else "غير محدد",
                'thumbnail': yt.thumbnail_url or (f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg" if video_id else "")
            }
        except Exception as e:
            logger.warning(f"pytubefix info failed: {e}")

    # 3. yt-dlp عبر android_vr client
    cookie_path = find_cookie_file()
    for client in [['android_vr'], ['android_creator'], ['tv_embedded']]:
        try:
            ydl_opts = {
                'quiet': True, 'no_warnings': True, 'socket_timeout': 15,
                'extractor_args': {'youtube': {'player_client': client}},
                'http_headers': {'User-Agent': MOBILE_USER_AGENTS[0]}
            }
            if cookie_path:
                ydl_opts['cookiefile'] = cookie_path
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(youtube_url, download=False)
                dur = info.get('duration') or 0
                return {
                    'id': info.get('id') or video_id,
                    'title': info.get('title') or 'مقطع يوتيوب',
                    'duration': dur,
                    'duration_string': f"{int(dur // 60)} دقيقة و {int(dur % 60)} ثانية" if dur else "غير محدد",
                    'thumbnail': info.get('thumbnail') or f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
                }
        except Exception as err:
            logger.warning(f"yt-dlp info ({client}): {err}")

    # Fallback
    return {
        'id': video_id or "unknown",
        'title': "مقطع فيديو جاهز للدمج",
        'duration': 90,
        'duration_string': "مقطع فيديو",
        'thumbnail': f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg" if video_id else ""
    }

def fetch_via_gendownload(youtube_url: str, status_callback=None):
    if status_callback: status_callback("🚀 [طبقة GenDownload API] جاري استخراج روابط التحميل المباشرة...")
    logger.info("Trying GenDownload API fallback...")
    try:
        payload = json.dumps({"url": youtube_url}).encode('utf-8')
        req = urllib.request.Request(
            "https://gendownload.com/api/extract",
            data=payload,
            headers={
                'Content-Type': 'application/json',
                'User-Agent': MOBILE_USER_AGENTS[0],
                'Accept': 'application/json'
            }
        )
        with urllib.request.urlopen(req, timeout=4) as resp:
            res = json.loads(resp.read().decode('utf-8'))
            formats = res.get('formats', [])
            best_url = None
            if isinstance(formats, list):
                for fmt in formats:
                    if isinstance(fmt, dict) and fmt.get('url'):
                        quality = str(fmt.get('quality', ''))
                        if '720' in quality or '1080' in quality or 'hd' in quality.lower():
                            return fmt.get('url')
                        if not best_url:
                            best_url = fmt.get('url')
            return best_url
    except Exception as e:
        logger.warning(f"GenDownload fallback failed: {e}")
    return None

def fetch_via_ahm7xmakki(youtube_url: str, status_callback=None):
    if status_callback: status_callback("⚡ [طبقة AHM7xMakki API] جاري فحص الرابط وجلب الوسائط...")
    logger.info("Trying AHM7xMakki API fallback...")
    try:
        url = f"https://ahm7xmakki.com/api/alldl?url={urllib.parse.quote(youtube_url)}"
        req = urllib.request.Request(url, headers={
            'User-Agent': MOBILE_USER_AGENTS[0],
            'Accept': 'application/json'
        })
        with urllib.request.urlopen(req, timeout=4) as resp:
            res = json.loads(resp.read().decode('utf-8'))
            if res.get('success'):
                media_info = res.get('mediaInfo', {})
                video_url = media_info.get('videoUrl')
                if video_url:
                    return video_url
                qualities = media_info.get('qualities', [])
                if isinstance(qualities, list):
                    for q in qualities:
                        if isinstance(q, dict) and q.get('url'):
                            return q.get('url')
                        elif isinstance(q, str) and q.startswith('http'):
                            return q
    except Exception as e:
        logger.warning(f"AHM7xMakki fallback failed: {e}")
    return None

def fetch_via_piped(youtube_url: str, status_callback=None):
    if status_callback: status_callback("🌐 [طبقة Piped API] جاري تجربة خوادم Piped الخارجية...")
    logger.info("Trying Piped API fallback...")
    video_id = extract_youtube_id(youtube_url)
    PIPED_INSTANCES = [
        "https://pipedapi.kavin.rocks",
        "https://pipedapi.tokhmi.xyz",
        "https://pipedapi.adminforge.de",
        "https://api.piped.privacydev.net"
    ]
    for base in PIPED_INSTANCES:
        try:
            url = f"{base}/streams/{video_id}"
            req = urllib.request.Request(url, headers={'User-Agent': MOBILE_USER_AGENTS[0]})
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                streams = data.get('videoStreams', [])
                best_stream = None
                for stream in streams:
                    if not stream.get('videoOnly', True):
                        best_stream = stream
                        if stream.get('quality') in ['1080p', '720p', '480p']:
                            break
                if best_stream and best_stream.get('url'):
                    return best_stream.get('url')
        except Exception as e:
            logger.warning(f"Piped API {base} failed: {e}")
    return None

def fetch_via_cobalt_dynamic(youtube_url: str, status_callback=None):
    if status_callback: status_callback("🛠️ [طبقة Cobalt API] جاري فحص خوادم Cobalt الديناميكية...")
    logger.info("Trying Dynamic Cobalt fallback...")
    instances = []
    try:
        req = urllib.request.Request("https://cobalt-api.kwiatekmateusz.com/instances", headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            for inst in data:
                if inst.get('api_online') and inst.get('trust', 0) > 0.7:
                    if 'url' in inst:
                        instances.append(inst['url'])
    except Exception as e:
        logger.warning(f"Failed to fetch Cobalt instances: {e}")
        instances = ["https://api.cobalt.tools", "https://cobalt.cachyos.org", "https://co.wuk.sh"]

    for base in instances:
        try:
            payload = json.dumps({"url": youtube_url, "videoQuality": "1080"}).encode('utf-8')
            req = urllib.request.Request(
                f"{base}/api/json",
                data=payload,
                headers={'Accept': 'application/json', 'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'}
            )
            with urllib.request.urlopen(req, timeout=4) as resp:
                res = json.loads(resp.read().decode('utf-8'))
                if res.get('status') in ['stream', 'redirect']:
                    return res.get('url')
        except Exception as e:
            logger.warning(f"Cobalt instance {base} failed: {e}")
    return None

def fetch_via_yt1s(youtube_url: str, status_callback=None):
    if status_callback: status_callback("🔄 [طبقة yt1s] جاري استخراج رابط التحميل...")
    logger.info("Trying yt1s.com fallback...")
    try:
        search_data = urllib.parse.urlencode({'q': youtube_url, 'vt': 'home'}).encode('utf-8')
        req = urllib.request.Request("https://yt1s.com/api/ajaxSearch/index", data=search_data, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Accept': '*/*',
            'Origin': 'https://yt1s.com',
            'Referer': 'https://yt1s.com/en361',
            'Accept-Language': 'en-US,en;q=0.9'
        })
        with urllib.request.urlopen(req, timeout=4) as resp:
            res = json.loads(resp.read().decode('utf-8'))
            if res.get('status') == 'ok':
                vid = res.get('vid')
                links = res.get('links', {}).get('mp4', {})
                k_val = None
                for quality in ['137', '136', 'auto', '18']:
                    if quality in links:
                        k_val = links[quality].get('k')
                        break
                if not k_val and links:
                    k_val = list(links.values())[0].get('k')
                
                if vid and k_val:
                    conv_data = urllib.parse.urlencode({'vid': vid, 'k': k_val}).encode('utf-8')
                    req_conv = urllib.request.Request("https://yt1s.com/api/ajaxConvert/convert", data=conv_data, headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
                        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                        'Accept': '*/*',
                        'Origin': 'https://yt1s.com',
                        'Referer': 'https://yt1s.com/en361',
                        'Accept-Language': 'en-US,en;q=0.9'
                    })
                    with urllib.request.urlopen(req_conv, timeout=6) as conv_resp:
                        conv_res = json.loads(conv_resp.read().decode('utf-8'))
                        dlink = conv_res.get('dlink')
                        if dlink:
                            return dlink
    except Exception as e:
        logger.warning(f"yt1s fallback failed: {e}")
    return None

def fetch_via_y2mate(youtube_url: str, status_callback=None):
    if status_callback: status_callback("🎬 [طبقة y2mate] جاري التحقق من السيرفر...")
    logger.info("Trying y2mate.com fallback...")
    try:
        search_data = urllib.parse.urlencode({'k_query': youtube_url, 'q_auto': 1, 'ajax': 1}).encode('utf-8')
        req = urllib.request.Request("https://www.y2mate.com/mates/analyzeV2/ajax", data=search_data, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Accept': '*/*',
            'Origin': 'https://www.y2mate.com',
            'Referer': 'https://www.y2mate.com/en885',
            'Accept-Language': 'en-US,en;q=0.9'
        })
        with urllib.request.urlopen(req, timeout=4) as resp:
            res = json.loads(resp.read().decode('utf-8'))
            if res.get('status') == 'ok':
                vid = res.get('vid')
                links = res.get('links', {}).get('mp4', {})
                k_val = None
                for quality in ['auto', '137', '136', '18']:
                    if quality in links:
                        k_val = links[quality].get('k')
                        break
                if not k_val and links:
                    k_val = list(links.values())[0].get('k')
                
                if vid and k_val:
                    conv_data = urllib.parse.urlencode({'vid': vid, 'k': k_val}).encode('utf-8')
                    req_conv = urllib.request.Request("https://www.y2mate.com/mates/convertV2/index", data=conv_data, headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
                        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                        'Accept': '*/*',
                        'Origin': 'https://www.y2mate.com',
                        'Referer': 'https://www.y2mate.com/en885',
                        'Accept-Language': 'en-US,en;q=0.9'
                    })
                    with urllib.request.urlopen(req_conv, timeout=6) as conv_resp:
                        conv_res = json.loads(conv_resp.read().decode('utf-8'))
                        dlink = conv_res.get('dlink')
                        if dlink:
                            return dlink
    except Exception as e:
        logger.warning(f"y2mate fallback failed: {e}")
    return None

def download_youtube_media(youtube_url: str, output_dir: str, task_id: str, status_callback=None):
    """
    تحميل فيديو يوتيوب بتقنيات متعددة وطبقات ذكية متدرجة وفائقة السرعة
    """
    os.makedirs(output_dir, exist_ok=True)
    final_mp4 = os.path.join(output_dir, f"{task_id}_raw.mp4")
    out_template = os.path.join(output_dir, f"{task_id}_raw.%(ext)s")
    cookie_path = find_cookie_file()
    video_id = extract_youtube_id(youtube_url)

    # 1. طبقة الـ Web APIs السريعة والمباشرة (GenDownload, AHM7xMakki, Cobalt, Piped, yt1s, y2mate)
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    web_fetchers = [
        ("GenDownload API", fetch_via_gendownload),
        ("AHM7xMakki API", fetch_via_ahm7xmakki),
        ("Cobalt API", fetch_via_cobalt_dynamic),
        ("Piped API", fetch_via_piped),
        ("yt1s", fetch_via_yt1s),
        ("y2mate", fetch_via_y2mate)
    ]

    for name, fetcher in web_fetchers:
        try:
            dlink = fetcher(youtube_url, status_callback=status_callback)
            if dlink:
                if status_callback: status_callback(f"⚡ [سريع] جاري تحميل الفيديو فورا من {name}...")
                logger.info(f"Downloading from web API fallback {name}: {dlink[:50]}...")
                req_dl = urllib.request.Request(dlink, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
                with urllib.request.urlopen(req_dl, timeout=10, context=ctx) as r:
                    with open(final_mp4, 'wb') as f:
                        while True:
                            chunk = r.read(16384)
                            if not chunk: break
                            f.write(chunk)
                if os.path.exists(final_mp4) and os.path.getsize(final_mp4) > 100000:
                    logger.info(f"SUCCESS download via Web API {name}")
                    if status_callback: status_callback(f"✅ تم تحميل الفيديو بنجاح من {name}!")
                    return final_mp4, get_video_info(youtube_url)
        except Exception as e:
            logger.warning(f"Failed to download from web API {name}: {e}")

    # 2. طبقة Invidious Proxy (سريعة جدا بمهلة 3 ثواني فقط لتجنب الانتظار)
    INVIDIOUS_INSTANCES = [
        "https://inv.tux.pizza",
        "https://invidious.privacyredirect.com",
        "https://inv.nadeko.net"
    ]
    
    if video_id:
        import socket
        old_getaddrinfo = socket.getaddrinfo
        def new_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
            return old_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
        socket.getaddrinfo = new_getaddrinfo

        if status_callback: status_callback("🌐 [طبقة Invidious] جاري تجربة السحب المباشر السريع...")
        try:
            for base in INVIDIOUS_INSTANCES:
                proxy_url = f"{base}/latest_version?id={video_id}&itag=18&local=true"
                logger.info(f"Trying Invidious proxy: {proxy_url}")
                try:
                    req = urllib.request.Request(proxy_url, headers={'User-Agent': MOBILE_USER_AGENTS[0]})
                    with urllib.request.urlopen(req, timeout=4, context=ctx) as resp:
                        if resp.getcode() == 200:
                            if status_callback: status_callback(f"📥 جاري التحميل من {base.split('//')[-1]}...")
                            with open(final_mp4, 'wb') as f:
                                while True:
                                    chunk = resp.read(16384)
                                    if not chunk: break
                                    f.write(chunk)
                            if os.path.exists(final_mp4) and os.path.getsize(final_mp4) > 100000:
                                logger.info(f"SUCCESS download via Invidious proxy {base}")
                                socket.getaddrinfo = old_getaddrinfo
                                if status_callback: status_callback("✅ تم التحميل بنجاح عبر Invidious!")
                                return final_mp4, get_video_info(youtube_url)
                except Exception as e:
                    logger.warning(f"Failed Invidious proxy {base}: {e}")
        finally:
            socket.getaddrinfo = old_getaddrinfo

    # 3. طبقة Pytubefix (حل ذكي ومضمون جداً مع دعم البروكسيات)
    if PYTUBEFIX_AVAILABLE:
        for attempt in range(3):
            try:
                current_proxy = proxy_manager.get_proxy()
                proxies = None
                if current_proxy:
                    proxy_url = current_proxy if current_proxy.startswith('http') else f"http://{current_proxy}"
                    proxies = {'http': proxy_url, 'https': proxy_url}
                    
                if status_callback: status_callback(f"🛡️ [طبقة Pytubefix] جاري المحاولة {attempt+1}/3 عبر البروكسي: {current_proxy or 'مباشر'}...")
                logger.info(f"Trying pytubefix fallback (client WEB)... Attempt {attempt+1}, Proxy: {current_proxy}")
                from pytubefix import YouTube
                yt = YouTube(youtube_url, client='WEB', proxies=proxies)
                v_stream = yt.streams.filter(type='video', file_extension='mp4').order_by('resolution').desc().first()
                a_stream = yt.streams.filter(type='audio').order_by('abr').desc().first()
                
                if v_stream and a_stream:
                    if status_callback: status_callback("📥 جاري دمج مسارات الفيديو والصوت بشكل منفصل بواسطة Pytubefix...")
                    logger.info(f"Downloading with pytubefix video/audio separately...")
                    v_path = v_stream.download(output_path=os.path.dirname(final_mp4), filename=f"{task_id}_v.mp4")
                    a_path = a_stream.download(output_path=os.path.dirname(final_mp4), filename=f"{task_id}_a.mp4")
                    
                    # Merge using ffmpeg
                    import subprocess
                    cmd = ['ffmpeg', '-y', '-i', v_path, '-i', a_path, '-c:v', 'copy', '-c:a', 'aac', final_mp4]
                    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    
                    # Cleanup temp files
                    if os.path.exists(v_path): os.remove(v_path)
                    if os.path.exists(a_path): os.remove(a_path)
                    
                    if os.path.exists(final_mp4) and os.path.getsize(final_mp4) > 100000:
                        logger.info("SUCCESS download via pytubefix")
                        if status_callback: status_callback("✅ تم تحميل ودمج المقطع بنجاح عبر Pytubefix!")
                        return final_mp4, get_video_info(youtube_url)
            except Exception as e:
                logger.warning(f"Pytubefix fallback failed with proxy {current_proxy}: {e}")
                if current_proxy and ("Sign in" in str(e) or "bot" in str(e).lower() or "timeout" in str(e).lower() or "HTTP Error 429" in str(e)):
                    proxy_manager.remove_proxy(current_proxy)

    # 4. طبقة yt-dlp مع عملاء اللاعبين المضمونة ومع دعم البروكسيات
    bulletproof_clients = [
        ['android_vr'],
        ['android_creator'],
        ['tv_embedded'],
        ['android']
    ]

    last_exception = None
    max_proxy_retries = 10
    client_idx = 0
    
    for attempt in range(max_proxy_retries):
        current_proxy = proxy_manager.get_proxy()
        client_list = bulletproof_clients[client_idx % len(bulletproof_clients)]
        client_idx += 1
        
        try:
            if status_callback: status_callback(f"🔁 [طبقة yt-dlp البروكسيات] المحاولة {attempt+1}/{max_proxy_retries} عبر البروكسي ({current_proxy or 'مباشر'})...")
            logger.info(f"Trying yt-dlp with client: {client_list} (Attempt {attempt+1}/{max_proxy_retries}, Proxy: {current_proxy})")
            ydl_opts = {
                'format': 'best/bestvideo+bestaudio/b',
                'outtmpl': out_template,
                'merge_output_format': 'mp4',
                'quiet': True,
                'no_warnings': True,
                'nocheckcertificate': True,
                'socket_timeout': 15,
                'retries': 2,
                'noplaylist': True,
                'extractor_args': {
                    'youtube': {
                        'player_client': client_list
                    }
                },
                'http_headers': {'User-Agent': MOBILE_USER_AGENTS[0]}
            }
            
            if current_proxy:
                proxy_url = current_proxy if current_proxy.startswith('http') else f"http://{current_proxy}"
                ydl_opts['proxy'] = proxy_url
                
            if cookie_path:
                ydl_opts['cookiefile'] = cookie_path

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(youtube_url, download=True)
                downloaded_file = ydl.prepare_filename(info)
                base, _ = os.path.splitext(downloaded_file)
                mp4_file = base + ".mp4"
                if os.path.exists(mp4_file):
                    logger.info(f"SUCCESS download via yt-dlp {client_list} using proxy {current_proxy}")
                    if status_callback: status_callback("✅ تم التحميل بنجاح عبر yt-dlp والبروكسي!")
                    return mp4_file, info
                if os.path.exists(downloaded_file):
                    if status_callback: status_callback("✅ تم التحميل بنجاح عبر yt-dlp!")
                    return downloaded_file, info
        except Exception as e:
            logger.warning(f"yt-dlp client {client_list} with proxy {current_proxy} failed: {e}")
            last_exception = e
            # If error is bot detection or network error, remove proxy
            if current_proxy and ("Sign in" in str(e) or "bot" in str(e).lower() or "timeout" in str(e).lower() or "HTTP Error 429" in str(e)):
                proxy_manager.remove_proxy(current_proxy)
            continue

    if last_exception:
        logger.warning(f"All yt-dlp clients and proxies failed: {last_exception}")

    raise RuntimeError("تعذر تحميل المقطع بعد تجربة جميع الحلول والطبقات الذكية. يرجى التأكد من الرابط.")

def download_background_media(media_url: str, output_dir: str, task_id: str, status_callback=None) -> str:
    """
    تحميل مقطع الخلفية (يوتيوب، انستقرام، تيك توك، بنترست...)
    """
    os.makedirs(output_dir, exist_ok=True)
    out_template = os.path.join(output_dir, f"{task_id}_bg.%(ext)s")
    cookie_path = find_cookie_file()
    video_id = extract_youtube_id(media_url)

    if video_id:
        bg_path, _ = download_youtube_media(media_url, output_dir, f"{task_id}_bg", status_callback=status_callback)
        return bg_path

    # المنصات الأخرى (بنترست، تيك توك، إلخ)
    max_proxy_retries = 10
    last_exception = None
    
    for attempt in range(max_proxy_retries):
        current_proxy = proxy_manager.get_proxy()
        if status_callback: status_callback(f"🖼️ [مقطع الخلفية] المحاولة {attempt+1}/{max_proxy_retries} عبر البروكسي ({current_proxy or 'مباشر'})...")
        ydl_opts = {
            'format': 'best/bestvideo+bestaudio/b',
            'outtmpl': out_template,
            'merge_output_format': 'mp4',
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
            'http_headers': {'User-Agent': MOBILE_USER_AGENTS[0]}
        }
        
        if current_proxy:
            proxy_url = current_proxy if current_proxy.startswith('http') else f"http://{current_proxy}"
            ydl_opts['proxy'] = proxy_url
            
        if cookie_path:
            ydl_opts['cookiefile'] = cookie_path

        try:
            logger.info(f"Downloading background media {media_url} (Attempt {attempt+1}, Proxy: {current_proxy})")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(media_url, download=True)
                downloaded_file = ydl.prepare_filename(info)
                base, _ = os.path.splitext(downloaded_file)
                mp4_file = base + ".mp4"
                if os.path.exists(mp4_file):
                    if status_callback: status_callback("✅ تم تحميل مقطع الخلفية بنجاح!")
                    return mp4_file
                if status_callback: status_callback("✅ تم تحميل مقطع الخلفية بنجاح!")
                return downloaded_file
        except Exception as e:
            logger.error(f"Background media download failed with proxy {current_proxy}: {e}")
            last_exception = e
            if current_proxy and ("Sign in" in str(e) or "bot" in str(e).lower() or "timeout" in str(e).lower() or "HTTP Error 429" in str(e)):
                proxy_manager.remove_proxy(current_proxy)
            continue
            
    raise RuntimeError(f"تعذر تحميل مقطع الخلفية بعد تجربة البروكسيات: {last_exception}")

def create_shorts_video(
    video_path: str,
    image_path: str,
    output_path: str,
    layout: str = "black_screen_transparent",
    key_tolerance: float = 0.25,
    video_position: str = "center",
    start_time: float = 0,
    end_time: float = None,
    progress_callback=None
):
    overlay_pos = "(W-w)/2:(H-h)/2"
    if video_position == "top":
        overlay_pos = "(W-w)/2:120"
    elif video_position == "bottom":
        overlay_pos = "(W-w)/2:H-h-120"

    if layout in ("black_screen_transparent", "colorkey_transparent"):
        tol_str = f"{key_tolerance:.2f}"
        filter_complex = (
            "[1:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920[bg];"
            f"[0:v]format=rgba,colorkey=0x000000:{tol_str}:0.1,scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black@0[fg];"
            f"[bg][fg]overlay={overlay_pos}:format=auto[v]"
        )
    elif layout == "screen_blend_mode":
        filter_complex = (
            "[1:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920[bg];"
            "[0:v]scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black[vid];"
            "[bg][vid]blend=all_mode='screen':all_opacity=1[v]"
        )
    elif layout == "split_top_image":
        filter_complex = (
            "[1:v]scale=1080:864:force_original_aspect_ratio=decrease,pad=1080:864:(ow-iw)/2:(oh-ih)/2:color=black[top];"
            "[0:v]scale=1080:1056:force_original_aspect_ratio=increase,crop=1080:1056[bottom];"
            "[top][bottom]vstack=inputs=2[v]"
        )
    elif layout == "split_bottom_image":
        filter_complex = (
            "[0:v]scale=1080:1056:force_original_aspect_ratio=increase,crop=1080:1056[top];"
            "[1:v]scale=1080:864:force_original_aspect_ratio=decrease,pad=1080:864:(ow-iw)/2:(oh-ih)/2:color=black[bottom];"
            "[top][bottom]vstack=inputs=2[v]"
        )
    else:
        filter_complex = (
            "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=30[bg];"
            "[1:v]scale=1000:1000:force_original_aspect_ratio=decrease,pad=1000:1000:(ow-iw)/2:(oh-ih)/2:color=black@0[img];"
            "[bg][img]overlay=(W-w)/2:(H-h)/2[v]"
        )

    cmd = ["ffmpeg", "-y"]
    if start_time > 0:
        cmd.extend(["-ss", str(start_time)])
    if end_time and end_time > start_time:
        cmd.extend(["-to", str(end_time)])

    cmd.extend([
        "-i", video_path, "-loop", "1", "-i", image_path,
        "-filter_complex", filter_complex,
        "-map", "[v]", "-map", "0:a?",
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest", "-pix_fmt", "yuv420p", output_path
    ])

    logger.info(f"FFmpeg: {' '.join(cmd)}")
    process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if process.returncode != 0:
        raise RuntimeError(f"فشلت عملية الدمج في FFmpeg: {process.stderr[-500:]}")
    return output_path

def create_shorts_video_from_video(
    primary_video_path: str,
    bg_video_path: str,
    output_path: str,
    layout: str = "black_screen_transparent",
    key_tolerance: float = 0.25,
    video_position: str = "center",
    start_time: float = 0,
    end_time: float = None
):
    def get_duration(path):
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=noprint_wrappers=1:nokey=1", path]
        try:
            return float(subprocess.check_output(cmd).decode("utf-8").strip())
        except:
            return 10.0

    dur1 = get_duration(primary_video_path)
    dur2 = get_duration(bg_video_path)
    if end_time and end_time > start_time:
        dur1 = min(dur1, end_time - start_time)
    speed_factor = 1.0
    if dur2 < dur1 and dur2 > 0:
        speed_factor = dur1 / dur2

    overlay_pos = "(W-w)/2:(H-h)/2"
    if video_position == "top":
        overlay_pos = "(W-w)/2:120"
    elif video_position == "bottom":
        overlay_pos = "(W-w)/2:H-h-120"

    bg_filter = f"[1:v]setpts=PTS*{speed_factor},scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920[bg];"

    if layout in ("black_screen_transparent", "colorkey_transparent"):
        tol_str = f"{key_tolerance:.2f}"
        filter_complex = (
            bg_filter +
            f"[0:v]format=rgba,colorkey=0x000000:{tol_str}:0.1,scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black@0[fg];"
            f"[bg][fg]overlay={overlay_pos}:format=auto[v]"
        )
    elif layout == "screen_blend_mode":
        filter_complex = (
            bg_filter +
            "[0:v]scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black[vid];"
            "[bg][vid]blend=all_mode='screen':all_opacity=1[v]"
        )
    else:
        filter_complex = (
            bg_filter +
            "[0:v]scale=1000:1000:force_original_aspect_ratio=decrease,pad=1000:1000:(ow-iw)/2:(oh-ih)/2:color=black@0[vid];"
            "[bg][vid]overlay=(W-w)/2:(H-h)/2[v]"
        )

    cmd = ["ffmpeg", "-y"]
    if start_time > 0:
        cmd.extend(["-ss", str(start_time)])
    if end_time and end_time > start_time:
        cmd.extend(["-to", str(end_time)])

    cmd.extend([
        "-i", primary_video_path, "-i", bg_video_path,
        "-filter_complex", filter_complex,
        "-map", "[v]", "-map", "0:a?",
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest", "-pix_fmt", "yuv420p", output_path
    ])

    logger.info(f"FFmpeg video+video: {' '.join(cmd)}")
    process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if process.returncode != 0:
        raise RuntimeError(f"فشلت عملية الدمج في FFmpeg: {process.stderr[-500:]}")
    return output_path
