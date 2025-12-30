import cv2
import numpy as np
from PIL import Image
import os
from config import config


class PhotoQualityChecker:
    def __init__(self):
        self.blur_threshold = config.BLUR_THRESHOLD
        self.overexposure_threshold = config.OVEREXPOSURE_THRESHOLD
        self.underexposure_threshold = config.UNDEREXPOSURE_THRESHOLD
        self.max_image_size = config.MAX_IMAGE_SIZE
        self.resize_scale = config.RESIZE_SCALE

        # 图片缓存（线程安全，每个实例独立）
        self.image_cache = {}
        self.cache_size_limit = config.IMAGE_CACHE_SIZE

    def _get_gray_image(self, image_path):
        """获取灰度图像（带缓存和缩放）"""
        if image_path in self.image_cache:
            return self.image_cache[image_path]

        try:
            # 读取灰度图
            img_gray = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
            if img_gray is None:
                return None

            # 如果图片太大，缩小处理
            h, w = img_gray.shape
            if h * w > self.max_image_size:
                new_h = int(h * self.resize_scale)
                new_w = int(w * self.resize_scale)
                img_gray = cv2.resize(img_gray, (new_w, new_h))

            # 缓存图像
            if len(self.image_cache) < self.cache_size_limit:
                self.image_cache[image_path] = img_gray

            return img_gray
        except Exception as e:
            print(f"读取图像失败 {image_path}: {e}")
            return None

    def detect_blur(self, image_path):
        """基于拉普拉斯算子的模糊检测（优化版）"""
        img_gray = self._get_gray_image(image_path)
        if img_gray is None:
            return {"is_defective": False, "defect_type": None}

        # 使用较小的核计算拉普拉斯算子
        laplacian = cv2.Laplacian(img_gray, cv2.CV_64F, ksize=3)
        blur_score = float(np.var(laplacian))  # 转换为Python float
        is_blurry = bool(blur_score < self.blur_threshold)  # 转换为Python bool

        return {
            "score": blur_score,
            "is_defective": is_blurry,
            "defect_type": "blur" if is_blurry else None
        }

    def detect_exposure(self, image_path):
        """曝光检测优化版 - 使用抽样"""
        img_gray = self._get_gray_image(image_path)
        if img_gray is None:
            return {"is_defective": False, "defect_type": None}

        # 对大图进行抽样（每5个像素取一个）
        h, w = img_gray.shape
        if h * w > 1000000:  # 超过100万像素
            sample = img_gray[::5, ::5]
        else:
            sample = img_gray

        # 计算直方图（降低精度以加快计算）
        hist = cv2.calcHist([sample], [0], None, [64], [0, 256])
        total_pixels = sample.shape[0] * sample.shape[1]

        # 计算过曝和欠曝像素比例
        # 过曝：亮度>240（在64级直方图中对应>60）
        # 欠曝：亮度<15（在64级直方图中对应<4）
        overexposed_pixels = np.sum(hist[60:]) / total_pixels
        underexposed_pixels = np.sum(hist[:4]) / total_pixels

        is_overexposed = bool(overexposed_pixels > self.overexposure_threshold)
        is_underexposed = bool(underexposed_pixels > self.underexposure_threshold)
        is_defective = bool(is_overexposed or is_underexposed)

        defect_type = None
        if is_overexposed:
            defect_type = "overexposed"
        elif is_underexposed:
            defect_type = "underexposed"

        return {
            "overexposed_ratio": float(overexposed_pixels),
            "underexposed_ratio": float(underexposed_pixels),
            "is_defective": is_defective,
            "defect_type": defect_type
        }

    def detect_closed_eyes(self, image_path):
        """闭眼检测简化版 - 避免网络问题"""
        # 对于大量图片处理，暂时跳过闭眼检测以避免网络问题
        return {
            "closed_eyes_count": 0,
            "is_defective": False,
            "defect_type": None
        }

    def check_photo_quality(self, image_path):
        """综合质量检测优化版"""
        # 并行执行检测
        blur_result = self.detect_blur(image_path)
        exposure_result = self.detect_exposure(image_path)
        eyes_result = self.detect_closed_eyes(image_path)

        # 综合判断是否为废片
        is_defective = bool(
            blur_result["is_defective"] or
            eyes_result["is_defective"] or
            exposure_result["is_defective"]
        )

        # 收集所有缺陷类型
        defect_types = []
        if blur_result["defect_type"]:
            defect_types.append(blur_result["defect_type"])
        if eyes_result["defect_type"]:
            defect_types.append(eyes_result["defect_type"])
        if exposure_result["defect_type"]:
            defect_types.append(exposure_result["defect_type"])

        return {
            "image_path": image_path,
            "is_defective": is_defective,
            "defect_types": defect_types,
            "details": {
                "blur": blur_result,
                "eyes": eyes_result,
                "exposure": exposure_result
            }
        }

    def batch_check_quality(self, image_paths):
        """批量质量检测（保持接口兼容性）"""
        results = []
        for path in image_paths:
            results.append(self.check_photo_quality(path))
        return results

    def clear_cache(self):
        """清理缓存"""
        self.image_cache.clear()