#!/usr/bin/env python3
"""分析验证码调试图片"""
import cv2
import numpy as np
import glob
import os

def analyze_captcha():
    # 查找最新的调试图片
    bg_files = sorted(glob.glob("captcha_bg_*.png"), reverse=True)
    edge_files = sorted(glob.glob("captcha_debug_*_edges.png"), reverse=True)
    
    if not bg_files:
        print("未找到 captcha_bg_*.png 文件")
        return
    
    bg_path = bg_files[0]
    print(f"分析文件: {bg_path}")
    
    # 加载背景图
    bg = cv2.imread(bg_path)
    if bg is None:
        print("加载失败")
        return
    
    h, w = bg.shape[:2]
    print(f"\n=== 图片基本信息 ===")
    print(f"尺寸: {w}x{h}")
    
    gray = cv2.cvtColor(bg, cv2.COLOR_BGR2GRAY)
    print(f"灰度范围: min={gray.min()}, max={gray.max()}, mean={gray.mean():.1f}")
    
    # 垂直投影分析
    print(f"\n=== 垂直投影分析 ===")
    col_means = np.mean(gray, axis=0)
    
    # 寻找突变点（可能是缺口边缘）
    diff = np.diff(col_means)
    
    # 找最大下降点（进入阴影区）
    drop_threshold = -5
    drops = []
    for i in range(50, len(diff) - 50):
        if diff[i] < drop_threshold:
            drops.append((i, diff[i]))
    
    if drops:
        drops.sort(key=lambda x: x[1])
        print(f"最大亮度下降点: x={drops[0][0]}, 下降值={drops[0][1]:.1f}")
    
    # 找最大上升点（离开阴影区）
    rise_threshold = 5
    rises = []
    for i in range(50, len(diff) - 50):
        if diff[i] > rise_threshold:
            rises.append((i, diff[i]))
    
    if rises:
        rises.sort(key=lambda x: x[1], reverse=True)
        print(f"最大亮度上升点: x={rises[0][0]}, 上升值={rises[0][1]:.1f}")
    
    # 如果找到配对的下降和上升点，中间可能就是缺口
    if drops and rises:
        drop_x = drops[0][0]
        rise_x = rises[0][0]
        if drop_x < rise_x and rise_x - drop_x < 80:
            gap_center = (drop_x + rise_x) // 2
            print(f"\n推测缺口中心: x={gap_center} (占比: {gap_center/w*100:.1f}%)")
            print(f"推测缺口宽度: {rise_x - drop_x}px")
    
    # 滑动窗口寻找最暗区域
    print(f"\n=== 最暗区域分析 ===")
    window = 50
    min_mean = 255
    min_x = 0
    for x in range(50, w - window - 20):
        window_mean = np.mean(col_means[x:x+window])
        if window_mean < min_mean:
            min_mean = window_mean
            min_x = x + window // 2
    
    print(f"最暗区域中心: x={min_x} (占比: {min_x/w*100:.1f}%)")
    print(f"最暗区域亮度: {min_mean:.1f}")
    
    # 对比周围
    if min_x > 60 and min_x + 60 < w:
        left_mean = np.mean(col_means[min_x-60:min_x-10])
        right_mean = np.mean(col_means[min_x+10:min_x+60])
        diff_val = (left_mean + right_mean)/2 - min_mean
        print(f"与周围亮度差: {diff_val:.1f}")
    
    # 边缘检测分析
    if edge_files:
        print(f"\n=== 边缘检测分析 ===")
        edge_path = edge_files[0]
        edges = cv2.imread(edge_path, cv2.IMREAD_GRAYSCALE)
        if edges is not None:
            edge_points = np.sum(edges > 0)
            print(f"边缘点数量: {edge_points}")
            
            # 提取边缘检测识别到的位置
            filename = os.path.basename(edge_path)
            # captcha_debug_1766747038122_edge_313_edges.png
            parts = filename.split("_")
            for i, p in enumerate(parts):
                if p == "edge" and i + 1 < len(parts):
                    detected_x = int(parts[i+1])
                    print(f"边缘检测识别位置: x={detected_x} (占比: {detected_x/w*100:.1f}%)")
                    break
    
    # 生成可视化图片
    print(f"\n=== 生成可视化 ===")
    vis = bg.copy()
    
    # 画出最暗区域
    cv2.line(vis, (min_x, 0), (min_x, h), (0, 255, 0), 2)
    cv2.putText(vis, f"Dark:{min_x}", (min_x-30, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
    
    # 画出下降点和上升点
    if drops:
        cv2.line(vis, (drops[0][0], 0), (drops[0][0], h), (255, 0, 0), 1)
    if rises:
        cv2.line(vis, (rises[0][0], 0), (rises[0][0], h), (0, 0, 255), 1)
    
    cv2.imwrite("captcha_analysis.png", vis)
    print("已保存: captcha_analysis.png")


if __name__ == "__main__":
    os.chdir("/Users/uroborus/PythonProject/crawler4j")
    analyze_captcha()

