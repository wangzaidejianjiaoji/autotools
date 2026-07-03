#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import cv2
import os
import sys

# 支持的视频扩展名（不区分大小写）
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv', '.flv', '.wmv', '.m4v'}

def is_video_file(filename):
    """检查文件是否为支持的视频格式"""
    ext = os.path.splitext(filename)[1].lower()
    return ext in VIDEO_EXTENSIONS

def extract_frames(video_path, output_dir, interval, naming_format, start_frame):
    """
    从单个视频提取帧并保存为JPG图片
    video_path: 视频文件路径
    output_dir: 图片输出目录（会被创建）
    interval: 帧间隔（0表示全部）
    naming_format: 命名格式 (1: 视频名_五位帧号, 2: 六位帧号)
    start_frame: 起始帧号 (0 或 1)
    返回成功保存的图片数量
    """
    os.makedirs(output_dir, exist_ok=True)
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"  错误：无法打开视频文件 {video_path}")
        return 0

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    print(f"  视频信息：总帧数 {total_frames}, 帧率 {fps:.2f}")

    # 获取视频基础名称（不含扩展名）
    video_name = os.path.splitext(os.path.basename(video_path))[0]

    frame_idx = 0
    saved_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if interval == 0 or frame_idx % interval == 0:
            # 计算实际保存的帧号（基于起始帧号）
            save_frame_idx = frame_idx + start_frame
            # 根据选择的命名格式生成文件名
            if naming_format == 1:
                # 按视频名_五位帧号格式命名
                filename = f"{video_name}_{save_frame_idx:05d}.jpg"
            else:
                # 按六位帧号格式命名
                filename = f"{save_frame_idx:06d}.jpg"
            filepath = os.path.join(output_dir, filename)
            try:
                cv2.imencode('.jpg', frame)[1].tofile(filepath)
                saved_count += 1
                if saved_count % 100 == 0:
                    print(f"    已保存 {saved_count} 张图片...")
            except Exception as e:
                print(f"    警告：保存失败 {filepath} - {e}")

        frame_idx += 1
        if frame_idx % 1000 == 0:
            print(f"    处理进度：{frame_idx}/{total_frames} 帧")

    cap.release()
    print(f"  完成！共保存 {saved_count} 张图片到：{output_dir}")
    return saved_count

def main():
    # 交互输入
    input_path = input("请输入视频文件路径或目录路径: ").strip()
    output_root = input("请输入图片输出根目录: ").strip()
    interval_str = input("请输入间隔帧数 (0表示输出所有帧，5表示每隔5帧提取一帧): ").strip()
    
    # 选择命名格式
    naming_format_str = input("请选择命名格式 (1: 视频名_五位帧号, 2: 六位帧号): ").strip()
    try:
        naming_format = int(naming_format_str)
        if naming_format not in [1, 2]:
            print("无效选项，使用默认格式1（视频名_五位帧号）")
            naming_format = 1
    except ValueError:
        print("无效输入，使用默认格式1（视频名_五位帧号）")
        naming_format = 1
    
    # 选择起始帧号
    start_frame_str = input("请选择起始帧号 (0: 从00000开始, 1: 从00001开始): ").strip()
    try:
        start_frame = int(start_frame_str)
        if start_frame not in [0, 1]:
            print("无效选项，使用默认值0（从00000开始）")
            start_frame = 0
    except ValueError:
        print("无效输入，使用默认值0（从00000开始）")
        start_frame = 0

    # 验证输入路径存在
    if not os.path.exists(input_path):
        print(f"错误：路径不存在 -> {input_path}")
        sys.exit(1)

    # 如果输出目录为空，默认为输入路径所在目录
    if not output_root:
        if os.path.isdir(input_path):
            output_root = input_path
        else:
            output_root = os.path.dirname(input_path) or '.'
        print(f"输出目录默认为：{output_root}")

    # 解析间隔帧数
    try:
        interval = int(interval_str)
        if interval < 0:
            print("间隔帧数必须 >= 0，使用默认值0")
            interval = 0
    except ValueError:
        print("无效数字，使用默认间隔0（输出所有帧）")
        interval = 0

    # 收集要处理的视频文件列表
    video_files = []
    if os.path.isfile(input_path):
        if is_video_file(input_path):
            video_files.append(input_path)
        else:
            print(f"错误：指定的文件不是受支持的视频格式（支持：{', '.join(VIDEO_EXTENSIONS)}）")
            sys.exit(1)
    else:  # 目录
        for f in os.listdir(input_path):
            full_path = os.path.join(input_path, f)
            if os.path.isfile(full_path) and is_video_file(full_path):
                video_files.append(full_path)
        if not video_files:
            print(f"错误：目录 {input_path} 中没有找到任何受支持的视频文件")
            sys.exit(1)
        print(f"找到 {len(video_files)} 个视频文件，开始批量处理...")

    # 处理每个视频
    total_success = 0
    for idx, video_path in enumerate(video_files, 1):
        print(f"\n[{idx}/{len(video_files)}] 处理视频: {video_path}")
        # 确定输出子目录：单文件模式直接使用 output_root；批量模式使用 output_root/视频文件名(无扩展名)
        if len(video_files) == 1 and os.path.isfile(input_path):
            output_dir = output_root
        else:
            base_name = os.path.splitext(os.path.basename(video_path))[0]
            output_dir = os.path.join(output_root, base_name)
        saved = extract_frames(video_path, output_dir, interval, naming_format, start_frame)
        total_success += saved

    print(f"\n全部处理完成！共处理 {len(video_files)} 个视频，成功保存 {total_success} 张图片。")

if __name__ == "__main__":
    main()