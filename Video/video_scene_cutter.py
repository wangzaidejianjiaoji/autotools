"""
视频场景切分脚本
功能：识别视频画面中的 conf 值，当 conf=0 时切分视频片段（前10秒到后3秒）
日期：2026-03-18
"""

import os
import re
import cv2
import pytesseract
from datetime import timedelta
import argparse
from pathlib import Path


def extract_conf_from_frame(frame):
    """
    从视频帧中提取 conf 值
    使用 OCR 识别画面中央区域的文字
    """
    h, w = frame.shape[:2]
    
    # 裁剪中央区域 (取中间 40% 区域)
    crop_h = int(h * 0.3)
    crop_w = int(w * 0.3)
    center_region = frame[crop_h:h-crop_h, crop_w:w-crop_w]
    
    # 转灰度
    gray = cv2.cvtColor(center_region, cv2.COLOR_BGR2GRAY)
    
    # 二值化处理，增强文字识别
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
    
    # OCR 识别
    text = pytesseract.image_to_string(thresh, config='--psm 7')
    
    # 提取 conf 值
    # 匹配 "conf: 0" 或 "conf=0" 或 "conf 0" 等格式
    conf_match = re.search(r'conf[:\s=]*(\d+\.?\d*)', text, re.IGNORECASE)
    if conf_match:
        return float(conf_match.group(1))
    
    # 也尝试匹配纯数字（如果画面只有数字）
    num_match = re.search(r'(\d+\.?\d*)', text)
    if num_match:
        return float(num_match.group(1))
    
    return None


def get_video_info(video_path):
    """获取视频基本信息"""
    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        print(f"无法打开视频: {video_path}")
        return None
    
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if fps > 0 else 0
    
    cap.release()
    
    return {
        'fps': fps,
        'total_frames': total_frames,
        'duration': duration
    }


def find_conf_zero_timestamps(video_path, sample_interval=30):
    """
    查找视频中 conf=0 的时间点
    
    Args:
        video_path: 视频路径
        sample_interval: 采样间隔（每N帧检测一次）
    
    Returns:
        conf_zero_timestamps: conf=0 的时间点列表（秒）
    """
    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        print(f"无法打开视频: {video_path}")
        return []
    
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    print(f"处理视频: {os.path.basename(video_path)}")
    print(f"  FPS: {fps:.2f}, 总帧数: {total_frames}")
    
    conf_zero_timestamps = []
    frame_idx = 0
    prev_conf = None
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        # 每隔 sample_interval 帧检测一次
        if frame_idx % sample_interval == 0:
            conf = extract_conf_from_frame(frame)
            
            # 检测 conf=0 的时刻（从非0变为0，或者首次检测到0）
            if conf is not None and conf == 0:
                timestamp = frame_idx / fps
                # 避免重复记录相近的时间点
                if not conf_zero_timestamps or (timestamp - conf_zero_timestamps[-1] > 5):
                    conf_zero_timestamps.append(timestamp)
                    print(f"  发现 conf=0 时刻: {timedelta(seconds=int(timestamp))}")
            
            prev_conf = conf
        
        frame_idx += 1
    
    cap.release()
    return conf_zero_timestamps


def cut_video_segment(video_path, output_path, start_time, end_time):
    """
    切分视频片段
    
    Args:
        video_path: 原视频路径
        output_path: 输出路径
        start_time: 开始时间（秒）
        end_time: 结束时间（秒）
    """
    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        print(f"无法打开视频: {video_path}")
        return False
    
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    # 设置输出视频
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    
    # 定位到开始帧
    start_frame = int(start_time * fps)
    end_frame = int(end_time * fps)
    
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    
    frame_idx = start_frame
    while frame_idx <= end_frame:
        ret, frame = cap.read()
        if not ret:
            break
        out.write(frame)
        frame_idx += 1
    
    cap.release()
    out.release()
    
    return True


def main():
    print("=" * 50)
    print("视频场景切分脚本 - 基于 conf=0 检测")
    print("=" * 50)
    
    # 交互式输入路径
    input_dir = input("请输入视频文件或目录路径: ").strip().strip('"').strip("'")
    
    if not input_dir:
        print("错误：路径不能为空")
        return
    
    input_path = Path(input_dir)
    
    # 检查路径是否存在
    if not input_path.exists():
        print(f"错误：路径不存在: {input_dir}")
        return
    
    # 设置输出目录
    output_dir = input("请输入输出目录（直接回车使用默认目录）: ").strip().strip('"').strip("'")
    if not output_dir:
        output_dir = None
    
    # 设置前后时间
    pre_seconds = input("conf=0 前多少秒（直接回车使用默认10秒）: ").strip()
    pre_seconds = int(pre_seconds) if pre_seconds else 10
    
    post_seconds = input("conf=0 后多少秒（直接回车使用默认3秒）: ").strip()
    post_seconds = int(post_seconds) if post_seconds else 3
    
    # 如果是文件，获取其父目录
    if input_path.is_file():
        video_files = [input_path]
        if output_dir is None:
            output_path = input_path.parent / "cut_segments"
        else:
            output_path = Path(output_dir)
    else:
        # 支持的视频格式
        video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv']
        
        # 查找所有视频文件
        video_files = []
        for ext in video_extensions:
            video_files.extend(input_path.glob(f'*{ext}'))
            video_files.extend(input_path.glob(f'*{ext.upper()}'))
        
        if not video_files:
            print(f"错误：未找到视频文件: {input_dir}")
            print(f"支持的视频格式: {', '.join(video_extensions)}")
            return
        
        # 设置输出目录
        if output_dir is None:
            output_path = input_path / "cut_segments"
        else:
            output_path = Path(output_dir)
    
    output_path.mkdir(parents=True, exist_ok=True)
    
    print("\n" + "=" * 50)
    print(f"找到 {len(video_files)} 个视频文件")
    print("=" * 50)
    
    # 处理每个视频
    for video_file in video_files:
        print(f"\n处理: {video_file.name}")
        
        # 获取视频信息
        info = get_video_info(str(video_file))
        if info is None:
            continue
        
        # 查找 conf=0 的时间点
        conf_zero_times = find_conf_zero_timestamps(str(video_file))
        
        if not conf_zero_times:
            print(f"  未检测到 conf=0 场景")
            continue
        
        # 切分视频片段
        video_name = video_file.stem
        for idx, timestamp in enumerate(conf_zero_times, 1):
            start_time = max(0, timestamp - pre_seconds)
            end_time = min(info['duration'], timestamp + post_seconds)
            
            output_file = output_path / f"{video_name}_scene{idx:02d}_conf0.mp4"
            
            print(f"  切分片段 {idx}: {timedelta(seconds=int(start_time))} - {timedelta(seconds=int(end_time))}")
            
            if cut_video_segment(str(video_file), str(output_file), start_time, end_time):
                print(f"    已保存: {output_file.name}")
    
    print("\n" + "=" * 50)
    print(f"处理完成！输出目录: {output_path}")
    print("=" * 50)


if __name__ == '__main__':
    main()