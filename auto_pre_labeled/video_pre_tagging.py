import cv2
import os
import concurrent.futures  # 未使用，可能遗留，实际使用 multiprocessing.Pool
from multiprocessing import cpu_count, Pool, Manager  # Manager未使用
import time
import numpy as np  # 未直接使用，但 OpenCV 读取的帧是 numpy 数组，间接依赖


class FrameProcessor:
    """视频帧处理器，使用多进程并行处理帧"""

    def __init__(self, video_path, output_dir, frame_numbers, prefix="", zfill_width=5):
        """
        初始化帧处理器
        :param video_path: 视频文件路径
        :param output_dir: 输出图片保存目录
        :param frame_numbers: 需要提取的帧号列表
        :param prefix: 输出文件名前缀，为空则自动使用视频文件名
        :param zfill_width: 帧号数字补零的宽度
        """
        self.video_path = video_path
        self.output_dir = output_dir
        self.frame_numbers = sorted(frame_numbers)  # 排序确保顺序处理（虽然多进程无序）
        self.prefix = prefix
        self.zfill_width = zfill_width
        self.frame_format = "jpg"  # 输出图像格式
        self.total_frames = len(frame_numbers)  # 总待处理帧数
        self.start_time = time.time()  # 记录开始时间，用于速度统计

    def _initialize(self):
        """初始化处理器：检查视频、创建输出目录、设置文件名前缀"""
        # 检查视频文件是否存在
        if not os.path.exists(self.video_path):
            print(f"错误: 视频文件 '{self.video_path}' 不存在")
            return False

        # 如果输出目录不存在，递归创建
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            print(f"已创建输出目录: {self.output_dir}")

        # 提取视频文件名（不含扩展名）作为默认前缀
        video_name = os.path.splitext(os.path.basename(self.video_path))[0]

        # 如果用户未提供前缀，则使用视频文件名
        if not self.prefix:
            self.prefix = video_name

        return True

    def _process_frame(self, frame_info):
        """
        单个帧的处理函数，将在多进程中被调用
        :param frame_info: 元组 (帧号, 输出完整路径)
        :return: (是否成功, 帧号)
        """
        frame_number, output_path = frame_info
        cap = None
        try:
            # 每个进程独立打开视频文件
            cap = cv2.VideoCapture(self.video_path)
            if not cap.isOpened():
                return False, frame_number

            # 设置视频读取位置到指定帧（注意：某些编码可能定位不精确）
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)  #cap.set(property_id, value)：设置视频捕获对象的属性
                                                            #cv2.CAP_PROP_POS_FRAMES：基于 0 索引 的帧位置属性。设置该属性后，下一次 read() 会从该帧开始读取
            # 读取该帧
            ret, frame = cap.read()
            if not ret:
                return False, frame_number

            # 保存为JPEG，压缩质量设为90，平衡速度与画质
            success = cv2.imwrite(output_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
            return success, frame_number
        except Exception as e:
            print(f"处理帧 {frame_number} 时出错: {e}")
            return False, frame_number
        finally:
            # 确保释放视频捕获对象
            if cap is not None:
                cap.release()

    def process(self, max_processes=None):
        """
        启动多进程并行处理所有帧
        :param max_processes: 最大进程数，None则自动计算为 min(8, cpu_count()//2+1)
        :return: (成功标志, 空列表) 第二个参数预留，目前未返回实际文件列表
        """
        # 1. 初始化检查
        if not self._initialize():
            return False, []

        print(f"开始处理 {self.total_frames} 帧...")

        # 2. 构造任务列表：(帧号, 输出路径)
        frame_infos = []
        for frame_number in self.frame_numbers:
            # 生成文件名：前缀_帧号补零.jpg
            output_filename = f"{self.prefix}_{str(frame_number).zfill(self.zfill_width)}.{self.frame_format}"
            output_path = os.path.join(self.output_dir, output_filename)
            frame_infos.append((frame_number, output_path))

        # 3. 确定进程数
        if max_processes is None:
            # 默认策略：最多8个进程，或 CPU 核心数的一半+1，避免系统过载
            num_processes = min(8, cpu_count() // 2 + 1)
        else:
            num_processes = max(1, min(max_processes, cpu_count()))
        print(f"使用 {num_processes} 个进程进行并行处理")

        saved_count = 0
        error_count = 0

        # 4. 分批处理，防止一次性提交过多任务导致内存占用过大
        batch_size = 100
        total_batches = (len(frame_infos) + batch_size - 1) // batch_size   #向上取整

        for batch_idx in range(total_batches):
            start_idx = batch_idx * batch_size
            end_idx = min((batch_idx + 1) * batch_size, len(frame_infos))
            batch_infos = frame_infos[start_idx:end_idx]

            # 使用进程池并行处理当前批次
            with Pool(processes=num_processes) as pool:
                results = pool.map(self._process_frame, batch_infos)

            # 统计成功/失败数量
            for success, frame_number in results:
                if success:
                    saved_count += 1
                else:
                    error_count += 1

            # 5. 进度显示
            processed = min((batch_idx + 1) * batch_size, len(frame_infos))
            elapsed = time.time() - self.start_time
            if processed % 100 == 0 or processed == len(frame_infos):
                fps = processed / elapsed
                print(f"处理进度: {processed}/{self.total_frames} 帧, 速度: {fps:.2f} 帧/秒")

        # 6. 最终统计
        elapsed_time = time.time() - self.start_time
        print(f"\n处理完成!")
        print(f"总帧数: {self.total_frames}")
        print(f"成功保存: {saved_count}")
        print(f"错误数量: {error_count}")
        print(f"处理时间: {elapsed_time:.2f} 秒")
        print(f"平均速度: {saved_count / elapsed_time:.2f} 帧/秒")

        return True, []  # 第二个元素预留，可改为实际保存的文件列表


def save_video_frames_with_interval(video_path, output_dir, interval=0, start_frame=0,
                                    end_frame=None, prefix="", zfill_width=5):
    """
    高层接口：根据帧间隔、起止帧号计算待提取的帧列表，然后调用 FrameProcessor 处理

    参数:
    video_path: 视频文件路径
    output_dir: 输出目录
    interval: 帧间隔 (0=连续帧, 1=隔1帧取1帧，即每隔一帧取一帧)
    start_frame: 起始帧号 (从0开始)
    end_frame: 结束帧号 (None表示到视频结束)
    prefix: 文件名前缀 (默认为视频文件名)
    zfill_width: 帧号补零宽度

    返回:
    (bool, list) 处理是否成功, 空列表（预留）
    """
    # 1. 检查视频文件是否存在
    if not os.path.exists(video_path):
        print(f"错误: 视频文件 '{video_path}' 不存在")
        return False, []

    # 2. 打开视频获取基本信息
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"错误: 无法打开视频文件 '{video_path}'")
        return False, []

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration = total_frames / fps if fps > 0 else 0

    # 打印视频信息
    print(f"视频信息:")
    print(f"  文件名: {os.path.basename(video_path)}")
    print(f"  总帧数: {total_frames}")
    print(f"  帧率: {fps:.2f}")
    print(f"  分辨率: {width}x{height}")
    print(f"  时长: {duration:.2f} 秒")
    print(f"  帧间隔: {interval}")

    # 3. 确定结束帧
    if end_frame is None or end_frame > total_frames:
        end_frame = total_frames

    # 4. 参数合理性校正
    if start_frame < 0:
        print(f"警告: 起始帧号 {start_frame} 小于0，自动调整为0")
        start_frame = 0

    if end_frame < start_frame:
        print(f"错误: 结束帧号 {end_frame} 小于起始帧号 {start_frame}")
        cap.release()
        return False, []

    # 5. 计算要提取的帧号列表
    # 注意：range 步长为 interval+1，因为 interval 表示要跳过的帧数
    frame_numbers = list(range(start_frame, end_frame + 1, interval + 1))

    if not frame_numbers:
        print("错误: 没有帧可以提取")
        cap.release()
        return False, []

    print(f"将提取 {len(frame_numbers)} 帧: 从第 {start_frame} 帧到第 {end_frame} 帧，间隔 {interval} 帧")

    # 6. 释放视频捕获对象，FrameProcessor 会重新打开
    cap.release()

    # 7. 实例化处理器并开始处理，强制最大进程数不超过8
    processor = FrameProcessor(video_path, output_dir, frame_numbers, prefix, zfill_width)
    return processor.process(max_processes=8)


def main():
    """主函数：通过命令行交互获取参数，调用帧提取功能"""
    print("=" * 50)
    print("视频帧提取工具 (并行优化版)")
    print("=" * 50)

    # 获取视频路径和输出目录
    video_path = input("请输入视频文件路径: ").strip()
    output_dir = input("请输入输出目录: ").strip()

    # 按间隔提取帧模式
    print("\n按间隔提取帧模式")
    interval_str = input("请输入帧间隔 (0=连续帧, 1=间隔1帧, 2=间隔2帧... 默认: 0): ").strip()
    interval = int(interval_str) if interval_str else 0

    start_str = input("请输入起始帧号 (从0开始, 默认: 0): ").strip()
    start_frame = int(start_str) if start_str else 0

    end_str = input("请输入结束帧号 (留空表示到视频结束): ").strip()
    end_frame = int(end_str) if end_str else None

    prefix = input("请输入文件名前缀 (留空使用视频文件名): ").strip()

    print("\n开始提取...")
    start_time = time.time()
    success, saved_files = save_video_frames_with_interval(
        video_path,
        output_dir,
        interval,
        start_frame,
        end_frame,
        prefix
    )
    elapsed_time = time.time() - start_time

    if success:
        print(f"\n提取完成!")
        print(f"总处理时间: {elapsed_time:.2f} 秒")
    else:
        print(f"\n提取失败!")

    print("=" * 50)


if __name__ == "__main__":
    main()