import os
import subprocess
import logging
import json
import uuid
import yt_dlp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("processor")

def get_video_info(youtube_url: str):
    """جلب معلومات مقطع اليوتيوب بدون تحميله"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        },
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(youtube_url, download=False)
        return {
            'id': info.get('id'),
            'title': info.get('title'),
            'duration': info.get('duration'),
            'duration_string': f"{int(info.get('duration') // 60)} دقيقة و {int(info.get('duration') % 60)} ثانية" if info.get('duration') else "غير محدد",
            'thumbnail': info.get('thumbnail')
        }

def download_youtube_media(youtube_url: str, output_dir: str, task_id: str):
    """تحميل مقطع الفيديو والصوت من يوتيوب بأعلى جودة متوفرة بصيغة mp4"""
    os.makedirs(output_dir, exist_ok=True)
    out_template = os.path.join(output_dir, f"{task_id}_raw.%(ext)s")
    
    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': out_template,
        'merge_output_format': 'mp4',
        'quiet': False,
        'socket_timeout': 15,
        'retries': 3,
        'noplaylist': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(youtube_url, download=True)
        downloaded_file = ydl.prepare_filename(info)
        base, _ = os.path.splitext(downloaded_file)
        mp4_file = base + ".mp4"
        if os.path.exists(mp4_file):
            return mp4_file, info
        return downloaded_file, info

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
    
    # تحديد تموضع overlay (الأعلى، المنتصف، الأسفل)
    overlay_pos = "(W-w)/2:(H-h)/2"
    if video_position == "top":
        overlay_pos = "(W-w)/2:120"
    elif video_position == "bottom":
        overlay_pos = "(W-w)/2:H-h-120"
        
    filter_complex = ""
    
    if layout == "black_screen_transparent" or layout == "colorkey_transparent":
        # تفريغ اللون الأسود بالشفافية النظيفة مع إمكانية تحكم في درجة الحساسية (key_tolerance)
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
    import json
    
    # الحصول على مدة المقطعين
    def get_duration(path):
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path]
        try:
            return float(subprocess.check_output(cmd).decode("utf-8").strip())
        except:
            return 10.0 # قيمة افتراضية في حالة الفشل

    dur1 = get_duration(primary_video_path)
    dur2 = get_duration(bg_video_path)
    
    if end_time and end_time > start_time:
        dur1 = min(dur1, end_time - start_time)
        
    # حساب معامل السرعة للخلفية
    speed_factor = 1.0
    if dur2 < dur1 and dur2 > 0:
        speed_factor = dur1 / dur2
    
    # تحديد تموضع overlay (الأعلى، المنتصف، الأسفل)
    overlay_pos = "(W-w)/2:(H-h)/2"
    if video_position == "top":
        overlay_pos = "(W-w)/2:120"
    elif video_position == "bottom":
        overlay_pos = "(W-w)/2:H-h-120"
        
    filter_complex = ""
    
    # تجهيز مقطع الخلفية مع إبطاء السرعة: setpts=PTS*speed_factor
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
        "-map", "0:a?", # أخذ الصوت من الفيديو الأساسي فقط
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
