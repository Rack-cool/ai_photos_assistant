// 前端应用主逻辑
class PhotoAssistantApp {
    constructor() {
        this.apiBaseUrl = this.detectApiUrl();
        this.photos = [];
        this.selectedFiles = [];
        this.currentTaskId = null;
        this.progressInterval = null;
        this.currentUploadId = null;

        this.init();
    }

    init() {
        // 初始化事件监听器
        this.bindEvents();
        // 测试API连接
        this.testApiConnection();
    }

    detectApiUrl() {
    // 自动检测API地址
    const hostname = window.location.hostname;
    const port = window.location.port;

    // 如果是通过前端页面访问（端口3000），则API在8001端口
    if (port === "3000" || port === "") {
        return "http://localhost:8001";
    }

    // 其他情况使用当前主机和端口
    return `${window.location.protocol}//${window.location.hostname}:8001`;
}

    async testApiConnection() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/`, {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' }
            });

            if (response.ok) {
                this.updateApiStatus(true);
                console.log('✅ API连接正常');
            } else {
                this.updateApiStatus(false);
            }
        } catch (error) {
            this.updateApiStatus(false);
            console.error('❌ API连接失败:', error);
        }
    }

    updateApiStatus(isOnline) {
        const statusElement = document.getElementById('apiStatus');
        const urlElement = document.getElementById('apiUrl');

        if (isOnline) {
            statusElement.textContent = '在线';
            statusElement.className = 'status online';
            urlElement.textContent = this.apiBaseUrl;
        } else {
            statusElement.textContent = '离线';
            statusElement.className = 'status offline';
            urlElement.textContent = this.apiBaseUrl;
        }
    }

    bindEvents() {
        // 上传区域点击
        document.getElementById('uploadArea').addEventListener('click', () => {
            document.getElementById('fileInput').click();
        });

        // 文件选择
        document.getElementById('fileInput').addEventListener('change', (e) => {
            this.handleFileSelect(e.target.files);
        });

        // 拖放上传
        const uploadArea = document.getElementById('uploadArea');
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.style.borderColor = '#764ba2';
            uploadArea.style.background = '#f8f9ff';
        });

        uploadArea.addEventListener('dragleave', () => {
            uploadArea.style.borderColor = '#667eea';
            uploadArea.style.background = '';
        });

        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.style.borderColor = '#667eea';
            uploadArea.style.background = '';
            this.handleFileSelect(e.dataTransfer.files);
        });

        // 开始处理按钮
        document.getElementById('processBtn').addEventListener('click', () => {
            this.startProcessing();
        });

        // 清除按钮
        document.getElementById('clearBtn').addEventListener('click', () => {
            this.clearAll();
        });

        // 搜索按钮
        document.getElementById('searchBtn').addEventListener('click', () => {
            this.performSearch();
        });

        // 搜索输入框回车
        document.getElementById('searchInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.performSearch();
            }
        });

        // 示例搜索按钮
        document.querySelectorAll('.example-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const query = e.target.dataset.query;
                document.getElementById('searchInput').value = query;
                this.performSearch();
            });
        });

        // 筛选标签
        document.querySelectorAll('.filter-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                // 移除所有active类
                document.querySelectorAll('.filter-btn').forEach(b => {
                    b.classList.remove('active');
                });
                // 添加active类到当前按钮
                e.target.classList.add('active');
                // 应用筛选
                this.filterPhotos(e.target.dataset.filter);
            });
        });

        // 缺陷类型筛选
        document.querySelectorAll('.filter-checkbox input').forEach(checkbox => {
            checkbox.addEventListener('change', () => {
                this.applyDefectFilters();
            });
        });

        // 测试API按钮
        document.getElementById('testApiBtn').addEventListener('click', () => {
            this.testApiConnection();
        });

        // 报告问题按钮
        document.getElementById('reportIssue').addEventListener('click', (e) => {
            e.preventDefault();
            this.reportIssue();
        });

        // 模态框关闭
        document.querySelector('.close').addEventListener('click', () => {
            this.closeModal();
        });

        // 点击模态框外部关闭
        window.addEventListener('click', (e) => {
            const modal = document.getElementById('previewModal');
            if (e.target === modal) {
                this.closeModal();
            }
        });
    }

    handleFileSelect(files) {
        if (files.length === 0) return;

        this.selectedFiles = Array.from(files);

        // 更新UI显示选择的文件数
        const uploadArea = document.getElementById('uploadArea');
        uploadArea.innerHTML = `
            <i class="fas fa-check-circle fa-3x" style="color: #4CAF50;"></i>
            <p>已选择 ${this.selectedFiles.length} 个文件</p>
            <p class="upload-hint">点击"开始处理"按钮进行分析</p>
            <input type="file" id="fileInput" multiple accept=".jpg,.jpeg,.png,.JPG,.JPEG,.PNG">
        `;

        // 显示文件列表预览
        this.showFileListPreview();

        // 重新绑定文件输入事件
        document.getElementById('fileInput').addEventListener('change', (e) => {
            this.handleFileSelect(e.target.files);
        });
    }

    showFileListPreview() {
        const container = document.createElement('div');
        container.className = 'file-list-preview';

        this.selectedFiles.slice(0, 5).forEach(file => {
            const item = document.createElement('div');
            item.className = 'file-item';
            item.innerHTML = `
                <i class="fas fa-image"></i>
                <span>${file.name}</span>
                <span class="file-size">(${this.formatFileSize(file.size)})</span>
            `;
            container.appendChild(item);
        });

        if (this.selectedFiles.length > 5) {
            const moreItem = document.createElement('div');
            moreItem.className = 'file-item';
            moreItem.innerHTML = `<i class="fas fa-ellipsis-h"></i> <span>... 还有 ${this.selectedFiles.length - 5} 个文件</span>`;
            container.appendChild(moreItem);
        }

        const uploadArea = document.getElementById('uploadArea');
        uploadArea.appendChild(container);
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    async startProcessing() {
        if (this.selectedFiles.length === 0) {
            alert('请先选择照片文件！');
            return;
        }

        // 显示进度条
        document.getElementById('progressContainer').style.display = 'block';
        document.getElementById('progressFill').style.width = '0%';
        document.getElementById('progressText').textContent = '0%';
        document.getElementById('progressDetails').textContent = '准备上传文件...';

        try {
        // 创建FormData并添加文件
        const formData = new FormData();
        this.selectedFiles.forEach(file => {
            formData.append('files', file);  // 修改这里：'photos' -> 'files'
        });

        // 上传文件
        document.getElementById('progressDetails').textContent = '正在上传文件...';
        const uploadResponse = await fetch(`${this.apiBaseUrl}/upload_photos`, {
            method: 'POST',
            body: formData
            // 注意：不要手动设置 Content-Type，浏览器会自动设置 multipart/form-data
        });

            if (!uploadResponse.ok) {
                const errorText = await uploadResponse.text();
                throw new Error(`上传失败: ${errorText}`);
            }

            const uploadResult = await uploadResponse.json();

            if (uploadResult.status === 'success') {
                this.currentUploadId = uploadResult.upload_id;
                document.getElementById('progressDetails').textContent = `上传成功，开始处理 ${uploadResult.uploaded_count} 张照片...`;

                // 使用上传的文件夹路径开始处理
                const processResponse = await fetch(`${this.apiBaseUrl}/process_photos_async`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        folder_path: uploadResult.folder_path
                    })
                });

                const processResult = await processResponse.json();

                if (processResult.status === 'started') {
                    this.currentTaskId = processResult.task_id;
                    this.startProgressTracking();
                } else {
                    throw new Error('处理启动失败');
                }
            } else {
                throw new Error(uploadResult.message || '上传失败');
            }

        } catch (error) {
            console.error('处理失败:', error);
            document.getElementById('progressDetails').textContent = `错误: ${error.message}`;
            document.getElementById('progressFill').style.width = '0%';
            document.getElementById('progressText').textContent = '0%';
        }
    }

    startProgressTracking() {
        if (this.progressInterval) {
            clearInterval(this.progressInterval);
        }

        this.progressInterval = setInterval(async () => {
            try {
                const response = await fetch(`${this.apiBaseUrl}/processing_status/${this.currentTaskId}`);
                const status = await response.json();

                // 更新进度
                const progress = status.progress || 0;
                document.getElementById('progressFill').style.width = `${progress}%`;
                document.getElementById('progressText').textContent = `${progress}%`;
                document.getElementById('progressDetails').textContent = status.message || '处理中...';

                // 如果处理完成
                if (status.status === 'completed') {
                    clearInterval(this.progressInterval);
                    this.progressInterval = null;

                    // 显示结果
                    this.displayResults(status.result);
                    document.getElementById('progressDetails').textContent = '处理完成！';

                    // 延迟隐藏进度条
                    setTimeout(() => {
                        document.getElementById('progressContainer').style.display = 'none';
                    }, 2000);
                } else if (status.status === 'error') {
                    clearInterval(this.progressInterval);
                    this.progressInterval = null;
                    document.getElementById('progressDetails').textContent = `错误: ${status.message}`;
                }

            } catch (error) {
                console.error('获取进度失败:', error);
            }
        }, 2000); // 每2秒更新一次
    }

    displayResults(result) {
        // 更新统计信息
        const statsHtml = `
            <div class="stats-grid">
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
            </div>
        `;

        document.getElementById('resultStats').innerHTML = statsHtml;

        // 显示照片
        this.photos = result.photos || [];
        this.renderPhotos();
    }

    renderPhotos() {
        const photoGrid = document.getElementById('photoGrid');

        if (this.photos.length === 0) {
            photoGrid.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-images fa-3x"></i>
                    <p>还没有照片，请先上传</p>
                </div>
            `;
            return;
        }

        photoGrid.innerHTML = '';

        this.photos.forEach(photo => {
            const photoItem = this.createPhotoElement(photo);
            photoGrid.appendChild(photoItem);
        });
    }

    createPhotoElement(photo) {
        const div = document.createElement('div');
        div.className = 'photo-item';

        // 从服务器获取缩略图
        const thumbnailUrl = `${this.apiBaseUrl}/get_photo/${encodeURIComponent(photo.image_path)}`;

        let badgeHtml = '';
        if (photo.is_defective && photo.defect_types && photo.defect_types.length > 0) {
            const defectIcons = {
                'blur': 'fa-blur',
                'overexposed': 'fa-sun',
                'underexposed': 'fa-moon'
            };

            const defectNames = {
                'blur': '模糊',
                'overexposed': '过曝',
                'underexposed': '欠曝'
            };

            const defectType = photo.defect_types[0];
            badgeHtml = `
                <div class="photo-badge">
                    <i class="fas ${defectIcons[defectType] || 'fa-exclamation-triangle'}"></i>
                    ${defectNames[defectType] || defectType}
                </div>
            `;
        }

        div.innerHTML = `
            <img src="${thumbnailUrl}" alt="${photo.filename}"
                 onerror="this.src='data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjE1MCIgdmlld0JveD0iMCAwIDIwMCAxNTAiIGZpbGw9IiNmMGYwZjAiPjxyZWN0IHdpZHRoPSIyMDAiIGhlaWdodD0iMTUwIi8+PHRleHQgeD0iMTAwIiB5PSI3NSIgZm9udC1mYW1pbHk9IkFyaWFsIiBmb250LXNpemU9IjE0IiBmaWxsPSIjYWFhIiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBkeT0iLjNlbSI+Jm5ic3A7PC90ZXh0Pjwvc3ZnPg=='">
            ${badgeHtml}
        `;

        // 点击预览
        div.addEventListener('click', () => {
            this.previewPhoto(photo);
        });

        return div;
    }

    previewPhoto(photo) {
        const modal = document.getElementById('previewModal');
        const image = document.getElementById('previewImage');
        const imageName = document.getElementById('imageName');
        const imageStatus = document.getElementById('imageStatus');
        const imageDefects = document.getElementById('imageDefects');

        // 设置图片
        const imageUrl = `${this.apiBaseUrl}/get_photo/${encodeURIComponent(photo.image_path)}`;
        image.src = imageUrl;
        imageName.textContent = photo.filename;

        // 设置状态
        if (photo.is_defective) {
            imageStatus.innerHTML = `<span style="color: #dc3545;"><i class="fas fa-times-circle"></i> 废片</span>`;

            if (photo.defect_types && photo.defect_types.length > 0) {
                const defectNames = {
                    'blur': '图像模糊',
                    'overexposed': '曝光过度',
                    'underexposed': '曝光不足'
                };

                const defectList = photo.defect_types.map(defect => {
                    return `<li><i class="fas fa-exclamation-circle"></i> ${defectNames[defect] || defect}</li>`;
                }).join('');

                imageDefects.innerHTML = `<p><strong>问题：</strong></p><ul>${defectList}</ul>`;
            }
        } else {
            imageStatus.innerHTML = `<span style="color: #28a745;"><i class="fas fa-check-circle"></i> 合格</span>`;
            imageDefects.innerHTML = '<p><strong>✓ 质量合格</strong></p>';
        }

        // 显示模态框
        modal.style.display = 'block';
    }

    closeModal() {
        document.getElementById('previewModal').style.display = 'none';
    }

    filterPhotos(filterType) {
        const photoItems = document.querySelectorAll('.photo-item');

        photoItems.forEach(item => {
            const hasBadge = item.querySelector('.photo-badge');

            switch (filterType) {
                case 'all':
                    item.style.display = 'block';
                    break;
                case 'qualified':
                    item.style.display = hasBadge ? 'none' : 'block';
                    break;
                case 'defective':
                    item.style.display = hasBadge ? 'block' : 'none';
                    break;
            }
        });
    }

    applyDefectFilters() {
        // 获取选中的缺陷类型
        const selectedDefects = [];
        document.querySelectorAll('.filter-checkbox input:checked').forEach(checkbox => {
            selectedDefects.push(checkbox.dataset.defect);
        });

        const photoItems = document.querySelectorAll('.photo-item');

        photoItems.forEach(item => {
            const badge = item.querySelector('.photo-badge');

            if (!badge) {
                // 没有缺陷的照片，始终显示
                item.style.display = 'block';
                return;
            }

            const badgeText = badge.textContent.toLowerCase();
            let hasSelectedDefect = false;

            // 检查是否包含选中的缺陷
            selectedDefects.forEach(defect => {
                const defectNames = {
                    'blur': '模糊',
                    'overexposed': '过曝',
                    'underexposed': '欠曝'
                };

                if (badgeText.includes(defectNames[defect])) {
                    hasSelectedDefect = true;
                }
            });

            // 根据筛选器显示/隐藏
            const currentFilter = document.querySelector('.filter-btn.active').dataset.filter;
            if (currentFilter === 'defective') {
                item.style.display = hasSelectedDefect ? 'block' : 'none';
            } else if (currentFilter === 'all') {
                item.style.display = hasSelectedDefect ? 'block' : 'block';
            }
        });
    }

    async performSearch() {
        const query = document.getElementById('searchInput').value.trim();

        if (!query) {
            alert('请输入搜索内容！');
            return;
        }

        const searchResults = document.getElementById('searchResults');

        // 显示加载状态
        searchResults.innerHTML = `
            <div class="loading">
                <i class="fas fa-spinner fa-spin fa-2x"></i>
                <p>正在搜索...</p>
            </div>
        `;

        try {
            const response = await fetch(`${this.apiBaseUrl}/search_photos`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    query: query,
                    top_k: 10
                })
            });

            const result = await response.json();

            if (result.results && result.results.length > 0) {
                this.displaySearchResults(result.results);
            } else {
                searchResults.innerHTML = `
                    <div class="empty-state">
                        <i class="fas fa-search fa-3x"></i>
                        <p>没有找到相关照片</p>
                        <p class="upload-hint">试试其他关键词</p>
                    </div>
                `;
            }

        } catch (error) {
            console.error('搜索失败:', error);
            searchResults.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-exclamation-triangle fa-3x"></i>
                    <p>搜索失败</p>
                    <p class="upload-hint">请检查网络连接或确认已处理照片</p>
                </div>
            `;
        }
    }

    displaySearchResults(results) {
        const searchResults = document.getElementById('searchResults');

        if (results.length === 0) {
            searchResults.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-search fa-3x"></i>
                    <p>没有找到相关照片</p>
                </div>
            `;
            return;
        }

        let html = '<div class="search-results-list">';

        results.forEach(result => {
            const imageUrl = `${this.apiBaseUrl}/get_photo/${encodeURIComponent(result.path)}`;
            const similarityPercent = Math.round(result.similarity_score * 100);

            html += `
                <div class="search-result">
                    <img src="${imageUrl}" alt="${result.filename}" class="result-image"
                         onerror="this.src='data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iODAiIGhlaWdodD0iODAiIHZpZXdCb3g9IjAgMCA4MCA4MCIgZmlsbD0iI2YwZjBmMCI+PHJlY3Qgd2lkdGg9IjgwIiBoZWlnaHQ9IjgwIi8+PHRleHQgeD0iNDAiIHk9IjQwIiBmb250LWZhbWlseT0iQXJpYWwiIGZvbnQtc2l6ZT0iMTIiIGZpbGw9IiNhYWEiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGR5PSIuM2VtIj4mbmJzcDs8L3RleHQ+PC9zdmc+'">
                    <div class="result-info">
                        <h4>${result.filename}</h4>
                        <p>相似度: <span class="result-score">${similarityPercent}%</span></p>
                        <button class="btn btn-small view-photo-btn" data-path="${result.path}">
                            <i class="fas fa-eye"></i> 查看
                        </button>
                    </div>
                </div>
            `;
        });

        html += '</div>';
        searchResults.innerHTML = html;

        // 绑定查看按钮事件
        document.querySelectorAll('.view-photo-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const path = e.target.dataset.path || e.target.closest('.view-photo-btn').dataset.path;
                this.viewPhoto(path);
            });
        });
    }

    viewPhoto(path) {
        // 查找对应的照片数据
        const photo = this.photos.find(p => p.image_path === path);
        if (photo) {
            this.previewPhoto(photo);
        } else {
            // 如果不在当前列表，直接预览
            this.previewPhoto({
                image_path: path,
                filename: path.split('/').pop() || path.split('\\').pop() || '未知文件',
                is_defective: false,
                defect_types: []
            });
        }
    }

    clearAll() {
        if (confirm('确定要清除所有数据和上传的文件吗？')) {
            // 停止进度跟踪
            if (this.progressInterval) {
                clearInterval(this.progressInterval);
                this.progressInterval = null;
            }

            // 调用后端清除缓存
            fetch(`${this.apiBaseUrl}/clear_cache`, {
                method: 'GET'
            }).catch(() => {
                // 忽略错误
            });

            // 重置UI
            document.getElementById('uploadArea').innerHTML = `
                <i class="fas fa-cloud-upload-alt fa-3x"></i>
                <p>拖放照片到这里，或点击选择文件</p>
                <p class="upload-hint">支持 JPG, PNG, JPEG 格式</p>
                <input type="file" id="fileInput" multiple accept=".jpg,.jpeg,.png,.JPG,.JPEG,.PNG">
            `;

            document.getElementById('progressContainer').style.display = 'none';
            document.getElementById('resultStats').innerHTML = '<p>请先上传并处理照片</p>';
            document.getElementById('photoGrid').innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-images fa-3x"></i>
                    <p>还没有照片，请先上传</p>
                </div>
            `;

            document.getElementById('searchResults').innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-search fa-3x"></i>
                    <p>输入搜索词开始查找照片</p>
                </div>
            `;

            // 重置数据
            this.selectedFiles = [];
            this.photos = [];
            this.currentTaskId = null;
            this.currentUploadId = null;

            // 重新绑定文件输入事件
            const fileInput = document.getElementById('fileInput');
            fileInput.addEventListener('change', (e) => {
                this.handleFileSelect(e.target.files);
            });
        }
    }

    reportIssue() {
        const issueUrl = `https://github.com/yourusername/ai-photo-assistant/issues/new?title=${encodeURIComponent('问题报告：云端部署')}`;
        window.open(issueUrl, '_blank');
    }
}

// 初始化应用
let app;
window.addEventListener('DOMContentLoaded', () => {
    app = new PhotoAssistantApp();

    // 全局访问
    window.app = app;

    // 添加一些CSS
    const additionalStyles = `
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 15px;
            margin: 1rem 0;
        }

        .stat-box {
            padding: 1rem;
            border-radius: 8px;
            text-align: center;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }

        .stat-box.total { background: #e3f2fd; }
        .stat-box.qualified { background: #e8f5e9; }
        .stat-box.defective { background: #ffebee; }
        .stat-box.indexed { background: #f3e5f5; }

        .stat-box h3 {
            font-size: 2rem;
            margin: 0;
            color: #333;
        }

        .stat-box p {
            margin: 5px 0 0 0;
            color: #666;
            font-weight: 500;
        }

        .loading {
            text-align: center;
            padding: 3rem;
            color: #666;
        }

        .loading i {
            margin-bottom: 1rem;
        }

        .file-list-preview {
            margin-top: 1rem;
            text-align: left;
            max-height: 200px;
            overflow-y: auto;
        }

        .file-item {
            padding: 8px;
            background: #f8f9ff;
            margin-bottom: 5px;
            border-radius: 4px;
            display: flex;
            align-items: center;
            gap: 10px;
            border-left: 3px solid #667eea;
        }

        .file-item i {
            color: #667eea;
        }

        .file-size {
            color: #888;
            font-size: 0.9rem;
            margin-left: auto;
        }

        .search-results-list {
            max-height: 500px;
            overflow-y: auto;
            padding-right: 10px;
        }

        .search-results-list::-webkit-scrollbar {
            width: 6px;
        }

        .search-results-list::-webkit-scrollbar-track {
            background: #f1f1f1;
            border-radius: 3px;
        }

        .search-results-list::-webkit-scrollbar-thumb {
            background: #c1c1c1;
            border-radius: 3px;
        }

        .search-result {
            display: flex;
            align-items: center;
            gap: 15px;
            padding: 15px;
            background: #f8f9ff;
            border-radius: 8px;
            margin-bottom: 10px;
            border-left: 4px solid #667eea;
            transition: transform 0.2s;
        }

        .search-result:hover {
            transform: translateX(5px);
            background: #f0f2ff;
        }

        .result-image {
            width: 80px;
            height: 80px;
            object-fit: cover;
            border-radius: 8px;
            border: 2px solid #e0e0e0;
        }

        .result-info {
            flex: 1;
        }

        .result-info h4 {
            margin: 0 0 5px 0;
            color: #333;
            font-size: 0.95rem;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .result-info p {
            margin: 0 0 8px 0;
            color: #666;
            font-size: 0.9rem;
        }

        .result-score {
            font-weight: bold;
            color: #667eea;
            font-size: 1rem;
        }

        .btn-small {
            padding: 6px 12px;
            font-size: 0.9rem;
            border-radius: 4px;
        }
    `;

    const styleSheet = document.createElement('style');
    styleSheet.textContent = additionalStyles;
    document.head.appendChild(styleSheet);
});