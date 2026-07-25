import os
import re
import subprocess
import logging
import json
import uuid
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

def fetch_from_invidious_or_piped(video_id: str):
    """جلب بيانات المقطع عبر خدمات Invidious/Piped العامة"""
    instances = [
        f"https://pipedapi.kavin.rocks/streams/{video_id}",
        f"https://inv.tux.pizza/api/v1/videos/{video_id}",
        f"https://invidious.nerdvpn.de/api/v1/videos/{video_id}"
    ]
    for inst in instances:
        try:
            req = urllib.request.Request(inst, headers={'User-Agent': MOBILE_USER_AGENTS[1]})
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.getcode() == 200:
                    data = json.loads(resp.read().decode('utf-8'))
                    title = data.get('title') or data.get('videoTitle')
                    thumb = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
                    return {
                        'id': video_id,
                        'title': title or 'مقطع يوتيوب',
                        'duration': data.get('duration', 90),
                        'duration_string': 'مقطع يوتيوب',
                        'thumbnail': thumb
                    }
        except Exception as e:
            logger.warning(f"Invidious/Piped fallback failed on {inst}: {e}")
    return None

def get_video_info(youtube_url: str):
    """
    جلب معلومات مقطع اليوتيوب بآلية متعددة الطبقات تمنع الحظر كلياً:
    1. YouTube oEmbed API الرسمية
    2. yt-dlp مع تدوير عملاء البلاير ورؤوس الموبايل + cookies.txt
    3. Invidious / Piped APIs العامة
    4. Fallback آمن متكامل برابط المصغرة القياسي
    """
    video_id = extract_youtube_id(youtube_url)
    
    # 1. الطبقة الأولى: YouTube oEmbed API (سريعة، مجانية، لا تخضع لتحدي البوتات)
    try:
        oembed_url = f"https://www.youtube.com/oembed?url={urllib.parse.quote(youtube_url)}&format=json"
        req = urllib.request.Request(oembed_url, headers={'User-Agent': MOBILE_USER_AGENTS[0]})
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.getcode() == 200:
                data = json.loads(resp.read().decode('utf-8'))
                thumb = data.get('thumbnail_url')
                if not thumb and video_id:
                    thumb = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
                return {
                    'id': video_id or "youtube_video",
                    'title': data.get('title', 'مقطع يوتيوب'),
                    'duration': 90,
                    'duration_string': 'مقطع يوتيوب',
                    'thumbnail': thumb
                }
    except Exception as e:
        logger.warning(f"oEmbed fetch skipped: {e}")

    # 2. الطبقة الثانية: yt-dlp مع مصفوفة العملاء المتقدمة وتدوير User-Agent
    player_clients = ['ios', 'android', 'web_creator', 'mweb', 'tv_embedded']
    cookie_path = find_cookie_file()
    
    for idx, client in enumerate(player_clients):
        try:
            ua = MOBILE_USER_AGENTS[idx % len(MOBILE_USER_AGENTS)]
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'socket_timeout': 5,
                'extractor_args': {
                    'youtube': {
                        'player_client': [client],
                        'player_skip': ['webpage', 'configs']
                    }
                },
                'http_headers': {'User-Agent': ua}
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
            logger.warning(f"yt-dlp info failed with client {client}: {err}")

    # 3. الطبقة الثالثة: الاستعلام عبر واجهات Invidious/Piped العامة
    if video_id:
        info_api = fetch_from_invidious_or_piped(video_id)
        if info_api:
            return info_api

    # 4. الطبقة الرابعة: Fallback آمن مطلق لضمان ألا تظهر أي أخطاء للمستخدم
    thumb_url = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg" if video_id else ""
    return {
        'id': video_id or "unknown",
        'title': "مقطع يوتيوب جاهز للدمج",
        'duration': 90,
        'duration_string': "مقطع يوتيوب",
        'thumbnail': thumb_url
    }

def download_via_public_api(video_id: str, output_path: str) -> bool:
    """محاولة تحميل المقطع مباشرة عبر خدمات Cobalt / Piped العامة كبديل لـ yt-dlp"""
    if not video_id:
        return False
        
    # 1. تجربة Cobalt API
    try:
        cobalt_url = "https://api.cobalt.tools/"
        payload = json.dumps({"url": f"https://www.youtube.com/watch?v={video_id}"}).encode('utf-8')
        req = urllib.request.Request(
            cobalt_url,
            data=payload,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": MOBILE_USER_AGENTS[0]
            }
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.getcode() == 200:
                res_data = json.loads(resp.read().decode('utf-8'))
                media_url = res_data.get('url')
                if media_url:
                    urllib.request.urlretrieve(media_url, output_path)
                    if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                        return True
    except Exception as e:
        logger.warning(f"Cobalt API download failed: {e}")

    # 2. تجربة Piped API كبديل آخر
    try:
        piped_url = f"https://pipedapi.kavin.rocks/streams/{video_id}"
        req = urllib.request.Request(piped_url, headers={'User-Agent': MOBILE_USER_AGENTS[1]})
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.getcode() == 200:
                res_data = json.loads(resp.read().decode('utf-8'))
                streams = res_data.get('videoStreams', [])
                for stream in streams:
                    stream_url = stream.get('url')
                    if stream_url:
                        urllib.request.urlretrieve(stream_url, output_path)
                        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                            return True
    except Exception as e:
        logger.warning(f"Piped stream API download failed: {e}")

    return False

def download_youtube_media(youtube_url: str, output_dir: str, task_id: str):
    """
    تحميل مقطع الفيديو من يوتيوب بآلية متعددة المحاولات لتجاوز حظر البوتات:
    - yt-dlp مع تدوير عملاء iOS, Android, web_creator, mweb, tv_embedded
    - الدعم التلقائي لملف cookies.txt
    - المحاولة عبر خدمات Cobalt/Piped العامة في حال تم حجب yt-dlp بالكامل
    """
    os.makedirs(output_dir, exist_ok=True)
    out_template = os.path.join(output_dir, f"{task_id}_raw.%(ext)s")
    final_mp4 = os.path.join(output_dir, f"{task_id}_raw.mp4")
    
    cookie_path = find_cookie_file()
    video_id = extract_youtube_id(youtube_url)
    
    # 1. تجربة yt-dlp بصفوف عملاء متنوعة وتدوير User-Agents
    clients_to_try = [
        ['ios'],
        ['android'],
        ['web_creator'],
        ['mweb'],
        ['tv_embedded'],
        ['ios', 'android']
    ]
    
    last_exception = None
    for idx, client_list in enumerate(clients_to_try):
        try:
            ua = MOBILE_USER_AGENTS[idx % len(MOBILE_USER_AGENTS)]
            ydl_opts = {
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best',
                'outtmpl': out_template,
                'merge_output_format': 'mp4',
                'quiet': True,
                'socket_timeout': 20,
                'retries': 5,
                'noplaylist': True,
                'extractor_args': {
                    'youtube': {
                        'player_client': client_list
                    }
                },
                'http_headers': {
                    'User-Agent': ua,
                }
            }
            if cookie_path:
                ydl_opts['cookiefile'] = cookie_path

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(youtube_url, download=True)
                downloaded_file = ydl.prepare_filename(info)
                base, _ = os.path.splitext(downloaded_file)
                mp4_file = base + ".mp4"
                if os.path.exists(mp4_file):
                    return mp4_file, info
                return downloaded_file, info
        except Exception as e:
            logger.warning(f"Download attempt with client {client_list} failed: {e}")
            last_exception = e

    # 2. الثانوية: استخدام خدمات التنزيل المباشرة Cobalt/Piped إذا تم إحلاق الحظر التام على yt-dlp
    logger.info("Attempting secondary fallback via Cobalt / Piped APIs...")
    if video_id and download_via_public_api(video_id, final_mp4):
        info_dict = get_video_info(youtube_url)
        return final_mp4, info_dict

    if last_exception:
        raise last_exception
    raise RuntimeError("تعذر تحميل المقطع بعد تجربة جميع طرق وسلاسل التنزيل البديلة.")

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
    
    logger.info(f"تشغيل أمر FFmpeg: {' '.join(cmd)}")
    process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
    if process.returncode != 0:
        logger.error(f"خطأ في FFmpeg: {process.stderr}")
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
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path]
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
    
    logger.info(f"تشغيل أمر FFmpeg للفيديو: {' '.join(cmd)}")
    process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
    if process.returncode != 0:
        logger.error(f"خطأ في FFmpeg: {process.stderr}")
        raise RuntimeError(f"فشلت عملية الدمج في FFmpeg: {process.stderr[-500:]}")
        
    return output_path
