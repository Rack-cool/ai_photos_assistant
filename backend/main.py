import os
import glob
import time
import json
import numpy as np
from typing import Dict, List, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import config
from photo_quality_checker import PhotoQualityChecker
from semantic_search import PhotoSemanticSearch
import uuid
import shutil
from fastapi import UploadFile, File

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.bool_, np.bool)):
            return bool(obj)
        elif isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        else:
            return super().default(obj)


def serialize_for_json(obj: Any) -> Any:
    if isinstance(obj, (np.bool_, np.bool)):
        return bool(obj)
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: serialize_for_json(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [serialize_for_json(item) for item in obj]
    else:
        return obj


# 初始化应用
app = FastAPI(
    title="AI Photo Assistant API",
    description="AI智能选片助手后端API",
    version="2.0.0"
)


@app.post("/upload_photos")
async def upload_photos(files: List[UploadFile] = File(...)):
    """上传照片文件"""
    try:
        # 创建唯一的上传目录
        upload_id = str(uuid.uuid4())
        upload_dir = config.TEMP_UPLOAD_DIR / upload_id
        upload_dir.mkdir(parents=True, exist_ok=True)

        uploaded_files = []
        for file in files:
            # 验证文件类型
            if not file.filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                continue

            # 保存文件
            file_path = upload_dir / file.filename
            with open(file_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)

            uploaded_files.append(str(file_path))

        if not uploaded_files:
            return {"status": "error", "message": "没有有效的图片文件"}

        return {
            "status": "success",
            "upload_id": upload_id,
            "uploaded_count": len(uploaded_files),
            "folder_path": str(upload_dir),
            "files": uploaded_files
        }

    except Exception as e:
        return {"status": "error", "message": f"上传失败: {str(e)}"}


@app.get("/clear_cache")
async def clear_cache():
    """清理缓存和临时文件"""
    try:
        # 清理处理任务
        processing_tasks.clear()

        # 清理临时上传目录
        if os.path.exists(config.TEMP_UPLOAD_DIR):
            shutil.rmtree(config.TEMP_UPLOAD_DIR, ignore_errors=True)
            config.TEMP_UPLOAD_DIR.mkdir(exist_ok=True)

        # 清理质量检查器缓存
        quality_checker.clear_cache()

        # 清空语义搜索索引
        semantic_search.clear_collection()

        # 清空内存数据
        processed_photos.clear()
        QUALIFIED_PHOTOS.clear()

        return {"status": "success", "message": "缓存已清理"}
    except Exception as e:
        return {"status": "error", "message": f"清理失败: {str(e)}"}
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

quality_checker = PhotoQualityChecker()
semantic_search = PhotoSemanticSearch()

processed_photos = {}
QUALIFIED_PHOTOS = []
processing_tasks: Dict[str, Dict] = {}


class FolderRequest(BaseModel):
    folder_path: str


class SearchQuery(BaseModel):
    query: str
    top_k: int = 10


def get_image_files(folder_path: str) -> List[str]:
    image_extensions = [".jpg", ".jpeg", ".png", ".bmp", ".JPG", ".JPEG", ".PNG", ".BMP"]
    photo_paths = []

    for ext in image_extensions:
        files = glob.glob(os.path.join(folder_path, f"*{ext}"), recursive=False)
        photo_paths.extend(files)

    photo_paths = list(set(photo_paths))
    photo_paths.sort()
    return photo_paths


def process_batch_photos(batch_paths: List[str]) -> List[dict]:
    batch_results = []
    for path in batch_paths:
        try:
            result = quality_checker.check_photo_quality(path)
            batch_results.append(result)
        except Exception as e:
            print(f"处理失败 {path}: {e}")
            batch_results.append({
                "image_path": path,
                "is_defective": False,
                "defect_types": [],
                "details": {}
            })
    return batch_results


def background_processing(task_id: str, folder_path: str):
    try:
        processing_tasks[task_id].update({
            "status": "initializing",
            "progress": 0,
            "message": "正在扫描文件夹..."
        })

        photo_paths = get_image_files(folder_path)
        total = len(photo_paths)

        if total == 0:
            processing_tasks[task_id].update({
                "status": "error",
                "message": "文件夹中未找到图片文件！"
            })
            return

        processing_tasks[task_id].update({
            "total": total,
            "message": f"找到 {total} 张照片，开始处理..."
        })

        quality_results = []
        batch_size = config.BATCH_SIZE

        for i in range(0, total, batch_size):
            batch_paths = photo_paths[i:i + batch_size]
            current = min(i + batch_size, total)

            progress = int(current / total * 100)
            processing_tasks[task_id].update({
                "status": "processing",
                "progress": progress,
                "current": current,
                "message": f"正在处理 {current}/{total} 张照片..."
            })

            with ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as executor:
                sub_batch_size = max(1, batch_size // config.MAX_WORKERS)
                futures = []

                for j in range(0, len(batch_paths), sub_batch_size):
                    sub_batch = batch_paths[j:j + sub_batch_size]
                    futures.append(executor.submit(process_batch_photos, sub_batch))

                for future in as_completed(futures):
                    try:
                        batch_results = future.result()
                        quality_results.extend(batch_results)
                    except Exception as e:
                        print(f"批次处理失败: {e}")

        quality_checker.clear_cache()

        qualified_photos = [r["image_path"] for r in quality_results if not r["is_defective"]]

        indexed_count = 0
        if qualified_photos:
            processing_tasks[task_id].update({
                "message": f"正在建立语义索引 ({len(qualified_photos)} 张合格照片)..."
            })

            search_batch_size = config.SEARCH_BATCH_SIZE
            for i in range(0, len(qualified_photos), search_batch_size):
                batch = qualified_photos[i:i + search_batch_size]
                clear_flag = (i == 0)
                indexed_count += semantic_search.index_photos(batch, clear_existing=clear_flag)

                idx_progress = int((i + len(batch)) / len(qualified_photos) * 30)
                processing_tasks[task_id].update({
                    "progress": 70 + idx_progress,
                    "message": f"语义索引进度: {min(i + search_batch_size, len(qualified_photos))}/{len(qualified_photos)}"
                })

        global processed_photos, QUALIFIED_PHOTOS
        processed_photos = {r["image_path"]: r for r in quality_results}
        QUALIFIED_PHOTOS = qualified_photos

        total_photos = total
        bad_photos = sum(1 for r in quality_results if r["is_defective"])
        qualified_photos_count = len(qualified_photos)

        result_data = serialize_for_json({
            "total_photos": total_photos,
            "bad_photos": bad_photos,
            "qualified_photos": qualified_photos_count,
            "indexed_photos": indexed_count,
            "photos": [{
                "image_path": r["image_path"],
                "filename": os.path.basename(r["image_path"]),
                "is_defective": bool(r["is_defective"]),
                "defect_types": r["defect_types"]
            } for r in quality_results]
        })

        processing_tasks[task_id].update({
            "status": "completed",
            "progress": 100,
            "message": "处理完成！",
            "result": result_data
        })

    except Exception as e:
        processing_tasks[task_id].update({
            "status": "error",
            "message": f"处理失败: {str(e)}"
        })


# API端点
@app.get("/")
async def root():
    return {
        "message": "AI智能选片助手API",
        "version": "2.0.0",
        "usage": "请访问 /demo 查看Web界面",
        "endpoints": {
            "/demo": "Web界面",
            "/process_photos": "POST处理照片",
            "/process_photos_async": "异步处理",
            "/processing_status/{task_id}": "查询进度",
            "/search_photos": "搜索照片"
        }
    }


@app.get("/demo")
async def demo():
    """提供简单的Web界面"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>AI智能选片助手</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .container { max-width: 800px; margin: auto; }
            .card { border: 1px solid #ddd; padding: 20px; margin: 20px 0; border-radius: 8px; }
            input, button { padding: 10px; margin: 5px; }
            button { background: #4CAF50; color: white; border: none; cursor: pointer; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>AI智能选片助手</h1>
            <p>说明：由于云环境限制，请直接使用本地文件夹路径处理照片</p>

            <div class="card">
                <h3>处理照片文件夹</h3>
                <p>输入本地文件夹路径（如：D:\\Photos\\Wedding）</p>
                <input type="text" id="folderPath" placeholder="文件夹路径" style="width: 80%">
                <button onclick="processPhotos()">开始处理</button>
            </div>

            <div class="card" id="progress" style="display:none">
                <h3>处理进度</h3>
                <div id="progressBar"></div>
                <div id="progressText"></div>
            </div>

            <div class="card">
                <h3>搜索照片</h3>
                <input type="text" id="searchQuery" placeholder="例如：海滩、婚礼、风景...">
                <button onclick="searchPhotos()">搜索</button>
                <div id="searchResults"></div>
            </div>

            <div class="card" id="results" style="display:none">
                <h3>处理结果</h3>
                <div id="stats"></div>
                <div id="photoList"></div>
            </div>
        </div>

        <script>
            let currentTaskId = null;

            async function processPhotos() {
                const path = document.getElementById('folderPath').value;
                if (!path) return alert('请输入文件夹路径');

                const response = await fetch('/process_photos_async', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({folder_path: path})
                });

                const result = await response.json();
                if (result.status === 'started') {
                    currentTaskId = result.task_id;
                    document.getElementById('progress').style.display = 'block';
                    checkProgress();
                } else {
                    alert('启动失败: ' + result.message);
                }
            }

            async function checkProgress() {
                const response = await fetch('/processing_status/' + currentTaskId);
                const status = await response.json();

                document.getElementById('progressBar').innerHTML = 
                    `<div style="background:#4CAF50;height:20px;width:${status.progress}%"></div>`;
                document.getElementById('progressText').innerHTML = 
                    `${status.message} (${status.progress}%)`;

                if (status.status === 'completed') {
                    showResults(status.result);
                } else if (status.status === 'error') {
                    alert('处理错误: ' + status.message);
                } else {
                    setTimeout(checkProgress, 2000);
                }
            }

            function showResults(result) {
                document.getElementById('stats').innerHTML = `
                    总照片: ${result.total_photos}<br>
                    合格照片: ${result.qualified_photos}<br>
                    废片: ${result.bad_photos}
                `;
                document.getElementById('results').style.display = 'block';
            }

            async function searchPhotos() {
                const query = document.getElementById('searchQuery').value;
                if (!query) return alert('请输入搜索词');

                const response = await fetch('/search_photos', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({query: query, top_k: 10})
                });

                const result = await response.json();
                let html = '<h4>搜索结果：</h4>';
                result.results.forEach(r => {
                    html += `<div>${r.filename} (相似度: ${Math.round(r.similarity_score*100)}%)</div>`;
                });
                document.getElementById('searchResults').innerHTML = html;
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.post("/process_photos")
async def process_photos_sync(request: FolderRequest):
    folder_path = request.folder_path

    if not os.path.exists(folder_path):
        return {"status": "error", "message": "文件夹路径不存在！"}

    photo_paths = get_image_files(folder_path)
    if not photo_paths:
        return {"status": "error", "message": "文件夹中未找到图片文件！"}

    print(f"开始处理 {len(photo_paths)} 张照片...")

    quality_results = []
    for i, photo_path in enumerate(photo_paths):
        if i % 100 == 0:
            print(f"处理进度: {i}/{len(photo_paths)}")
        result = quality_checker.check_photo_quality(photo_path)
        quality_results.append(result)

    qualified_photos = [r["image_path"] for r in quality_results if not r["is_defective"]]

    indexed_count = semantic_search.index_photos(qualified_photos) if qualified_photos else 0

    global processed_photos, QUALIFIED_PHOTOS
    processed_photos = {r["image_path"]: r for r in quality_results}
    QUALIFIED_PHOTOS = qualified_photos

    total_photos = len(photo_paths)
    bad_photos = sum(1 for r in quality_results if r["is_defective"])
    qualified_photos_count = len(qualified_photos)

    return serialize_for_json({
        "status": "success",
        "total_photos": total_photos,
        "bad_photos": bad_photos,
        "qualified_photos": qualified_photos_count,
        "indexed_photos": indexed_count,
        "photos": [{
            "image_path": r["image_path"],
            "filename": os.path.basename(r["image_path"]),
            "is_defective": bool(r["is_defective"]),
            "defect_types": r["defect_types"]
        } for r in quality_results]
    })


@app.post("/process_photos_async")
async def process_photos_async(request: FolderRequest, background_tasks: BackgroundTasks):
    folder_path = request.folder_path

    if not os.path.exists(folder_path):
        return {"status": "error", "message": "文件夹路径不存在！"}

    task_id = str(int(time.time() * 1000))

    processing_tasks[task_id] = {
        "task_id": task_id,
        "status": "pending",
        "progress": 0,
        "current": 0,
        "total": 0,
        "message": "任务已创建，等待开始...",
        "result": None
    }

    background_tasks.add_task(background_processing, task_id, folder_path)

    return {
        "status": "started",
        "task_id": task_id,
        "message": "照片处理已开始，请使用task_id查询进度"
    }


@app.get("/processing_status/{task_id}")
async def get_processing_status(task_id: str):
    if task_id not in processing_tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    task_info = processing_tasks[task_id]
    serialized = json.loads(json.dumps(task_info, cls=NumpyEncoder))
    return serialized


@app.post("/search_photos")
async def search_photos(query: SearchQuery):
    if not QUALIFIED_PHOTOS:
        raise HTTPException(status_code=400, detail="请先处理照片文件夹")

    results = semantic_search.search_photos(query.query, query.top_k)
    return {"results": results}


@app.get("/get_photo/{photo_path:path}")
async def get_photo(photo_path: str):
    if not os.path.exists(photo_path):
        raise HTTPException(status_code=404, detail="照片不存在")
    return FileResponse(photo_path)


@app.get("/web")
async def web_interface():
    """提供完整的前端界面"""
    html_content = """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>AI智能选片助手 - 完整版</title>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; }

            .container { max-width: 1200px; margin: 0 auto; padding: 20px; }

            .card { background: white; border-radius: 16px; padding: 30px; margin-bottom: 30px; 
                    box-shadow: 0 10px 30px rgba(0,0,0,0.1); }

            h1 { color: white; margin-bottom: 20px; text-align: center; font-size: 2.5rem; }
            h2 { color: #333; margin-bottom: 15px; font-size: 1.8rem; }

            .folder-input { display: flex; gap: 10px; margin: 20px 0; }
            .folder-input input { flex: 1; padding: 12px; border: 2px solid #e4e6f1; 
                                  border-radius: 8px; font-size: 1rem; }
            .btn { padding: 12px 24px; background: #667eea; color: white; border: none; 
                   border-radius: 8px; cursor: pointer; font-size: 1rem; font-weight: 600; }
            .btn:hover { background: #5a6fd8; }

            .progress-bar { height: 10px; background: #e4e6f1; border-radius: 5px; 
                            margin: 20px 0; overflow: hidden; }
            .progress-fill { height: 100%; background: linear-gradient(90deg, #667eea, #764ba2); 
                             width: 0%; transition: width 0.3s; }

            .stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; 
                          margin: 20px 0; }
            .stat-box { padding: 20px; border-radius: 8px; text-align: center; }
            .stat-box.total { background: #e3f2fd; }
            .stat-box.qualified { background: #e8f5e9; }
            .stat-box.defective { background: #ffebee; }
            .stat-box.indexed { background: #f3e5f5; }

            .photo-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); 
                          gap: 15px; margin-top: 20px; }
            .photo-item { position: relative; border-radius: 8px; overflow: hidden; cursor: pointer; }
            .photo-item img { width: 100%; height: 150px; object-fit: cover; }

            .search-box { display: flex; gap: 10px; margin: 20px 0; }
            .search-box input { flex: 1; padding: 12px; border: 2px solid #e4e6f1; 
                                border-radius: 8px; font-size: 1rem; }

            .search-results { max-height: 500px; overflow-y: auto; margin-top: 20px; }
            .search-result { display: flex; align-items: center; gap: 15px; padding: 15px; 
                             background: #f8f9ff; border-radius: 8px; margin-bottom: 10px; }
            .result-image { width: 80px; height: 80px; object-fit: cover; border-radius: 8px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1><i class="fas fa-camera"></i> AI智能选片助手</h1>

            <div class="card">
                <h2><i class="fas fa-folder-open"></i> 处理照片文件夹</h2>
                <p>输入本地文件夹路径（如：D:\Photos\Wedding）</p>
                <div class="folder-input">
                    <input type="text" id="folderPath" placeholder="文件夹路径">
                    <button class="btn" onclick="processPhotos()">开始处理</button>
                </div>

                <div id="progressContainer" style="display: none;">
                    <div class="progress-bar">
                        <div class="progress-fill" id="progressFill"></div>
                    </div>
                    <div id="progressText">0%</div>
                    <div id="progressMessage">准备开始...</div>
                </div>
            </div>

            <div class="card" id="resultsCard" style="display: none;">
                <h2><i class="fas fa-chart-bar"></i> 处理结果</h2>
                <div class="stats-grid" id="statsGrid"></div>

                <div style="margin: 20px 0;">
                    <button class="btn" onclick="filterPhotos('all')">全部</button>
                    <button class="btn" onclick="filterPhotos('qualified')">合格</button>
                    <button class="btn" onclick="filterPhotos('defective')">废片</button>
                </div>

                <div class="photo-grid" id="photoGrid"></div>
            </div>

            <div class="card">
                <h2><i class="fas fa-search"></i> 语义搜索</h2>
                <div class="search-box">
                    <input type="text" id="searchInput" placeholder="例如：球、海滩、婚礼...">
                    <button class="btn" onclick="searchPhotos()">搜索</button>
                </div>

                <div class="search-results" id="searchResults">
                    <p style="text-align: center; color: #666; padding: 20px;">
                        请输入搜索词开始查找照片
                    </p>
                </div>
            </div>
        </div>

        <script>
            let currentTaskId = null;
            let processedPhotos = [];

            async function processPhotos() {
                const path = document.getElementById('folderPath').value.trim();
                if (!path) {
                    alert('请输入文件夹路径！');
                    return;
                }

                // 显示进度条
                const progressContainer = document.getElementById('progressContainer');
                const progressFill = document.getElementById('progressFill');
                const progressText = document.getElementById('progressText');
                const progressMessage = document.getElementById('progressMessage');

                progressContainer.style.display = 'block';
                progressFill.style.width = '0%';
                progressText.textContent = '0%';
                progressMessage.textContent = '正在启动处理...';

                try {
                    // 开始异步处理
                    const response = await fetch('/process_photos_async', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ folder_path: path })
                    });

                    const result = await response.json();

                    if (result.status === 'started') {
                        currentTaskId = result.task_id;
                        progressMessage.textContent = '处理已开始，正在处理照片...';
                        checkProgress();
                    } else {
                        alert('处理启动失败: ' + result.message);
                    }
                } catch (error) {
                    alert('请求失败: ' + error.message);
                }
            }

            async function checkProgress() {
                try {
                    const response = await fetch('/processing_status/' + currentTaskId);
                    const status = await response.json();

                    const progressFill = document.getElementById('progressFill');
                    const progressText = document.getElementById('progressText');
                    const progressMessage = document.getElementById('progressMessage');

                    const progress = status.progress || 0;
                    progressFill.style.width = progress + '%';
                    progressText.textContent = progress + '%';
                    progressMessage.textContent = status.message || '处理中...';

                    if (status.status === 'completed') {
                        displayResults(status.result);
                        progressMessage.textContent = '处理完成！';
                        setTimeout(() => {
                            document.getElementById('progressContainer').style.display = 'none';
                        }, 2000);
                    } else if (status.status === 'error') {
                        alert('处理失败: ' + status.message);
                    } else {
                        setTimeout(checkProgress, 2000);
                    }
                } catch (error) {
                    console.error('获取进度失败:', error);
                    setTimeout(checkProgress, 3000);
                }
            }

            function displayResults(result) {
                // 显示结果卡片
                document.getElementById('resultsCard').style.display = 'block';

                // 更新统计信息
                const statsHtml = `
                    <div class="stat-box total">
                        <h3>${result.total_photos || 0}</h3>
                        <p>总照片数</p>
                    </div>
                    <div class="stat-box qualified">
                        <h3>${result.qualified_photos || 0}</h3>
                        <p>合格照片</p>
                    </div>
                    <div class="stat-box defective">
                        <h3>${result.bad_photos || 0}</h3>
                        <p>废片数量</p>
                    </div>
                    <div class="stat-box indexed">
                        <h3>${result.indexed_photos || 0}</h3>
                        <p>已索引</p>
                    </div>
                `;
                document.getElementById('statsGrid').innerHTML = statsHtml;

                // 存储照片数据
                processedPhotos = result.photos || [];
                renderPhotos();
            }

            function renderPhotos(filter = 'all') {
                const photoGrid = document.getElementById('photoGrid');

                if (processedPhotos.length === 0) {
                    photoGrid.innerHTML = '<p style="text-align: center; padding: 20px; color: #666;">暂无照片数据</p>';
                    return;
                }

                let filteredPhotos = processedPhotos;
                if (filter === 'qualified') {
                    filteredPhotos = processedPhotos.filter(p => !p.is_defective);
                } else if (filter === 'defective') {
                    filteredPhotos = processedPhotos.filter(p => p.is_defective);
                }

                let html = '';
                filteredPhotos.forEach(photo => {
                    // 使用后端API获取图片
                    const imageUrl = `/get_photo/${encodeURIComponent(photo.image_path)}`;

                    html += `
                        <div class="photo-item">
                            <img src="${imageUrl}" alt="${photo.filename}" 
                                 onerror="this.onerror=null; this.src='data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjE1MCIgdmlld0JveD0iMCAwIDIwMCAxNTAiIGZpbGw9IiNmMGYwZjAiPjxyZWN0IHdpZHRoPSIyMDAiIGhlaWdodD0iMTUwIi8+PHRleHQgeD0iMTAwIiB5PSI3NSIgZm9udC1mYW1pbHk9IkFyaWFsIiBmb250LXNpemU9IjE0IiBmaWxsPSIjYWFhIiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBkeT0iLjNlbSI+PGltYWdlIC8+PC90ZXh0Pjwvc3ZnPgo='">
                            ${photo.is_defective ? '<div style="position: absolute; top: 10px; right: 10px; background: red; color: white; padding: 3px 8px; border-radius: 10px; font-size: 12px;">废片</div>' : ''}
                        </div>
                    `;
                });

                photoGrid.innerHTML = html;
            }

            function filterPhotos(type) {
                renderPhotos(type);
            }

            async function searchPhotos() {
                const query = document.getElementById('searchInput').value.trim();
                if (!query) {
                    alert('请输入搜索词！');
                    return;
                }

                const searchResults = document.getElementById('searchResults');
                searchResults.innerHTML = '<p style="text-align: center; padding: 20px; color: #666;">正在搜索...</p>';

                try {
                    const response = await fetch('/search_photos', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ query: query, top_k: 10 })
                    });

                    const result = await response.json();

                    if (result.results && result.results.length > 0) {
                        let html = '';
                        result.results.forEach(item => {
                            const imageUrl = `/get_photo/${encodeURIComponent(item.path)}`;
                            const similarityPercent = Math.round(item.similarity_score * 100);

                            html += `
                                <div class="search-result">
                                    <img src="${imageUrl}" alt="${item.filename}" class="result-image"
                                         onerror="this.onerror=null; this.src='data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iODAiIGhlaWdodD0iODAiIHZpZXdCb3g9IjAgMCA4MCA4MCIgZmlsbD0iI2YwZjBmMCI+PHJlY3Qgd2lkdGg9IjgwIiBoZWlnaHQ9IjgwIi8+PHRleHQgeD0iNDAiIHk9IjQwIiBmb250LWZhbWlseT0iQXJpYWwiIGZvbnQtc2l6ZT0iMTIiIGZpbGw9IiNhYWEiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGR5PSIuM2VtIj48aW1hZ2UgLz48L3RleHQ+PC9zdmc+Cg==';">
                                    <div>
                                        <h4>${item.filename}</h4>
                                        <p>相似度: <strong>${similarityPercent}%</strong></p>
                                    </div>
                                </div>
                            `;
                        });
                        searchResults.innerHTML = html;
                    } else {
                        searchResults.innerHTML = '<p style="text-align: center; padding: 20px; color: #666;">没有找到相关照片</p>';
                    }
                } catch (error) {
                    searchResults.innerHTML = '<p style="text-align: center; padding: 20px; color: red;">搜索失败: ' + error.message + '</p>';
                }
            }

            // 初始化
            window.onload = function() {
                // 可以添加一些默认路径
                document.getElementById('folderPath').value = '${config.PHOTOS_DIR}'.replace(/\\/g, '\\\\');
            };
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.get("/get_photo/{photo_path:path}")
async def get_photo(photo_path: str):
    """获取照片文件 - 修复版"""
    try:
        # 解码路径
        from urllib.parse import unquote
        photo_path = unquote(photo_path)

        # 检查文件是否存在
        if os.path.exists(photo_path):
            return FileResponse(photo_path)

        # 尝试在PHOTOS_DIR中查找
        filename = os.path.basename(photo_path)
        local_path = os.path.join(config.PHOTOS_DIR, filename)
        if os.path.exists(local_path):
            return FileResponse(local_path)

        # 尝试在临时上传目录中查找
        temp_photos = glob.glob(os.path.join(config.TEMP_UPLOAD_DIR, "*", "*"))
        for temp_path in temp_photos:
            if os.path.basename(temp_path) == filename:
                return FileResponse(temp_path)

        # 返回404
        raise HTTPException(status_code=404, detail="照片不存在")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取照片失败: {str(e)}")
# 静态文件服务
import shutil

for file in ["index.html", "style.css", "app.js"]:
    src = os.path.join(config.BASE_DIR, file)
    dst = os.path.join(config.STATIC_DIR, file)
    if os.path.exists(src) and not os.path.exists(dst):
        try:
            shutil.copy2(src, dst)
            print(f"✅ 复制 {file} 到 frontend 目录")
        except Exception as e:
            print(f"❌ 复制 {file} 失败: {e}")

app.mount("/frontend", StaticFiles(directory=config.STATIC_DIR), name="frontend")

if __name__ == "__main__":
    import uvicorn

    print(f"AI智能选片助手后端启动中...")
    print(f"API地址: http://{config.API_HOST}:{config.API_PORT}")
    print(f"Web界面: http://{config.API_HOST}:{config.API_PORT}/demo")
    print(f"静态文件: {config.STATIC_DIR}")

    uvicorn.run(
        app,
        host=config.API_HOST,
        port=config.API_PORT,
        log_level="info"
    )