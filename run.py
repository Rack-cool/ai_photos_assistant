# run.py - 启动脚本
import os
import sys
import webbrowser
import time
import subprocess
from pathlib import Path


def main():
    print("🎨 AI智能选片助手 v2.0")
    print("=" * 60)

    # 创建必要的目录
    print("📁 创建目录结构...")
    os.makedirs("data/photos", exist_ok=True)
    os.makedirs("backend/frontend", exist_ok=True)
    os.makedirs("chroma_db", exist_ok=True)

    # 复制前端文件
    frontend_files = ['index.html', 'style.css', 'app.js']
    for file in frontend_files:
        if os.path.exists(file) and not os.path.exists(f"backend/frontend/{file}"):
            import shutil
            shutil.copy2(file, f"backend/frontend/{file}")

    print("✅ 目录结构已创建")

    # 检查照片目录
    import glob
    photos = glob.glob("data/photos/*.jpg") + \
             glob.glob("data/photos/*.jpeg") + \
             glob.glob("data/photos/*.png")

    if photos:
        print(f"📸 找到 {len(photos)} 张测试照片")
    else:
        print("⚠️  照片目录为空，请将照片放入: data/photos/")
        print("   您可以在程序运行后添加照片")

    print("\n" + "=" * 60)
    print("🚀 启动系统...")
    print("=" * 60)

    # 显示访问地址
    print("后端API地址: http://localhost:8001")
    print("前端访问地址: http://localhost:3000")
    print("\n" + "=" * 60)
    print("按 Ctrl+C 停止服务")
    print("=" * 60 + "\n")

    # 启动后端服务（通过命令行调用uvicorn）
    try:
        # 使用subprocess启动uvicorn
        process = subprocess.Popen([
            sys.executable, "-m", "uvicorn",
            "main:app",
            "--host", "0.0.0.0",
            "--port", "8001",
            "--reload"
        ])

        # 等待进程结束
        process.wait()

    except KeyboardInterrupt:
        print("\n👋 服务已停止")
    except Exception as e:
        print(f"❌ 启动失败: {e}")


if __name__ == "__main__":
    main()