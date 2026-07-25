import os
import re
import subprocess
import logging
import json
import uuid
import time
import urllib.request
import urllib.parse
import yt_dlp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("processor")

MOBILE_USER_AGENTS = [
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15'
]

# -------------------------------------------------------------------
# قائمة ثابتة من خوادم Invidious الموثوقة (تعمل server-to-server)
# لا تعتمد على cobalt.wiki الذي يفشل من IPs خوادم السحابة
# -------------------------------------------------------------------
INVIDIOUS_INSTANCES = [
    "https://inv.tux.pizza",
    "https://invidious.nerdvpn.de",
    "https://invidious.privacyredirect.com",
    "https://invidious.perennialte.ch",
    "https://iv.melmac.space",
    "https://invidious.fdn.fr",
    "https://invidious.drgns.space",
    "https://invidious.incogniweb.net",
    "https://invidious.slipfox.xyz",
    "https://vid.puffyan.us",
    "https://invidious.io.lol",
    "https://invidious.private.coffee",
    "https://yewtu.be",
    "https://invidious.projectsegfau.lt",
]

# -------------------------------------------------------------------
# خوادم Piped كبديل ثانٍ
# -------------------------------------------------------------------
PIPED_INSTANCES = [
    "https://pipedapi.kavin.rocks",
    "https://pipedapi.adminforge.de",
    "https://pipedapi.tokhmi.xyz",
    "https://pipedapi.moomoo.me",
    "https://pipedapi.syncpundit.io",
]


def find_cookie_file() -> str:
    """البحث عن ملف الكوكيز في المسارات المحتملة"""
    possible_paths = [
        os.path.join(os.path.dirname(__file__), "cookies.txt"),
        os.path.join(os.getcwd(), "cookies.txt"),
        os.path.join(os.path.dirname(__file__), "..", "cookies.txt")
    ]
    for p in possible_paths:
        if os.path.isfile(p) and os.path.getsize(p) > 0:
            return p
    return None


def extract_youtube_id(url: str) -> str:
    match = re.search(r'(?:v=|\/|be\/|shorts\/)([a-zA-Z0-9_-]{11})', url)
    return match.group(1) if match else None


def _safe_download_url(url: str, output_path: str, timeout: int = 60) -> bool:
    """تحميل ملف من رابط مباشر مع دعم ملفات الميديا الكبيرة"""
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': MOBILE_USER_AGENTS[0],
            'Referer': 'https://www.youtube.com/',
            'Origin': 'https://www.youtube.com'
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            chunk_size = 1024 * 1024  # 1MB chunks
            with open(output_path, 'wb') as f:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
        size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
        return size > 10000  # minimum 10KB
    except Exception as e:
        logger.warning(f"Direct download failed from {url[:60]}: {e}")
        return False


def fetch_from_invidious(video_id: str) -> dict:
    """جلب معلومات المقطع عبر Invidious"""
    for base in INVIDIOUS_INSTANCES:
        try:
            url = f"{base}/api/v1/videos/{video_id}"
            req = urllib.request.Request(url, headers={
                'User-Agent': MOBILE_USER_AGENTS[1],
                'Accept': 'application/json'
            })
            with urllib.request.urlopen(req, timeout=8) as resp:
                if resp.getcode() == 200:
                    data = json.loads(resp.read().decode('utf-8'))
                    title = data.get('title', 'مقطع يوتيوب')
                    dur = data.get('lengthSeconds', 90)
                    thumb = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
                    # استخراج رابط stream مباشر
                    streams = []
                    for fmt in data.get('adaptiveFormats', []):
                        if fmt.get('type', '').startswith('video/mp4'):
                            streams.append((fmt.get('bitrate', 0), fmt.get('url', '')))
                    for fmt in data.get('formatStreams', []):
                        if 'mp4' in fmt.get('type', ''):
                            streams.append((999999, fmt.get('url', '')))
                    
                    stream_url = None
                    if streams:
                        streams.sort(key=lambda x: x[0], reverse=True)
                        stream_url = streams[0][1]
                    
                    return {
                        'title': title,
                        'duration': dur,
                        'thumbnail': thumb,
                        'stream_url': stream_url,
                        'instance': base
                    }
        except Exception as e:
            logger.warning(f"Invidious {base} failed: {e}")
    return None


def fetch_from_piped(video_id: str) -> dict:
    """جلب معلومات وروابط التدفق عبر Piped API"""
    for base in PIPED_INSTANCES:
        try:
            url = f"{base}/streams/{video_id}"
            req = urllib.request.Request(url, headers={
                'User-Agent': MOBILE_USER_AGENTS[0],
                'Accept': 'application/json'
            })
            with urllib.request.urlopen(req, timeout=8) as resp:
                if resp.getcode() == 200:
                    data = json.loads(resp.read().decode('utf-8'))
                    title = data.get('title', 'مقطع يوتيوب')
                    dur = data.get('duration', 90)
                    thumb = data.get('thumbnailUrl') or f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
                    
                    # أفضل رابط تدفق مباشر
                    stream_url = None
                    best_bitrate = 0
                    for s in data.get('videoStreams', []):
                        bitrate = s.get('bitrate', 0)
                        fmt = s.get('format', '')
                        if fmt in ('MP4', 'MPEG_4') and bitrate > best_bitrate:
                            best_bitrate = bitrate
                            stream_url = s.get('url')
                    
                    # fallback: first available stream
                    if not stream_url and data.get('videoStreams'):
                        stream_url = data['videoStreams'][0].get('url')
                    
                    return {
                        'title': title,
                        'duration': dur,
                        'thumbnail': thumb,
                        'stream_url': stream_url,
                        'instance': base
                    }
        except Exception as e:
            logger.warning(f"Piped {base} failed: {e}")
    return None


def get_video_info(youtube_url: str):
    """
    جلب معلومات المقطع بطبقات متعددة مضمونة.
    """
    video_id = extract_youtube_id(youtube_url)

    # 1. YouTube oEmbed (سريع وموثوق للعنوان والصورة المصغرة)
    try:
        oembed_url = f"https://www.youtube.com/oembed?url={urllib.parse.quote(youtube_url)}&format=json"
        req = urllib.request.Request(oembed_url, headers={'User-Agent': MOBILE_USER_AGENTS[0]})
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.getcode() == 200:
                data = json.loads(resp.read().decode('utf-8'))
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

    # 2. Invidious
    if video_id:
        result = fetch_from_invidious(video_id)
        if result:
            dur = result['duration']
            dur_str = f"{int(dur // 60)} دقيقة و {int(dur % 60)} ثانية" if dur else "غير محدد"
            return {
                'id': video_id,
                'title': result['title'],
                'duration': dur,
                'duration_string': dur_str,
                'thumbnail': result['thumbnail']
            }

    # 3. Piped
    if video_id:
        result = fetch_from_piped(video_id)
        if result:
            dur = result['duration']
            dur_str = f"{int(dur // 60)} دقيقة و {int(dur % 60)} ثانية" if dur else "غير محدد"
            return {
                'id': video_id,
                'title': result['title'],
                'duration': dur,
                'duration_string': dur_str,
                'thumbnail': result['thumbnail']
            }

    # 4. yt-dlp (آخر محاولة)
    cookie_path = find_cookie_file()
    for client in ['ios', 'android', 'mweb', 'tv_embedded']:
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'socket_timeout': 8,
                'extractor_args': {'youtube': {'player_client': [client]}},
                'http_headers': {'User-Agent': MOBILE_USER_AGENTS[0]}
            }
            if cookie_path:
                ydl_opts['cookiefile'] = cookie_path
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(youtube_url, download=False)
                dur = info.get('duration') or 0
                dur_str = f"{int(dur // 60)} دقيقة و {int(dur % 60)} ثانية" if dur else "غير محدد"
                return {
                    'id': info.get('id') or video_id,
                    'title': info.get('title') or 'مقطع يوتيوب',
                    'duration': dur,
                    'duration_string': dur_str,
                    'thumbnail': info.get('thumbnail') or f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
                }
        except Exception as err:
            logger.warning(f"yt-dlp info failed ({client}): {err}")

    # 5. Fallback مطلق
    thumb_url = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg" if video_id else ""
    return {
        'id': video_id or "unknown",
        'title': "مقطع فيديو جاهز للدمج",
        'duration': 90,
        'duration_string': "مقطع فيديو",
        'thumbnail': thumb_url
    }


def download_youtube_media(youtube_url: str, output_dir: str, task_id: str):
    """
    تحميل مقطع يوتيوب بطبقات متعددة:
    1. Invidious stream مباشر (الأسرع من data center IPs)
    2. Piped stream مباشر
    3. yt-dlp مع عملاء متعددة + cookies
    """
    os.makedirs(output_dir, exist_ok=True)
    final_mp4 = os.path.join(output_dir, f"{task_id}_raw.mp4")
    out_template = os.path.join(output_dir, f"{task_id}_raw.%(ext)s")
    cookie_path = find_cookie_file()
    video_id = extract_youtube_id(youtube_url)

    # ================================================================
    # الطبقة 1: Invidious (أفضل حل لـ data center IPs)
    # ================================================================
    logger.info(f"[Layer 1] Trying Invidious for {video_id}")
    if video_id:
        result = fetch_from_invidious(video_id)
        if result and result.get('stream_url'):
            logger.info(f"[Layer 1] Invidious stream URL found from {result['instance']}, downloading...")
            if _safe_download_url(result['stream_url'], final_mp4, timeout=120):
                logger.info(f"[Layer 1] SUCCESS via Invidious: {result['instance']}")
                info_dict = {
                    'id': video_id,
                    'title': result['title'],
                    'duration': result['duration'],
                    'duration_string': f"{int(result['duration'] // 60)} دقيقة",
                    'thumbnail': result['thumbnail']
                }
                return final_mp4, info_dict
            else:
                logger.warning("[Layer 1] Invidious stream download failed (file too small or error)")

    # ================================================================
    # الطبقة 2: Piped
    # ================================================================
    logger.info(f"[Layer 2] Trying Piped for {video_id}")
    if video_id:
        result = fetch_from_piped(video_id)
        if result and result.get('stream_url'):
            logger.info(f"[Layer 2] Piped stream URL found from {result['instance']}, downloading...")
            if _safe_download_url(result['stream_url'], final_mp4, timeout=120):
                logger.info(f"[Layer 2] SUCCESS via Piped: {result['instance']}")
                info_dict = {
                    'id': video_id,
                    'title': result['title'],
                    'duration': result['duration'],
                    'duration_string': f"{int(result['duration'] // 60)} دقيقة",
                    'thumbnail': result['thumbnail']
                }
                return final_mp4, info_dict
            else:
                logger.warning("[Layer 2] Piped stream download failed")

    # ================================================================
    # الطبقة 3: yt-dlp مع عملاء متعددة
    # ================================================================
    logger.info("[Layer 3] Trying yt-dlp with multiple clients")
    clients_to_try = [
        ['android', 'mweb'],
        ['android'],
        ['ios'],
        ['mweb'],
        ['tv_embedded'],
        ['web_creator'],
    ]

    last_exception = None
    for idx, client_list in enumerate(clients_to_try):
        try:
            ua = MOBILE_USER_AGENTS[idx % len(MOBILE_USER_AGENTS)]
            ydl_opts = {
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'outtmpl': out_template,
                'merge_output_format': 'mp4',
                'quiet': True,
                'no_warnings': True,
                'nocheckcertificate': True,
                'socket_timeout': 30,
                'retries': 3,
                'noplaylist': True,
                'extractor_args': {
                    'youtube': {
                        'player_client': client_list
                    }
                },
                'http_headers': {'User-Agent': ua}
            }
            if cookie_path:
                ydl_opts['cookiefile'] = cookie_path

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(youtube_url, download=True)
                downloaded_file = ydl.prepare_filename(info)
                base, _ = os.path.splitext(downloaded_file)
                mp4_file = base + ".mp4"
                if os.path.exists(mp4_file):
                    logger.info(f"[Layer 3] SUCCESS via yt-dlp client {client_list}")
                    return mp4_file, info
                if os.path.exists(downloaded_file):
                    return downloaded_file, info
        except Exception as e:
            logger.warning(f"[Layer 3] yt-dlp client {client_list} failed: {e}")
            last_exception = e

    # ================================================================
    # الطبقة 4: Invidious embed download (حل أخير)
    # ================================================================
    logger.info("[Layer 4] Trying Invidious embed page download via yt-dlp")
    if video_id:
        for inv_base in INVIDIOUS_INSTANCES[:5]:
            invidious_url = f"{inv_base}/watch?v={video_id}"
            try:
                ydl_opts = {
                    'format': 'best[ext=mp4]/best',
                    'outtmpl': out_template,
                    'merge_output_format': 'mp4',
                    'quiet': True,
                    'no_warnings': True,
                    'nocheckcertificate': True,
                    'socket_timeout': 30,
                    'retries': 2,
                    'noplaylist': True,
                }
                if cookie_path:
                    ydl_opts['cookiefile'] = cookie_path
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(invidious_url, download=True)
                    downloaded_file = ydl.prepare_filename(info)
                    base, _ = os.path.splitext(downloaded_file)
                    mp4_file = base + ".mp4"
                    if os.path.exists(mp4_file):
                        logger.info(f"[Layer 4] SUCCESS via Invidious embed {inv_base}")
                        return mp4_file, info
                    if os.path.exists(downloaded_file):
                        return downloaded_file, info
            except Exception as e:
                logger.warning(f"[Layer 4] Invidious embed {inv_base} failed: {e}")

    if last_exception:
        raise last_exception
    raise RuntimeError("تعذر تحميل المقطع بعد تجربة جميع طرق التنزيل البديلة.")


def download_background_media(media_url: str, output_dir: str, task_id: str) -> str:
    """
    تحميل مقطع الخلفية (يوتيوب، انستقرام، تيك توك، بنترست...) بآلية ذكية متعددة الطبقات.
    """
    os.makedirs(output_dir, exist_ok=True)
    out_template = os.path.join(output_dir, f"{task_id}_bg.%(ext)s")
    final_mp4 = os.path.join(output_dir, f"{task_id}_bg.mp4")
    cookie_path = find_cookie_file()

    # للروابط من يوتيوب، نجرب Invidious/Piped أولاً
    video_id = extract_youtube_id(media_url)
    if video_id:
        result = fetch_from_invidious(video_id)
        if result and result.get('stream_url'):
            if _safe_download_url(result['stream_url'], final_mp4, timeout=120):
                return final_mp4
        
        result = fetch_from_piped(video_id)
        if result and result.get('stream_url'):
            if _safe_download_url(result['stream_url'], final_mp4, timeout=120):
                return final_mp4

    # yt-dlp لبقية المنصات
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': out_template,
        'merge_output_format': 'mp4',
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'socket_timeout': 30,
        'retries': 3,
        'noplaylist': True,
        'http_headers': {'User-Agent': MOBILE_USER_AGENTS[0]}
    }
    if cookie_path:
        ydl_opts['cookiefile'] = cookie_path

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(media_url, download=True)
            downloaded_file = ydl.prepare_filename(info)
            base, _ = os.path.splitext(downloaded_file)
            mp4_file = base + ".mp4"
            if os.path.exists(mp4_file):
                return mp4_file
            return downloaded_file
    except Exception as e:
        logger.error(f"Background media download failed: {e}")
        raise RuntimeError(f"تعذر تحميل مقطع الخلفية: {e}")


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
    """
    دمج الفيديو والصورة وتحويل التنسيق إلى يوتيوب شورتس (1080x1920 - 9:16)
    """
    overlay_pos = "(W-w)/2:(H-h)/2"
    if video_position == "top":
        overlay_pos = "(W-w)/2:120"
    elif video_position == "bottom":
        overlay_pos = "(W-w)/2:H-h-120"

    filter_complex = ""

    if layout == "black_screen_transparent" or layout == "colorkey_transparent":
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
    else:  # center_image_blur_bg
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
        "-i", video_path,
        "-loop", "1", "-i", image_path,
        "-filter_complex", filter_complex,
        "-map", "[v]",
        "-map", "0:a?",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "22",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-pix_fmt", "yuv420p",
        output_path
    ])

    logger.info(f"Running FFmpeg: {' '.join(cmd)}")
    process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    if process.returncode != 0:
        logger.error(f"FFmpeg error: {process.stderr}")
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
    """
    دمج فيديو أساسي (شاشة سوداء) مع فيديو خلفية مع مزامنة السرعة.
    """
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

    if layout == "black_screen_transparent" or layout == "colorkey_transparent":
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
        "-i", primary_video_path,
        "-i", bg_video_path,
        "-filter_complex", filter_complex,
        "-map", "[v]",
        "-map", "0:a?",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "22",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-pix_fmt", "yuv420p",
        output_path
    ])

    logger.info(f"Running FFmpeg for video: {' '.join(cmd)}")
    process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    if process.returncode != 0:
        logger.error(f"FFmpeg error: {process.stderr}")
        raise RuntimeError(f"فشلت عملية الدمج في FFmpeg: {process.stderr[-500:]}")

    return output_path
