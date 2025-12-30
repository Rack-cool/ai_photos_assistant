import os
import torch
import chromadb
from chromadb import PersistentClient
from PIL import Image
from config import config


class PhotoSemanticSearch:
    def __init__(self, collection_name="photo_collection"):
        # 设备选择
        self.device = "cuda" if torch.cuda.is_available() and config.USE_GPU else "cpu"
        print(f"使用设备: {self.device}")

        # 尝试加载CLIP模型
        self.clip_available = False
        self.model = None
        self.preprocess = None
        self.clip_module = None  # 保存CLIP模块引用

        try:
            import clip  # 使用直接导入
            self.clip_module = clip
            print(f"✅ 成功导入CLIP模块: {clip.__name__}")

            # 加载模型
            self.model, self.preprocess = self.clip_module.load(config.CLIP_MODEL_NAME, device=self.device)
            self.clip_available = True
            print(f"✅ CLIP模型加载成功: {config.CLIP_MODEL_NAME}")
            print(f"✅ 模型已加载到: {self.device}")
        except ImportError as e:
            print(f"❌ CLIP导入失败: {e}")
            print("⚠️ 语义搜索功能将不可用，质量检测功能正常")
        except Exception as e:
            print(f"⚠️ CLIP模型加载失败: {e}")
            print("⚠️ 语义搜索功能将不可用，质量检测功能正常")

        # 初始化ChromaDB
        os.makedirs(config.CHROMA_DB_DIR, exist_ok=True)
        self.client = PersistentClient(path=config.CHROMA_DB_DIR)

        # 获取或创建集合
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}  # 使用余弦相似度
        )

    def get_image_embedding(self, image_path):
        """生成单张图片的CLIP嵌入向量"""
        if not self.clip_available or self.model is None:
            print("⚠️  CLIP不可用，无法生成图像嵌入")
            return None

        try:
            # 确保图片存在
            if not os.path.exists(image_path):
                print(f"❌ 图片不存在: {image_path}")
                return None

            # 打开并处理图片
            image = Image.open(image_path).convert("RGB")
            image_tensor = self.preprocess(image).unsqueeze(0).to(self.device)

            with torch.no_grad():
                image_embedding = self.model.encode_image(image_tensor)
                # 归一化向量
                image_embedding = image_embedding / image_embedding.norm(dim=-1, keepdim=True)

            return image_embedding.cpu().numpy().flatten().tolist()

        except Exception as e:
            print(f"❌ 生成图片嵌入失败 {image_path}: {e}")
            return None

    def get_text_embedding(self, text):
        """生成文本的CLIP嵌入向量"""
        if not self.clip_available or self.model is None or self.clip_module is None:
            print("⚠️  CLIP不可用，无法生成文本嵌入")
            return None

        try:
            # 使用保存的CLIP模块引用
            text_input = self.clip_module.tokenize([text]).to(self.device)
            with torch.no_grad():
                text_embedding = self.model.encode_text(text_input)
                text_embedding = text_embedding / text_embedding.norm(dim=-1, keepdim=True)
            return text_embedding.cpu().numpy().flatten().tolist()
        except Exception as e:
            print(f"❌ 生成文本嵌入失败 '{text}': {e}")
            return None

    def index_photos(self, photo_paths, clear_existing=False):
        """批量索引合格照片到向量数据库（带重复检查）

        Args:
            photo_paths: 照片路径列表
            clear_existing: 是否清空已有数据（默认False，增量添加）
        """
        if not photo_paths:
            print("⚠️  没有照片需要索引")
            return 0

        if not self.clip_available:
            print("⚠️  CLIP不可用，跳过语义索引")
            return 0

        print(f"✅ CLIP可用，开始索引 {len(photo_paths)} 张照片...")

        # 可选：清空现有数据（只在第一次调用时清空）
        if clear_existing:
            existing_count = self.collection.count()
            if existing_count > 0:
                print(f"清空现有 {existing_count} 条记录...")
                self.clear_collection()

        ids = []
        embeddings = []
        metadatas = []

        indexed_count = 0
        failed_count = 0

        # 用于检查重复文件名
        indexed_filenames = set()

        for idx, photo_path in enumerate(photo_paths):
            # 每处理50张打印一次进度
            if idx % 50 == 0:
                print(f"  索引进度: {idx}/{len(photo_paths)}")

            # 检查文件是否存在
            if not os.path.exists(photo_path):
                print(f"❌ 文件不存在，跳过: {photo_path}")
                failed_count += 1
                continue

            filename = os.path.basename(photo_path)

            # 检查是否已索引（基于文件名）
            if filename in indexed_filenames:
                print(f"⚠️  文件已索引，跳过重复: {filename}")
                continue

            # 生成嵌入向量
            embedding = self.get_image_embedding(photo_path)
            if embedding:
                # 检查嵌入向量是否有效（不全为0）
                if all(abs(v) < 0.000001 for v in embedding[:10]):  # 使用小阈值检查是否为0
                    print(f"⚠️  嵌入向量接近0，跳过: {filename}")
                    failed_count += 1
                    continue

                # 创建唯一ID
                photo_id = f"{filename}_{idx}"
                ids.append(photo_id)
                embeddings.append(embedding)
                metadatas.append({
                    "path": photo_path,
                    "filename": filename,
                    "index": idx
                })
                indexed_filenames.add(filename)
                indexed_count += 1
            else:
                print(f"⚠️  嵌入生成失败，跳过: {filename}")
                failed_count += 1

        # 批量添加到数据库
        if ids:
            try:
                print(f"正在添加 {len(ids)} 个嵌入到数据库...")
                self.collection.add(
                    ids=ids,
                    embeddings=embeddings,
                    metadatas=metadatas
                )
                print(f"✅ 成功索引 {len(ids)} 张照片到向量数据库")

                # 验证添加的数量
                new_count = self.collection.count()
                print(f"✅ 向量数据库现在有 {new_count} 张照片")

            except Exception as e:
                print(f"❌ 添加到向量数据库失败: {e}")
                return 0
        else:
            print("⚠️  没有成功生成任何嵌入向量")

        print(f"📊 索引统计: 成功 {indexed_count}, 失败 {failed_count}")
        return indexed_count

    def search_photos(self, query_text, top_k=10):
        """基于自然语言查询搜索相似照片"""
        if not self.clip_available:
            print("⚠️  CLIP不可用，无法进行语义搜索")
            return []

        print(f"🔍 语义搜索: '{query_text}'，查找 {top_k} 个结果")

        # 生成查询文本嵌入
        text_embedding = self.get_text_embedding(query_text)
        if not text_embedding:
            print("❌ 文本嵌入生成失败")
            return []

        # 获取集合中的照片数量
        collection_count = self.collection.count()
        print(f"✅ 向量数据库中有 {collection_count} 张照片")

        if collection_count == 0:
            print("⚠️  向量数据库中暂无照片，请先处理照片文件夹")
            return []

        # 向量检索
        try:
            results = self.collection.query(
                query_embeddings=[text_embedding],
                n_results=min(top_k, collection_count)
            )
        except Exception as e:
            print(f"❌ 向量检索失败: {e}")
            return []

        # 修复相似度计算
        search_results = []
        if results["metadatas"] and results["metadatas"][0]:
            for idx, metadata in enumerate(results["metadatas"][0]):
                # 计算相似度分数（修复版）
                if results["distances"] and results["distances"][0]:
                    distance = results["distances"][0][idx]
                    # ✅ 修复：使用 1.0 - (distance/2.0) 得到0-1范围的相似度
                    # 余弦距离范围是0-2，所以除以2得到0-1范围
                    similarity = 1.0 - (distance / 2.0)
                    # 确保在0-1范围内
                    similarity = max(0.0, min(1.0, similarity))
                    print(
                        f"📄 结果{idx + 1}: 距离={distance:.3f}, 相似度={similarity:.3f}, 文件={metadata.get('filename')}")
                else:
                    similarity = 0.5

                search_results.append({
                    "rank": idx + 1,
                    "similarity_score": similarity,
                    "path": metadata.get("path", ""),
                    "filename": metadata.get("filename", "")
                })

        print(f"✅ 找到 {len(search_results)} 个相关结果")
        return search_results

    def clear_collection(self):
        """清空向量数据库"""
        try:
            self.client.delete_collection(name=self.collection.name)
            print("✅ 已清空向量数据库")
        except Exception as e:
            print(f"❌ 清空向量数据库失败: {e}")
        self.collection = self.client.get_or_create_collection(name=self.collection.name)

    def get_collection_stats(self):
        """获取集合统计信息"""
        count = self.collection.count()
        return {
            "total_photos": count,
            "collection_name": self.collection.name,
            "clip_available": self.clip_available,
            "device": self.device
        }