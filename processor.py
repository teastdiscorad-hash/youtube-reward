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

def fetch_via_cobalt_fast(youtube_url: str):
    try:
        req = urllib.request.Request(
            "https://api.cobalt.tools/api/json",
            data=json.dumps({"url": youtube_url}).encode('utf-8'),
            headers={'Accept': 'application/json', 'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            res = json.loads(resp.read().decode('utf-8'))
            if res.get('status') in ['stream', 'redirect', 'picker']:
                return res.get('url')
    except Exception:
        pass
    return None

def download_youtube_media(youtube_url: str, output_dir: str, task_id: str, status_callback=None):
    """
    تحميل فيديو يوتيوب مع نظام تجاوز حظر البوتات والـ IP السحابي لـ Render
    """
    os.makedirs(output_dir, exist_ok=True)
    final_mp4 = os.path.join(output_dir, f"{task_id}_raw.mp4")
    out_template = os.path.join(output_dir, f"{task_id}_raw.%(ext)s")
    cookie_path = find_cookie_file()
    video_id = extract_youtube_id(youtube_url)

    # 1. المحاولة المباشرة عبر عملاء yt-dlp المتخصصين
    bulletproof_clients = [
        ['android_vr'],
        ['android_creator'],
        ['tv_embedded'],
        ['android'],
        ['web']
    ]

    last_exception = None
    for client_list in bulletproof_clients:
        try:
            client_name = client_list[0]
            if status_callback: status_callback(f"📥 [مكتبة yt] جاري التحميل عبر عميل {client_name}...")
            logger.info(f"Downloading with yt-dlp client: {client_list}")
            ydl_opts = {
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
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

            if cookie_path:
                ydl_opts['cookiefile'] = cookie_path

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(youtube_url, download=True)
                downloaded_file = ydl.prepare_filename(info)
                base, _ = os.path.splitext(downloaded_file)
                mp4_file = base + ".mp4"
                if os.path.exists(mp4_file) and os.path.getsize(mp4_file) > 100000:
                    if status_callback: status_callback("✅ تم التحميل بنجاح عبر مكتبة yt-dlp!")
                    return mp4_file, info
                if os.path.exists(downloaded_file) and os.path.getsize(downloaded_file) > 100000:
                    if status_callback: status_callback("✅ تم التحميل بنجاح عبر مكتبة yt-dlp!")
                    return downloaded_file, info
        except Exception as e:
            logger.warning(f"yt-dlp client {client_list} direct failed: {e}")
            last_exception = e

    # 2. التجاوز السريع الفوري لـ Render عبر خوادم Invidious Stream (تتجاوز حظر الـ IP والبوتات فورا بدون كوكيز)
    if video_id:
        if status_callback: status_callback("⚡ [تجاوز الحظر السحابي] جاري التحميل الفوري عبر خادم وسيط...")
        invidious_stream_servers = [
            "https://invidious.nerdvpn.de",
            "https://vid.pugices.pt",
            "https://invidious.fdn.fr",
            "https://inv.tux.pizza",
            "https://invidious.drgns.space",
            "https://invidious.lunar.icu"
        ]
        
        import ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        for base in invidious_stream_servers:
            proxy_url = f"{base}/latest_version?id={video_id}&itag=18"
            try:
                logger.info(f"Trying Invidious fast stream proxy: {proxy_url}")
                req = urllib.request.Request(proxy_url, headers={'User-Agent': MOBILE_USER_AGENTS[0]})
                with urllib.request.urlopen(req, timeout=8, context=ctx) as resp:
                    if resp.getcode() == 200:
                        with open(final_mp4, 'wb') as f:
                            while True:
                                chunk = resp.read(16384)
                                if not chunk: break
                                f.write(chunk)
                        if os.path.exists(final_mp4) and os.path.getsize(final_mp4) > 100000:
                            logger.info(f"SUCCESS download via Invidious fast stream {base}")
                            if status_callback: status_callback("✅ تم التحميل بنجاح عبر التجاوز السريع!")
                            return final_mp4, get_video_info(youtube_url)
            except Exception as e:
                logger.warning(f"Invidious stream proxy {base} failed: {e}")

    # 3. تجربة التخطي بالبروكسيات الدوارة (Free Proxy Pool)
    if status_callback: status_callback("🔄 [شبكة البروكسيات] جاري تجربة بروكسي سحابي مجاني...")
    for attempt in range(5):
        current_proxy = proxy_manager.get_proxy()
        if not current_proxy:
            break
        try:
            proxy_url = current_proxy if current_proxy.startswith('http') else f"http://{current_proxy}"
            ydl_opts = {
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'outtmpl': out_template,
                'merge_output_format': 'mp4',
                'quiet': True,
                'no_warnings': True,
                'nocheckcertificate': True,
                'proxy': proxy_url,
                'socket_timeout': 15,
                'retries': 2,
                'noplaylist': True,
                'http_headers': {'User-Agent': MOBILE_USER_AGENTS[0]}
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(youtube_url, download=True)
                downloaded_file = ydl.prepare_filename(info)
                base, _ = os.path.splitext(downloaded_file)
                mp4_file = base + ".mp4"
                if os.path.exists(mp4_file) and os.path.getsize(mp4_file) > 100000:
                    if status_callback: status_callback("✅ تم التحميل بنجاح عبر البروكسي!")
                    return mp4_file, info
                if os.path.exists(downloaded_file) and os.path.getsize(downloaded_file) > 100000:
                    return downloaded_file, info
        except Exception as e:
            logger.warning(f"Proxy attempt {attempt+1} failed: {e}")
            proxy_manager.remove_proxy(current_proxy)

    raise RuntimeError(f"تعذر تحميل المقطع بعد تجربة جميع طرق التجاوز: {last_exception}")

def download_background_media(media_url: str, output_dir: str, task_id: str, status_callback=None) -> str:
    """
    تحميل مقطع الخلفية (يوتيوب، انستقرام، تيك توك، بنترست...) عبر مكتبة yt
    """
    os.makedirs(output_dir, exist_ok=True)
    out_template = os.path.join(output_dir, f"{task_id}_bg.%(ext)s")
    cookie_path = find_cookie_file()
    video_id = extract_youtube_id(media_url)

    if video_id:
        bg_path, _ = download_youtube_media(media_url, output_dir, f"{task_id}_bg", status_callback=status_callback)
        return bg_path

    # المنصات الأخرى (بنترست، تيك توك، إلخ) عبر مكتبة yt-dlp المباشرة
    if status_callback: status_callback("🖼️ [مقطع الخلفية] جاري تحميل فيديو الخلفية مباشرة...")
    ydl_opts = {
        'format': 'best/bestvideo+bestaudio/b',
        'outtmpl': out_template,
        'merge_output_format': 'mp4',
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'socket_timeout': 30,
        'retries': 3,
        'http_headers': {'User-Agent': MOBILE_USER_AGENTS[0]}
    }
    
    if cookie_path:
        ydl_opts['cookiefile'] = cookie_path

    try:
        logger.info(f"Downloading background media {media_url} directly with yt-dlp")
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
        logger.error(f"Background media download failed: {e}")
        raise RuntimeError(f"تعذر تحميل مقطع الخلفية بواسطة مكتبة yt: {e}")

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
        "-c:v", "libx264", "-preset", "superfast", "-threads", "2", "-crf", "22",
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
        "-c:v", "libx264", "-preset", "superfast", "-threads", "2", "-crf", "22",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest", "-pix_fmt", "yuv420p", output_path
    ])

    logger.info(f"FFmpeg video+video: {' '.join(cmd)}")
    process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if process.returncode != 0:
        raise RuntimeError(f"فشلت عملية الدمج في FFmpeg: {process.stderr[-500:]}")
    return output_path
