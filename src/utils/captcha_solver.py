import time

import cv2
import ddddocr
import numpy as np

from src.utils.logger import logger


class CaptchaSolver:
    """滑块验证码识别器 - ddddocr 方案"""

    @staticmethod
    def solve_slider(background_bytes: bytes, slider_bytes: bytes | None = None, debug: bool = False) -> tuple[int, int]:
        """
        识别滑块缺口位置。

        Args:
            background_bytes: 背景图片字节流
            slider_bytes: 滑块图片字节流（可选，但推荐提供以提高准确率）
            debug: 是否开启调试模式

        Returns:
            (center_x, image_width) - center_x 是缺口中心的 X 坐标
        """
        try:
            # 初始化 ocr
            # show_ad=False 防止输出广告
            det = ddddocr.DdddOcr(det=False, ocr=False, show_ad=False)

            center_x = 0

            # 使用 slide_match (通常需要 background + target)
            if slider_bytes:
                # simple_target=True 表示滑块图片是简单的（如透明背景的小图）
                # 注意：ddddocr 1.4.x 的 slide_match 参数顺序通常是 (target_bytes, background_bytes, simple_target=True)
                res = det.slide_match(slider_bytes, background_bytes, simple_target=True)

                # res format: {'target': [x1, y1, x2, y2]} where x1 is the left edge (gap position)
                if res and 'target' in res:
                    x1, y1, x2, y2 = res['target']
                    # 返回缺口中心 X 坐标
                    center_x = (x1 + x2) // 2

                    if debug:
                        logger.debug(f"ddddocr result: {res}, center_x={center_x}, gap_width={x2-x1}")
            else:
                logger.warning("No slider image provided for ddddocr slide_match. Using OpenCV fallback.")
                return CaptchaSolver._detect_gap_opencv(background_bytes, debug)

            # ddddocr 成功（或失败但继续）后的处理
            # 解码背景图以获取宽度
            nparr = np.frombuffer(background_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                logger.error("Failed to decode background image")
                return 0, 0
                
            img_h, img_w = img.shape[:2]
            
            # 保存调试图片
            if debug:
                try:
                    timestamp = int(time.time() * 1000)
                    cv2.imwrite(f"captcha_debug_{timestamp}_bg.png", img)
                    if slider_bytes:
                        slider_arr = np.frombuffer(slider_bytes, np.uint8)
                        slider_img = cv2.imdecode(slider_arr, cv2.IMREAD_UNCHANGED)
                        cv2.imwrite(f"captcha_debug_{timestamp}_slider.png", slider_img)

                    # 绘制结果
                    if center_x > 0:
                        # 绘制缺口中心线（红色）
                        cv2.line(img, (center_x, 0), (center_x, img_h), (0, 0, 255), 2)
                        # 绘制预估缺口区域（假设宽度 90px，中心在 center_x）
                        gap_w = 90
                        left_x = center_x - gap_w // 2
                        cv2.rectangle(img, (left_x, 0), (left_x + gap_w, img_h), (0, 255, 0), 1)
                        cv2.imwrite(f"captcha_debug_{timestamp}_result.png", img)
                        logger.debug(f"Saved debug images with prefix: captcha_debug_{timestamp}_")
                except Exception as e:
                    logger.debug(f"Failed to save debug images: {e}")

            return center_x, img_w

        except Exception as e:
            logger.error(f"Captcha solving failed with ddddocr: {e}")
            return 0, 0

    @staticmethod
    def _detect_gap_opencv(background_bytes: bytes, debug: bool = False) -> tuple[int, int]:
        """
        OpenCV fallback for detecting gap in background image
        """
        try:
            nparr = np.frombuffer(background_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                return 0, 0
            
            img_h, img_w = img.shape[:2]
            
            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Image enhancement
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            gray = clahe.apply(gray)
            
            # Gaussian blur to reduce noise
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            
            # Canny edge detection
            edges = cv2.Canny(blurred, 50, 150)
            
            # Find contours
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            candidates = []
            
            # Search area restrictions
            min_x = int(img_w * 0.15)
            max_x = int(img_w * 0.90)
            
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                
                # Filter by size (gap is usually around 40-60px)
                if not (30 <= w <= 80 and 30 <= h <= 80):
                    continue
                    
                # Filter by position
                if x < min_x or x + w > max_x:
                    continue
                    
                # Calculate brightness difference
                # Gap usually darker or different texture
                mask = np.zeros_like(gray)
                cv2.drawContours(mask, [contour], -1, 255, -1)
                
                # ROI mean brightness
                roi = gray[y:y+h, x:x+w]
                # roi_mean = np.mean(roi) # Unused
                
                # Score based on dimensions and position
                # Ideal square-ish shape
                aspect_ratio = float(w)/h
                shape_score = 1.0 - abs(aspect_ratio - 1.0)
                
                candidates.append((x, y, w, h, shape_score))
                
            if candidates:
                # Sort by shape score (index 4)
                candidates.sort(key=lambda c: c[4], reverse=True)
                best_x = candidates[0][0]
                best_y = candidates[0][1]
                best_w = candidates[0][2]
                best_h = candidates[0][3]
                
                # Calculate center
                center_x = best_x + best_w // 2
                
                if debug:
                    logger.debug(f"OpenCV fallback candidates top 3: {candidates[:3]}")
                    try:
                        timestamp = int(time.time() * 1000)
                        # Ensure coordinates are integers
                        pt1 = (int(best_x), int(best_y))
                        pt2 = (int(best_x + best_w), int(best_y + best_h))
                        cv2.rectangle(img, pt1, pt2, (0, 255, 0), 2)
                        # Draw center line
                        cv2.line(img, (int(center_x), 0), (int(center_x), img_h), (0, 0, 255), 2)
                        cv2.imwrite(f"captcha_debug_{timestamp}_opencv_fallback.png", img)
                    except Exception as e:
                        logger.warning(f"Failed to draw debug rect: {e}")
                
                return center_x, img_w
                
            return 0, img_w
            
        except Exception as e:
            logger.error(f"OpenCV fallback failed: {e}")
            return 0, 0
