import os
import re
import subprocess
import logging
import json
import urllib.request
import urllib.parse
import urllib.error
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
# Invidious instances - the /latest_version endpoint proxies through
# the Invidious server itself, bypassing YouTube CDN blocks on cloud IPs
# itag=22 = 720p MP4, itag=18 = 360p MP4
# -------------------------------------------------------------------
INVIDIOUS_INSTANCES = [
    "https://yewtu.be",           # CONFIRMED WORKING from cloud IPs (HTTP 206)
    "https://invidious.fdn.fr",
    "https://invidious.projectsegfau.lt",
    "https://iv.melmac.space",
    "https://invidious.private.coffee",
    "https://invidious.incogniweb.net",
    "https://invidious.perennialte.ch",
    "https://vid.puffyan.us",
    "https://invidious.io.lol",
    "https://invidious.slipfox.xyz",
    "https://invidious.nerdvpn.de",
    "https://invidious.drgns.space",
    "https://invidious.privacyredirect.com",
    "https://inv.tux.pizza",
]

PIPED_INSTANCES = [
    "https://pipedapi.kavin.rocks",
    "https://pipedapi.adminforge.de",
    "https://pipedapi.tokhmi.xyz",
    "https://pipedapi.moomoo.me",
    "https://pipedapi.syncpundit.io",
]

ITAGS_PRIORITY = [22, 18, 137, 248, 136, 247, 135, 244, 134, 243, 133]


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


def _download_chunked(url: str, output_path: str, timeout: int = 120, extra_headers: dict = None) -> bool:
    """تحميل ملف بالـ chunks مع دعم الملفات الكبيرة"""
    headers = {
        'User-Agent': MOBILE_USER_AGENTS[0],
        'Accept': '*/*',
        'Accept-Encoding': 'identity',
    }
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            with open(output_path, 'wb') as f:
                while True:
                    chunk = resp.read(512 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
        size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
        return size > 50000  # at least 50KB
    except Exception as e:
        logger.warning(f"Chunked download failed from {url[:60]}: {e}")
        if os.path.exists(output_path):
            os.remove(output_path)
        return False


# ====================================================================
# LAYER 1: Invidious /latest_version PROXY endpoint
# This proxies through the Invidious server itself → no YouTube CDN block
# ====================================================================
def download_via_invidious_proxy(video_id: str, output_path: str) -> bool:
    """
    استخدام نقطة النهاية /latest_version الخاصة بـ Invidious
    هذه النقطة تُنزّل الفيديو عبر خادم Invidious نفسه كوسيط
    مما يخفي IP السحابة عن يوتيوب تماماً
    """
    for base in INVIDIOUS_INSTANCES:
        for itag in ITAGS_PRIORITY[:5]:
            proxy_url = f"{base}/latest_version?id={video_id}&itag={itag}&local=true"
            logger.info(f"[Invidious Proxy] Trying {base} itag={itag}")
            try:
                if _download_chunked(proxy_url, output_path, timeout=180):
                    logger.info(f"[Invidious Proxy] SUCCESS {base} itag={itag}")
                    return True
            except Exception as e:
                logger.warning(f"[Invidious Proxy] {base} itag={itag} failed: {e}")
    return False


# ====================================================================
# LAYER 2: Piped proxyUrl (proxied through Piped server)
# ====================================================================
def download_via_piped_proxy(video_id: str, output_path: str) -> bool:
    """
    استخدام Piped API مع حقل proxyUrl الذي يوجّه التدفق عبر خادم Piped
    """
    for base in PIPED_INSTANCES:
        try:
            data = _http_get_json(f"{base}/streams/{video_id}", timeout=10)
            streams = data.get('videoStreams', [])
            
            # ترتيب حسب الجودة، ونفضّل proxyUrl على url
            best_url = None
            best_quality = 0
            for s in streams:
                quality = s.get('quality', '') or ''
                try:
                    q_num = int(quality.replace('p', '').split(' ')[0])
                except:
                    q_num = 0
                fmt = s.get('format', '')
                # نفضل MP4
                if fmt in ('MP4', 'MPEG_4') and q_num > best_quality:
                    # نستخدم proxyUrl أولاً (يمر عبر سيرفر Piped)
                    proxy_url = s.get('proxyUrl') or s.get('url')
                    if proxy_url:
                        best_quality = q_num
                        best_url = proxy_url
            
            if not best_url and streams:
                s = streams[0]
                best_url = s.get('proxyUrl') or s.get('url')
            
            if best_url:
                logger.info(f"[Piped Proxy] Trying {base}")
                if _download_chunked(best_url, output_path, timeout=180):
                    logger.info(f"[Piped Proxy] SUCCESS via {base}")
                    return True
        except Exception as e:
            logger.warning(f"[Piped Proxy] {base} failed: {e}")
    return False


# ====================================================================
# LAYER 3: Invidious API with local=true (proxied stream URLs)
# ====================================================================
def download_via_invidious_api_local(video_id: str, output_path: str) -> bool:
    """
    استخدام Invidious API مع local=true لجلب روابط تدفق مُوكّلة
    """
    for base in INVIDIOUS_INSTANCES:
        try:
            data = _http_get_json(f"{base}/api/v1/videos/{video_id}?local=true", timeout=10)
            
            # نبحث في formatStreams أولاً (روابط مدمجة أسهل)
            format_streams = data.get('formatStreams', [])
            for fmt in sorted(format_streams, key=lambda x: x.get('bitrate', 0), reverse=True):
                if 'mp4' in fmt.get('type', '').lower():
                    stream_url = fmt.get('url')
                    if stream_url:
                        logger.info(f"[Invidious API local] Trying formatStream from {base}")
                        if _download_chunked(stream_url, output_path, timeout=180):
                            logger.info(f"[Invidious API local] SUCCESS via {base}")
                            return True
            
            # ثم adaptiveFormats
            adaptive = data.get('adaptiveFormats', [])
            for fmt in sorted(adaptive, key=lambda x: x.get('bitrate', 0), reverse=True):
                if 'video/mp4' in fmt.get('type', '').lower():
                    stream_url = fmt.get('url')
                    if stream_url:
                        logger.info(f"[Invidious API local] Trying adaptive from {base}")
                        if _download_chunked(stream_url, output_path, timeout=180):
                            logger.info(f"[Invidious API local] SUCCESS adaptive via {base}")
                            return True
        except Exception as e:
            logger.warning(f"[Invidious API local] {base} failed: {e}")
    return False


# ====================================================================
# INFO functions
# ====================================================================
def fetch_youtube_info_from_invidious(video_id: str) -> dict:
    for base in INVIDIOUS_INSTANCES:
        try:
            data = _http_get_json(f"{base}/api/v1/videos/{video_id}", timeout=8)
            title = data.get('title', 'مقطع يوتيوب')
            dur = data.get('lengthSeconds', 90)
            thumb = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
            return {'title': title, 'duration': dur, 'thumbnail': thumb}
        except Exception as e:
            logger.warning(f"Invidious info {base}: {e}")
    return None


def get_video_info(youtube_url: str):
    video_id = extract_youtube_id(youtube_url)

    # 1. YouTube oEmbed
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

    # 2. Invidious
    if video_id:
        result = fetch_youtube_info_from_invidious(video_id)
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

    # 3. yt-dlp (last resort for info only)
    cookie_path = find_cookie_file()
    for client in ['ios', 'android', 'tv_embedded']:
        try:
            ydl_opts = {
                'quiet': True, 'no_warnings': True, 'socket_timeout': 8,
                'extractor_args': {'youtube': {'player_client': [client]}},
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


# ====================================================================
# MAIN DOWNLOAD FUNCTION
# ====================================================================
def download_youtube_media(youtube_url: str, output_dir: str, task_id: str):
    os.makedirs(output_dir, exist_ok=True)
    final_mp4 = os.path.join(output_dir, f"{task_id}_raw.mp4")
    out_template = os.path.join(output_dir, f"{task_id}_raw.%(ext)s")
    cookie_path = find_cookie_file()
    video_id = extract_youtube_id(youtube_url)

    # ================================================================
    # الطبقة 1: Invidious /latest_version Proxy (الأقوى - يمر عبر سيرفر Invidious)
    # ================================================================
    logger.info(f"[Layer 1] Invidious /latest_version proxy for {video_id}")
    if video_id:
        if download_via_invidious_proxy(video_id, final_mp4):
            info_dict = fetch_youtube_info_from_invidious(video_id) or {}
            return final_mp4, {
                'id': video_id,
                'title': info_dict.get('title', 'مقطع يوتيوب'),
                'duration': info_dict.get('duration', 90),
                'thumbnail': info_dict.get('thumbnail', f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg")
            }

    # ================================================================
    # الطبقة 2: Piped proxyUrl (يمر عبر سيرفر Piped)
    # ================================================================
    logger.info(f"[Layer 2] Piped proxy for {video_id}")
    if video_id:
        if download_via_piped_proxy(video_id, final_mp4):
            info_dict = fetch_youtube_info_from_invidious(video_id) or {}
            return final_mp4, {
                'id': video_id,
                'title': info_dict.get('title', 'مقطع يوتيوب'),
                'duration': info_dict.get('duration', 90),
                'thumbnail': info_dict.get('thumbnail', f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg")
            }

    # ================================================================
    # الطبقة 3: Invidious API local=true
    # ================================================================
    logger.info(f"[Layer 3] Invidious API local=true for {video_id}")
    if video_id:
        if download_via_invidious_api_local(video_id, final_mp4):
            info_dict = fetch_youtube_info_from_invidious(video_id) or {}
            return final_mp4, {
                'id': video_id,
                'title': info_dict.get('title', 'مقطع يوتيوب'),
                'duration': info_dict.get('duration', 90),
                'thumbnail': info_dict.get('thumbnail', f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg")
            }

    # ================================================================
    # الطبقة 4: yt-dlp مع عملاء متعددة + cookies
    # ================================================================
    logger.info("[Layer 4] yt-dlp multi-client fallback")
    clients_to_try = [
        ['android', 'mweb'], ['android'], ['ios'],
        ['mweb'], ['tv_embedded'], ['web_creator'],
    ]
    last_exception = None
    for idx, client_list in enumerate(clients_to_try):
        try:
            ua = MOBILE_USER_AGENTS[idx % len(MOBILE_USER_AGENTS)]
            ydl_opts = {
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'outtmpl': out_template,
                'merge_output_format': 'mp4',
                'quiet': True, 'no_warnings': True,
                'nocheckcertificate': True,
                'socket_timeout': 30, 'retries': 3, 'noplaylist': True,
                'extractor_args': {'youtube': {'player_client': client_list}},
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
                    logger.info(f"[Layer 4] yt-dlp SUCCESS {client_list}")
                    return mp4_file, info
                if os.path.exists(downloaded_file):
                    return downloaded_file, info
        except Exception as e:
            logger.warning(f"[Layer 4] yt-dlp {client_list}: {e}")
            last_exception = e

    if last_exception:
        raise last_exception
    raise RuntimeError("تعذر تحميل المقطع. يُرجى التحقق من الرابط أو المحاولة لاحقاً.")


def download_background_media(media_url: str, output_dir: str, task_id: str) -> str:
    """
    تحميل مقطع الخلفية (يوتيوب، انستقرام، تيك توك، بنترست...)
    """
    os.makedirs(output_dir, exist_ok=True)
    out_template = os.path.join(output_dir, f"{task_id}_bg.%(ext)s")
    final_mp4 = os.path.join(output_dir, f"{task_id}_bg.mp4")
    cookie_path = find_cookie_file()
    video_id = extract_youtube_id(media_url)

    # لروابط يوتيوب نستخدم Invidious proxy أولاً
    if video_id:
        if download_via_invidious_proxy(video_id, final_mp4):
            return final_mp4
        if download_via_piped_proxy(video_id, final_mp4):
            return final_mp4
        if download_via_invidious_api_local(video_id, final_mp4):
            return final_mp4

    # لبقية المنصات yt-dlp
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': out_template,
        'merge_output_format': 'mp4',
        'quiet': True, 'no_warnings': True,
        'nocheckcertificate': True,
        'socket_timeout': 30, 'retries': 3, 'noplaylist': True,
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
