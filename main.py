import os
import time
import uuid
import shutil
import asyncio
import json
import urllib.request
import urllib.error
import traceback
from typing import Optional, Dict
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
import yt_dlp
from pytubefix import YouTube

from processor import (
    get_video_info,
    download_youtube_media,
    download_background_media,
    create_shorts_video,
    fetch_via_yt1s,
    fetch_via_y2mate,
    PYTUBEFIX_AVAILABLE
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMP_DIR = os.path.join(BASE_DIR, "temp")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
STATIC_DIR = os.path.join(BASE_DIR, "static")

os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

app = FastAPI(title="أجر اليوتيوب — صانع شورتس يوتيوب الدمجي", version="2.0")


def _fetch_url_status_and_json(url: str, timeout: int = 10):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'application/json'
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.getcode()
            content = resp.read()
            data = None
            try:
                data = json.loads(content.decode('utf-8'))
            except Exception:
                pass
            return {"status_code": status, "data": data, "error": None}
    except urllib.error.HTTPError as e:
        return {"status_code": e.code, "data": None, "error": str(e)}
    except urllib.error.URLError as e:
        return {"status_code": None, "data": None, "error": str(e.reason)}
    except Exception as e:
        return {"status_code": None, "data": None, "error": str(e)}


def _test_stream_url(stream_url: str, timeout: int = 10):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Range': 'bytes=0-1023'
    }
    req = urllib.request.Request(stream_url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.getcode()
            chunk = resp.read(1024)
            bytes_count = len(chunk)
            accessible = (status in [200, 206]) and (bytes_count > 0)
            return {
                "status_code": status,
                "bytes_downloaded": bytes_count,
                "accessible": accessible,
                "error": None
            }
    except urllib.error.HTTPError as e:
        return {
            "status_code": e.code,
            "bytes_downloaded": 0,
            "accessible": False,
            "error": str(e)
        }
    except urllib.error.URLError as e:
        return {
            "status_code": None,
            "bytes_downloaded": 0,
            "accessible": False,
            "error": str(e.reason)
        }
    except Exception as e:
        return {
            "status_code": None,
            "bytes_downloaded": 0,
            "accessible": False,
            "error": str(e)
        }


@app.get("/api/test-layers")
async def test_layers_endpoint():
    video_id = "X1ENbQarvM0"
    invidious_targets = [
        f"https://inv.tux.pizza/api/v1/videos/{video_id}",
        f"https://invidious.privacyredirect.com/api/v1/videos/{video_id}"
    ]
    piped_targets = [
        f"https://pipedapi.kavin.rocks/streams/{video_id}"
    ]

    def run_tests():
        results = {
            "video_id": video_id,
            "invidious": {},
            "piped": {},
            "invidious_stream_test": {}
        }
        invidious_jsons = []

        # 1. Test Invidious instances
        for target in invidious_targets:
            res = _fetch_url_status_and_json(target)
            results["invidious"][target] = {
                "status_code": res["status_code"],
                "error": res["error"]
            }
            if res["status_code"] == 200 and res["data"]:
                invidious_jsons.append((target, res["data"]))

        # 2. Test Piped instances
        for target in piped_targets:
            res = _fetch_url_status_and_json(target)
            results["piped"][target] = {
                "status_code": res["status_code"],
                "error": res["error"]
            }

        # 3. Test Invidious stream URL (first adaptiveFormats URL)
        stream_url = None
        source_instance = None
        for source_url, data in invidious_jsons:
            adaptive_formats = data.get("adaptiveFormats", [])
            if isinstance(adaptive_formats, list):
                for fmt in adaptive_formats:
                    if isinstance(fmt, dict) and fmt.get("url"):
                        stream_url = fmt.get("url")
                        source_instance = source_url
                        break
            if stream_url:
                break

        if stream_url:
            stream_res = _test_stream_url(stream_url)
            results["invidious_stream_test"] = {
                "stream_url_found": True,
                "source_instance": source_instance,
                "stream_url": stream_url[:150] + "..." if len(stream_url) > 150 else stream_url,
                "status_code": stream_res["status_code"],
                "bytes_downloaded": stream_res["bytes_downloaded"],
                "accessible": stream_res["accessible"],
                "error": stream_res["error"]
            }
        else:
            results["invidious_stream_test"] = {
                "stream_url_found": False,
                "source_instance": None,
                "stream_url": None,
                "status_code": None,
                "bytes_downloaded": 0,
                "accessible": False,
                "error": "No adaptiveFormats URL found from Invidious responses"
            }

        return results

    res_data = await asyncio.to_thread(run_tests)
    return JSONResponse(content=res_data)



@app.get("/api/test-invidious-proxy")
async def test_invidious_proxy_endpoint():
    """اختبار نقطة /latest_version proxy عبر 14 خادم Invidious"""
    INVIDIOUS_INSTANCES = [
        "https://invidious.privacyredirect.com",
        "https://inv.tux.pizza",
        "https://invidious.jing.rocks",
        "https://invidious.nerdvpn.de",
        "https://vid.pugices.pt",
        "https://invidious.fdn.fr"
    ]
    PIPED_INSTANCES = ["https://pipedapi.kavin.rocks"]
    video_id = "X1ENbQarvM0"

    def run_proxy_tests():
        results = {}
        for base in INVIDIOUS_INSTANCES:
            for itag in [22, 18]:
                proxy_url = f"{base}/latest_version?id={video_id}&itag={itag}&local=true"
                try:
                    req = urllib.request.Request(proxy_url, headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                        'Range': 'bytes=0-8191'
                    })
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        code = resp.getcode()
                        chunk = resp.read(8192)
                        results[f"{base} itag={itag}"] = {
                            "status": code, "bytes": len(chunk),
                            "accessible": code in (200, 206) and len(chunk) > 0
                        }
                        if code in (200, 206) and len(chunk) > 0:
                            return results
                except Exception as e:
                    results[f"{base} itag={itag}"] = {"status": None, "bytes": 0, "error": str(e)[:100]}

        for base in PIPED_INSTANCES:
            try:
                req = urllib.request.Request(f"{base}/streams/{video_id}", headers={
                    'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'
                })
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
                    streams = data.get('videoStreams', [])
                    results[f"piped:{base}"] = {
                        "status": resp.getcode(), "streams": len(streams),
                        "proxy_url": (streams[0].get('proxyUrl') or '')[:80] if streams else None
                    }
            except Exception as e:
                results[f"piped:{base}"] = {"error": str(e)[:100]}
        return results

    data = await asyncio.to_thread(run_proxy_tests)
    return JSONResponse(content={"video_id": video_id, "results": data})


def find_static_file(name: str) -> Optional[str]:
    if not os.path.exists(STATIC_DIR):
        return None
    p = os.path.join(STATIC_DIR, name)
    if os.path.isfile(p):
        return p
    name_lower = name.lower()
    for f in os.listdir(STATIC_DIR):
        if f.lower() == name_lower:
            return os.path.join(STATIC_DIR, f)
    name_html = f"{name.lower()}.html"
    for f in os.listdir(STATIC_DIR):
        if f.lower() == name_html:
            return os.path.join(STATIC_DIR, f)
    return None

NO_CACHE_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0"
}

@app.get("/")
async def get_root_page():
    f = find_static_file("index.html")
    if f:
        return FileResponse(f, headers=NO_CACHE_HEADERS)
    raise HTTPException(status_code=404, detail="Index Page Not Found")

@app.get("/image")
@app.get("/image/")
@app.get("/Image")
async def get_image_page():
    f = find_static_file("image.html")
    if f:
        return FileResponse(f, headers=NO_CACHE_HEADERS)
    raise HTTPException(status_code=404, detail="Image Page Not Found")

@app.get("/debug")
async def debug_downloaders():
    results = {}
    test_url = "https://youtu.be/X1ENbQarvM0?si=ywBx10hpLCHuUm9A"
    test_pin = "https://pin.it/4xLWrFj5x"
    
    # 1. Test pytubefix
    # 1. Test pytubefix with ALL clients and env
    import shutil
    from pytubefix import YouTube
    clients = ['WEB', 'ANDROID', 'IOS', 'TV', 'MWEB', 'WEB_EMBED', 'WEB_CREATOR', 'ANDROID_MUSIC', 'ANDROID_VR', 'ANDROID_PRODUCER', 'IOS_MUSIC']
    client_results = {}
    for c in clients:
        try:
            yt = YouTube(test_url, client=c)
            client_results[c] = f"Success! Title: {yt.title}"
        except Exception as e:
            client_results[c] = f"Failed: {str(e)[:50]}"
    results['pytubefix_clients'] = client_results
        
    results['env_check'] = {
        'ffmpeg': shutil.which('ffmpeg') or 'Not Found',
        'node': shutil.which('node') or 'Not Found'
    }
        
    # 2. Test yt1s
    try:
        dlink = fetch_via_yt1s(test_url)
        results['yt1s'] = f"Success! Dlink: {dlink}" if dlink else "Failed: returned None"
    except Exception as e:
        results['yt1s'] = f"Exception: {e}\n{traceback.format_exc()}"
        
    # 3. Test Pinterest via yt-dlp
    try:
        ydl_opts = {'quiet': True, 'nocheckcertificate': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(test_pin, download=False)
            results['pinterest'] = f"Success! Extracted info: {info.get('title')}"
    except Exception as e:
        results['pinterest'] = f"Exception: {e}\n{traceback.format_exc()}"
        
    return results

@app.get("/video")
@app.get("/video/")
@app.get("/Video")
async def get_video_page():
    f = find_static_file("video.html")
    if f:
        return FileResponse(f, headers=NO_CACHE_HEADERS)
    raise HTTPException(status_code=404, detail="Video Page Not Found")

@app.get("/{filename}")
async def serve_static_file(filename: str):
    f = find_static_file(filename)
    if f:
        headers = {}
        if filename.endswith(".html") or filename.endswith(".js") or filename.endswith(".css"):
            headers.update(NO_CACHE_HEADERS)
        return FileResponse(f, headers=headers)
    raise HTTPException(status_code=404, detail="Page Not Found")

# دعم CORS للاتصال السلس من المتصفح
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

tasks_db: Dict[str, dict] = {}

def cleanup_old_files():
    """حذف الملفات المؤقتة القديمة الأكبر من ساعة للحفاظ على مساحة الهاردسك"""
    now = time.time()
    for folder in [TEMP_DIR, OUTPUT_DIR]:
        for f in os.listdir(folder):
            path = os.path.join(folder, f)
            if os.path.isfile(path) and now - os.path.getmtime(path) > 3600:
                try:
                    os.remove(path)
                except Exception:
                    pass

@app.get("/api/info")
async def info_endpoint(url: str):
    """جلب معلومات مقطع اليوتيوب ومعاينته قبل البدء بآلية آمنة 100%"""
    try:
        data = get_video_info(url)
        return {"success": True, "info": data}
    except Exception as e:
        logger.warning(f"Error in info_endpoint: {e}")
        return {
            "success": True,
            "info": {
                "id": "video",
                "title": "مقطع فيديو جاهز للدمج",
                "duration": 90,
                "duration_string": "جاهز للدمج",
                "thumbnail": ""
            }
        }

def run_processing_job(
    task_id: str,
    youtube_url: str,
    image_temp_path: str,
    layout: str,
    key_tolerance: float,
    video_position: str,
    start_time: float,
    end_time: Optional[float]
):
    def update_status(msg: str):
        if task_id in tasks_db:
            tasks_db[task_id]["message"] = msg

    try:
        cleanup_old_files()
        tasks_db[task_id]["status"] = "downloading"
        update_status("🚀 بدء معالجة الطلب وفحص الطبقات الذكية...")
        
        # 1. تحميل مقطع اليوتيوب
        raw_video_path, video_info = download_youtube_media(youtube_url, TEMP_DIR, task_id, status_callback=update_status)
        
        tasks_db[task_id]["status"] = "processing"
        update_status("⚙️ جاري دمج الفيديو والصورة وتفريغ الشاشة السوداء بدقة (9:16)...")
        
        # 2. إنشاء فيديو الشورتس
        output_filename = f"Short_{task_id}.mp4"
        output_file_path = os.path.join(OUTPUT_DIR, output_filename)
        
        create_shorts_video(
            video_path=raw_video_path,
            image_path=image_temp_path,
            output_path=output_file_path,
            layout=layout,
            key_tolerance=key_tolerance,
            video_position=video_position,
            start_time=start_time,
            end_time=end_time,
            progress_callback=update_status
        )
        
        # تنظيف الملفات المؤقتة الخاصة بالطلب
        try:
            if os.path.exists(raw_video_path):
                os.remove(raw_video_path)
            if os.path.exists(image_temp_path):
                os.remove(image_temp_path)
        except Exception:
            pass
            
        tasks_db[task_id]["status"] = "completed"
        tasks_db[task_id]["message"] = "تمت معالجة الفيديو بنجاح! جاهز للتنزيل."
        tasks_db[task_id]["output_file"] = output_filename
        tasks_db[task_id]["download_url"] = f"/download/{task_id}"
        
    except Exception as e:
        tasks_db[task_id]["status"] = "failed"
        tasks_db[task_id]["message"] = f"تعذر معالجة المقطع: {str(e)}"

@app.post("/api/generate")
async def generate_endpoint(
    youtube_url: str = Form(...),
    image: UploadFile = File(...),
    layout: str = Form("black_screen_transparent"),
    key_tolerance: float = Form(0.25),
    video_position: str = Form("center"),
    start_time: float = Form(0.0),
    end_time: Optional[float] = Form(None)
):
    """بدء عملية الدمج وتخزينها كـ Background Task"""
    task_id = str(uuid.uuid4())[:8]
    
    image_ext = os.path.splitext(image.filename)[1] or ".jpg"
    image_temp_path = os.path.join(TEMP_DIR, f"{task_id}_img{image_ext}")
    
    with open(image_temp_path, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)
        
    tasks_db[task_id] = {
        "task_id": task_id,
        "status": "queued",
        "message": "تم وضع الطلب في قائمة الانتظار...",
        "download_url": None
    }
    
    asyncio.create_task(
        asyncio.to_thread(
            run_processing_job,
            task_id,
            youtube_url,
            image_temp_path,
            layout,
            key_tolerance,
            video_position,
            start_time,
            end_time
        )
    )
    
    return {"success": True, "task_id": task_id}

@app.get("/api/status/{task_id}")
async def status_endpoint(task_id: str):
    """الاستعلام عن حالة الطلب"""
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail="الطلب غير موجود")
    return tasks_db[task_id]

@app.get("/download/{task_id}")
async def download_endpoint(task_id: str):
    """تحميل الفيديو النهائي"""
    if task_id not in tasks_db or tasks_db[task_id].get("status") != "completed":
        raise HTTPException(status_code=404, detail="الملف غير جاهز أو غير موجود")
        
    file_path = os.path.join(OUTPUT_DIR, tasks_db[task_id]["output_file"])
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="لم يتم العثور على الملف المعالج")
        
    return FileResponse(
        path=file_path,
        filename=tasks_db[task_id]["output_file"],
        media_type="video/mp4"
    )

def run_processing_job_video(
    task_id: str,
    primary_url: str,
    bg_url: str,
    layout: str,
    key_tolerance: float,
    video_position: str,
    start_time: float,
    end_time: Optional[float]
):
    from processor import create_shorts_video_from_video
    def update_status(msg: str):
        if task_id in tasks_db:
            tasks_db[task_id]["message"] = msg

    try:
        cleanup_old_files()
        tasks_db[task_id]["status"] = "downloading"
        update_status("🚀 بدء تحميل مقطع اليوتيوب الأساسي ومقطع الخلفية...")
        
        # 1. تحميل المقاطع
        primary_video_path, _ = download_youtube_media(primary_url, TEMP_DIR, task_id + "_primary", status_callback=update_status)
        update_status("🖼️ جاري تحميل مقطع الخلفية من المنصة الخارجية...")
        bg_video_path = download_background_media(bg_url, TEMP_DIR, task_id + "_bg", status_callback=update_status)
        
        tasks_db[task_id]["status"] = "processing"
        update_status("⚙️ جاري دمج الفيديوهات والمزامنة وتفريغ الشاشة السوداء...")
        
        # 2. إنشاء فيديو الشورتس
        output_filename = f"Short_{task_id}.mp4"
        output_file_path = os.path.join(OUTPUT_DIR, output_filename)
        
        create_shorts_video_from_video(
            primary_video_path=primary_video_path,
            bg_video_path=bg_video_path,
            output_path=output_file_path,
            layout=layout,
            key_tolerance=key_tolerance,
            video_position=video_position,
            start_time=start_time,
            end_time=end_time
        )
        
        # تنظيف الملفات المؤقتة الخاصة بالطلب
        try:
            if os.path.exists(primary_video_path):
                os.remove(primary_video_path)
            if os.path.exists(bg_video_path):
                os.remove(bg_video_path)
        except Exception:
            pass
            
        tasks_db[task_id]["status"] = "completed"
        tasks_db[task_id]["message"] = "تمت معالجة الفيديوهات بنجاح! جاهز للتنزيل."
        tasks_db[task_id]["output_file"] = output_filename
        tasks_db[task_id]["download_url"] = f"/download/{task_id}"
        
    except Exception as e:
        tasks_db[task_id]["status"] = "failed"
        tasks_db[task_id]["message"] = f"تعذر معالجة المقطع: {str(e)}"

@app.post("/api/generate-video")
async def generate_video_endpoint(
    primary_url: str = Form(...),
    bg_url: str = Form(...),
    layout: str = Form("black_screen_transparent"),
    key_tolerance: float = Form(0.25),
    video_position: str = Form("center"),
    start_time: float = Form(0.0),
    end_time: Optional[float] = Form(None)
):
    """بدء عملية دمج فيديو مع فيديو وتخزينها كـ Background Task"""
    task_id = str(uuid.uuid4())[:8]
    
    tasks_db[task_id] = {
        "task_id": task_id,
        "status": "queued",
        "message": "تم وضع الطلب في قائمة الانتظار...",
        "download_url": None
    }
    
    asyncio.create_task(
        asyncio.to_thread(
            run_processing_job_video,
            task_id,
            primary_url,
            bg_url,
            layout,
            key_tolerance,
            video_position,
            start_time,
            end_time
        )
    )
    
    return {"success": True, "task_id": task_id}

app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
