import os
import time
from video_pre_tagging import save_video_frames_with_interval

# 测试函数
def test_performance():
    """测试视频帧提取性能"""
    # 使用一个示例视频文件路径（请根据实际情况修改）
    video_path = "test_video.mp4"
    output_dir = "test_output"
    
    # 检查测试视频是否存在
    if not os.path.exists(video_path):
        print(f"错误: 测试视频文件 '{video_path}' 不存在")
        print("请修改 video_path 为实际存在的视频文件路径")
        return
    
    # 确保输出目录存在
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 测试参数
    interval = 1  # 间隔1帧
    start_frame = 0
    end_frame = 100  # 只测试前100帧
    
    print("开始性能测试...")
    print(f"视频文件: {video_path}")
    print(f"输出目录: {output_dir}")
    print(f"测试范围: 第 {start_frame} 帧到第 {end_frame} 帧，间隔 {interval} 帧")
    
    # 记录开始时间
    start_time = time.time()
    
    # 执行帧提取
    success, _ = save_video_frames_with_interval(
        video_path=video_path,
        output_dir=output_dir,
        interval=interval,
        start_frame=start_frame,
        end_frame=end_frame
    )
    
    # 记录结束时间
    end_time = time.time()
    elapsed_time = end_time - start_time
    
    print(f"\n性能测试结果:")
    print(f"处理状态: {'成功' if success else '失败'}")
    print(f"总处理时间: {elapsed_time:.2f} 秒")
    
    # 清理测试文件
    if os.path.exists(output_dir):
        import shutil
        shutil.rmtree(output_dir)
        print(f"已清理测试输出目录: {output_dir}")

if __name__ == "__main__":
    test_performance()
