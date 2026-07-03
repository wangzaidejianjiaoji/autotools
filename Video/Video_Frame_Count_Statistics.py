#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import cv2
import os
import sys

# 支持的视频扩展名（不区分大小写）
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv', '.flv', '.wmv', '.m4v', '.webm'}

def get_video_frame_count(video_path):
    """返回视频的总帧数，若无法读取则返回 None"""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None
    # 尝试直接获取帧数（多数视频有效）
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    # 如果帧数为0或负数，可能编码特殊，返回None
    return frame_count if frame_count > 0 else None

def scan_directory(root_dir):
    """遍历目录，收集所有视频文件"""
    video_files = []
    for dirpath, _, filenames in os.walk(root_dir):
        for f in filenames:
            ext = os.path.splitext(f)[1].lower()
            if ext in VIDEO_EXTENSIONS:
                full_path = os.path.join(dirpath, f)
                video_files.append(full_path)
    return video_files

def main():
    # 交互输入目录
    input_dir = input("请输入待标注视频所在的目录: ").strip()
    if not os.path.isdir(input_dir):
        print(f"错误：目录不存在 -> {input_dir}")
        sys.exit(1)

    # 收集所有视频文件
    video_list = scan_directory(input_dir)
    if not video_list:
        print(f"在目录 {input_dir} 中未找到任何支持的视频文件（支持格式：{', '.join(VIDEO_EXTENSIONS)}）")
        sys.exit(0)

    print(f"\n找到 {len(video_list)} 个视频文件，开始统计帧数...\n")

    total_frames = 0
    results = []  # 存储 (相对路径或文件名, 帧数)

    for idx, full_path in enumerate(video_list, 1):
        # 显示相对路径便于识别
        rel_path = os.path.relpath(full_path, input_dir)
        print(f"[{idx}/{len(video_list)}] 正在读取: {rel_path}", end='', flush=True)

        frames = get_video_frame_count(full_path)
        if frames is None:
            print(" -> 读取失败（跳过）")
            results.append((rel_path, "无法读取"))
        else:
            print(f" -> 帧数: {frames}")
            results.append((rel_path, frames))
            total_frames += frames

    # 输出汇总
    print("\n========== 统计结果 ==========")
    for name, frames in results:
        if isinstance(frames, int):
            print(f"{name} : {frames} 帧")
        else:
            print(f"{name} : {frames}")
    print("==============================")
    print(f"所有视频总帧数合计: {total_frames} 帧")

if __name__ == "__main__":
    main()