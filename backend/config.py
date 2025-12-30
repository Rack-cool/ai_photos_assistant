# config.py - 云部署优化版
import os
from pathlib import Path


class Config:
    # ========== 前端配置 ==========
    WEB_TITLE = "AI智能选片助手"
    WEB_DESCRIPTION = "自动检测照片质量，支持语义搜索"
    WEB_FAVICON = "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"
    # ========== 从环境变量读取配置 ==========
    # 性能优化配置
    MAX_WORKERS = int(os.getenv("MAX_WORKERS", "2"))  # 云环境减少并发
    BATCH_SIZE = int(os.getenv("BATCH_SIZE", "10"))  # 减小批次大小
    IMAGE_CACHE_SIZE = int(os.getenv("IMAGE_CACHE_SIZE", "30"))

    # ========== 质量检测阈值 ==========
    BLUR_THRESHOLD = float(os.getenv("BLUR_THRESHOLD", "30.0"))
    OVEREXPOSURE_THRESHOLD = float(os.getenv("OVEREXPOSURE_THRESHOLD", "0.95"))
    UNDEREXPOSURE_THRESHOLD = float(os.getenv("UNDEREXPOSURE_THRESHOLD", "0.05"))

    # ========== 图像处理配置 ==========
    MAX_IMAGE_SIZE = int(os.getenv("MAX_IMAGE_SIZE", "500000"))  # 云环境减少
    RESIZE_SCALE = float(os.getenv("RESIZE_SCALE", "0.25"))  # 缩小更多

    # ========== 语义搜索配置 ==========
    SEARCH_BATCH_SIZE = int(os.getenv("SEARCH_BATCH_SIZE", "25"))
    SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.4"))

    # ========== 路径配置 ==========
    # 云部署环境下使用正确的路径
    BASE_DIR = Path(__file__).parent

    if os.getenv("RAILWAY_ENVIRONMENT"):
        # Railway环境使用持久化目录
        DATA_DIR = Path("/data")
        # 确保静态文件目录存在
        STATIC_DIR = DATA_DIR / "frontend"
    else:
        DATA_DIR = BASE_DIR / "data"
        STATIC_DIR = BASE_DIR / "frontend"

    # 确保目录存在
    DATA_DIR.mkdir(exist_ok=True)
    PHOTOS_DIR = DATA_DIR / "photos"
    PHOTOS_DIR.mkdir(exist_ok=True)
    CHROMA_DB_DIR = DATA_DIR / "chroma_db"
    CHROMA_DB_DIR.mkdir(exist_ok=True)
    STATIC_DIR.mkdir(exist_ok=True)

    # ========== 服务器配置 ==========
    API_HOST = os.getenv("API_HOST", "0.0.0.0")
    API_PORT = int(os.getenv("PORT", "8001"))  # Railway自动分配
    WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
    WEB_PORT = int(os.getenv("WEB_PORT", "3000"))

    # ========== 模型配置 ==========
    CLIP_MODEL_NAME = os.getenv("CLIP_MODEL_NAME", "ViT-B/32")
    USE_GPU = os.getenv("USE_GPU", "false").lower() == "true"

    # ========== 前端配置 ==========
    # 获取前端URL，用于CORS
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

    # ========== 云存储配置 ==========
    # 如果使用云存储，可以配置S3等
    USE_CLOUD_STORAGE = os.getenv("USE_CLOUD_STORAGE", "false").lower() == "true"
    CLOUD_STORAGE_BUCKET = os.getenv("CLOUD_STORAGE_BUCKET", "")

    # ========== 临时文件配置 ==========
    TEMP_UPLOAD_DIR = DATA_DIR / "temp_uploads"
    TEMP_UPLOAD_DIR.mkdir(exist_ok=True)


# 全局配置实例
config = Config()