import os
import time
import uuid
import shutil
import asyncio
from typing import Optional, Dict
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from processor import get_video_info, download_youtube_media, create_shorts_video

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMP_DIR = os.path.join(BASE_DIR, "temp")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
STATIC_DIR = os.path.join(BASE_DIR, "static")

os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

app = FastAPI(title="أجر اليوتيوب — صانع شورتس يوتيوب الدمجي", version="2.0")

@app.get("/")
async def get_root_page():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

@app.get("/image")
@app.get("/Image")
async def get_image_page():
    return FileResponse(os.path.join(STATIC_DIR, "image.html"))

@app.get("/video")
@app.get("/Video")
async def get_video_page():
    return FileResponse(os.path.join(STATIC_DIR, "video.html"))

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
    """جلب معلومات مقطع اليوتيوب ومعاينته قبل البدء"""
    try:
        data = get_video_info(url)
        return {"success": True, "info": data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"تعذر جلب معلومات المقطع. تأكد من صحة الرابط: {str(e)}")

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
    try:
        cleanup_old_files()
        tasks_db[task_id]["status"] = "downloading"
        tasks_db[task_id]["message"] = "جاري تحميل مقطع اليوتيوب..."
        
        # 1. تحميل مقطع اليوتيوب
        raw_video_path, video_info = download_youtube_media(youtube_url, TEMP_DIR, task_id)
        
        tasks_db[task_id]["status"] = "processing"
        tasks_db[task_id]["message"] = "جاري دمج الفيديو والصورة وتفرغ الشاشة السوداء بدقة (9:16)..."
        
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
            end_time=end_time
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
    try:
        cleanup_old_files()
        tasks_db[task_id]["status"] = "downloading"
        tasks_db[task_id]["message"] = "جاري تحميل مقطع اليوتيوب الأساسي ومقطع الخلفية..."
        
        # 1. تحميل المقاطع
        primary_video_path, _ = download_youtube_media(primary_url, TEMP_DIR, task_id + "_primary")
        bg_video_path, _ = download_youtube_media(bg_url, TEMP_DIR, task_id + "_bg")
        
        tasks_db[task_id]["status"] = "processing"
        tasks_db[task_id]["message"] = "جاري دمج الفيديوهات والمزامنة وتفريغ الشاشة السوداء..."
        
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
