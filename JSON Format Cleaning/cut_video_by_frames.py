import os
import cv2


def cut_video_by_frames():
    """
    交互式视频截取工具
    根据起始帧和结束帧截取视频片段
    """
    # 交互输入视频路径
    video_path = input("请输入视频路径: ").strip().strip('"').strip("'")

    # 检查视频文件是否存在
    if not os.path.exists(video_path):
        print(f"错误: 视频文件不存在: {video_path}")
        return

    # 打开视频
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"错误: 无法打开视频文件: {video_path}")
        return

    # 获取视频信息
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    print(f"\n视频信息:")
    print(f"  总帧数: {total_frames}")
    print(f"  帧率: {fps:.2f} FPS")
    print(f"  分辨率: {width}x{height}")
    print(f"  时长: {total_frames/fps:.2f} 秒\n")

    # 输入起始帧和结束帧
    try:
        start_frame = int(input(f"请输入起始帧 (0-{total_frames-1}): "))
        end_frame = int(input(f"请输入结束帧 ({start_frame}-{total_frames-1}): "))
    except ValueError:
        print("错误: 请输入有效的数字")
        cap.release()
        return

    # 验证帧范围
    if start_frame < 0 or start_frame >= total_frames:
        print(f"错误: 起始帧必须在 0 到 {total_frames-1} 之间")
        cap.release()
        return

    if end_frame <= start_frame or end_frame >= total_frames:
        print(f"错误: 结束帧必须大于起始帧且小于 {total_frames}")
        cap.release()
        return

    # 生成输出文件名
    video_dir = os.path.dirname(video_path)
    video_name = os.path.splitext(os.path.basename(video_path))[0]
    video_ext = os.path.splitext(video_path)[1]
    output_path = os.path.join(video_dir, f"{video_name}_cut_{start_frame}_{end_frame}{video_ext}")

    # 设置视频写入器
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    if not out.isOpened():
        print("错误: 无法创建输出视频文件")
        cap.release()
        return

    # 跳转到起始帧
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    # 截取视频
    frame_count = 0
    total_to_write = end_frame - start_frame + 1

    print(f"\n正在截取视频...")
    for frame_idx in range(start_frame, end_frame + 1):
        ret, frame = cap.read()
        if not ret:
            print(f"警告: 在第 {frame_idx} 帧读取失败")
            break

        out.write(frame)
        frame_count += 1

        # 显示进度
        progress = (frame_count / total_to_write) * 100
        print(f"\r进度: {progress:.1f}% ({frame_count}/{total_to_write})", end="", flush=True)

    # 释放资源
    cap.release()
    out.release()

    print(f"\n\n视频截取完成!")
    print(f"输出文件: {output_path}")
    print(f"截取帧数: {frame_count}")
    print(f"视频时长: {frame_count/fps:.2f} 秒")


if __name__ == "__main__":
    cut_video_by_frames()