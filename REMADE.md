项目概述
这是一个帮助摄影师高效管理和检索照片库的AI智能选片助手。系统能够自动识别技术性废片（模糊、闭眼、曝光不当），并提供基于自然语言的语义搜索功能，让用户可以使用日常语言描述来查找照片。

设计思路
系统架构

┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│    Web前端       │    │    FastAPI后端   │    │    核心算法      │
│  (HTML/JS/CSS)  │◄──►│ (Python/UVicorn)│◄──►│   (CLIP/OpenCV) │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                          ┌─────────────────┐
                          │   向量数据库      │
                          │   (ChromaDB)    │
                          └─────────────────┘
核心功能实现
1. 智能质检与筛选
图像模糊检测: 使用拉普拉斯算子计算图像方差，低于阈值判定为模糊

曝光不当检测: 分析图像直方图，计算过曝和欠曝像素比例

人物闭眼检测: 预留接口（实际部署时可集成人脸识别模型）

2. 语义搜索功能
CLIP模型: 使用OpenAI的CLIP（Contrastive Language-Image Pre-training）模型

向量检索: 使用ChromaDB存储图像嵌入向量，支持余弦相似度搜索

自然语言理解: 将文本查询转换为向量，在向量空间中查找最相似的图像

项目结构

ai-photo-assistant/
│
├── config.py              # 配置文件
├── main.py               # FastAPI主应用
├── photo_quality_checker.py # 照片质量检测模块
├── semantic_search.py    # 语义搜索模块
├── run.py               # 启动脚本
├── start.bat            # Windows启动脚本
├── index.html           # Web前端页面
├── README.md            # 项目文档
├── requirements.txt     # Python依赖
│
├── data/                # 数据目录
│   └── photos/          # 照片存储目录
├── static/              # 静态文件目录
│   └── index.html       # 前端页面副本
└── chroma_db/           # 向量数据库目录
安装与运行
环境要求
Python 3.8+

4GB+ 内存

2GB+ 可用磁盘空间

快速开始
1. 克隆项目
bash
git clone <项目地址>
cd ai-photo-assistant
2. 安装依赖
bash
pip install -r requirements.txt
3. 准备照片数据集
将您的照片（至少500张）复制到 data/photos/ 目录，或使用以下命令下载示例数据集：


# 创建数据目录
mkdir -p data/photos

# 下载示例数据集（需自行准备或使用公开数据集）
# 示例：使用Kaggle婚礼照片数据集
# 注意：需要先安装kaggle API并配置凭据
4. 运行系统
方式一：使用启动脚本（推荐）

python run.py
方式二：直接启动

# 启动后端API服务
python main.py

# 在另一个终端启动前端服务（如果需要）
cd static && python -m http.server 8080
方式三：Windows用户
双击运行 start.bat 文件

5. 访问应用
前端界面: http://localhost:8080

API文档: http://localhost:8001/docs

使用指南
1. 加载照片文件夹
打开Web界面

点击"选择文件夹"按钮

输入照片文件夹的完整路径（如 C:\Photos\Wedding 或 /home/user/photos）

点击"开始处理"按钮

2. 查看质检结果
系统会自动分析所有照片，识别并标记有质量问题的照片

可以切换查看"全部照片"、"合格照片"或"废片"

支持按缺陷类型筛选（模糊、过曝、欠曝）

3. 语义搜索照片
在搜索框中输入自然语言描述，例如：

"穿白色婚纱的新娘"

"日落时分的海滩"

"正在微笑的孩子"

点击搜索按钮

系统会返回语义上最相关的照片

4. 批量操作
支持批量隐藏废片

支持批量导出合格照片

支持重新处理文件夹

技术特性
性能优化
并行处理: 支持多线程批量处理照片

智能缓存: 图像处理结果缓存，减少重复计算

增量索引: 只对新照片进行语义索引

可配置参数
所有参数可在 config.py 中调整：

质量检测阈值

并发处理数量

图像处理参数

服务器配置

扩展性
支持添加新的质量检测算法

支持更换不同的CLIP模型

支持自定义向量数据库

示例效果
质检界面

📊 处理统计：
总照片数: 500张
合格照片: 420张 (84%)
废片数量: 80张 (16%)
  - 模糊: 35张
  - 过曝: 25张
  - 欠曝: 20张
搜索结果
text
搜索: "婚礼上的第一支舞"
找到 12 个相关结果:
1. dance_001.jpg (相似度: 0.89)
2. dance_002.jpg (相似度: 0.85)
3. dance_003.jpg (相似度: 0.82)
...
高级配置
启用GPU加速
在 config.py 中设置：

python
USE_GPU = True  # 如果系统有NVIDIA GPU且已安装CUDA
调整质量阈值
python
# 模糊检测阈值（越低越严格）
BLUR_THRESHOLD = 25.0

# 曝光阈值
OVEREXPOSURE_THRESHOLD = 0.90  # 过曝
UNDEREXPOSURE_THRESHOLD = 0.10  # 欠曝
性能调优
python
# 增加并发数（提高处理速度）
MAX_WORKERS = 16

# 增大批次大小
BATCH_SIZE = 100
故障排除
常见问题
CLIP模型加载失败

原因: 网络问题或磁盘空间不足
解决方案: 手动下载模型或检查网络连接
内存不足

原因: 同时处理过多大尺寸图片
解决方案: 减小BATCH_SIZE或开启图像缩放
搜索无结果

原因: 语义索引未成功创建
解决方案: 重新处理文件夹或检查ChromaDB日志
日志查看
# 查看后端日志
tail -f logs/app.log

# 查看处理进度
curl http://localhost:8001/stats
开发指南
添加新的质量检测器
在 photo_quality_checker.py 中添加新的检测方法

在 check_photo_quality 方法中集成新检测器

更新前端界面显示新的缺陷类型

集成其他AI模型
在 semantic_search.py 中替换CLIP模型

更新嵌入向量生成方法

调整相似度计算逻辑

许可证
MIT License

致谢
OpenAI CLIP 团队

ChromaDB 向量数据库

FastAPI 开发团队

OpenCV 计算机视觉库

项目状态
✅ 核心功能完成
✅ Web界面可用
✅ 文档完整
🔄 持续优化中

版本: 2.0.0
最后更新: 2025年12月
维护者: zhaojie