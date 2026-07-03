import os
import sys
import argparse
import warnings
from typing import Optional, List, Tuple
import cv2

warnings.filterwarnings("ignore")

# 设置项目根目录的绝对路径
prj_path = '/home/vsg/wanghd/OSTrack'

# 将项目路径添加到系统路径中（如果尚未存在）
if prj_path not in sys.path:
    sys.path.append(prj_path)

# 从项目路径导入 Tracker 类
from lib.test.evaluation.tracker_autolabel import Tracker


class VideoTracker:
    """视频追踪器类，支持失败重试功能"""

    def __init__(self, tracker_name: str, tracker_param: str):
        """初始化追踪器

        Args:
            tracker_name: 追踪器名称
            tracker_param: 追踪器参数配置
        """
        self.tracker_name = tracker_name
        self.tracker_param = tracker_param
        self.tracker = None
        self.current_video = None

    def initialize_tracker(self) -> None:
        """初始化追踪器实例"""
        self.tracker = Tracker(self.tracker_name, self.tracker_param, "video")

    def select_roi_interactive(self, video_path: str) -> Optional[Tuple[int, int, int, int]]:
        """交互式选择ROI区域

        Args:
            video_path: 视频文件路径

        Returns:
            选择的ROI区域 (x, y, w, h) 或 None
        """
        cap = None
        try:
            # 打开视频文件
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                return None

            # 读取第一帧
            ret, frame = cap.read()
            if not ret:
                return None

            # 调整窗口大小以适应屏幕
            height, width = frame.shape[:2]
            max_height = 800
            resize_scale = 1.0
            
            if height > max_height:
                resize_scale = max_height / height
                new_width = int(width * resize_scale)
                frame = cv2.resize(frame, (new_width, max_height))

            # 选择ROI
            roi = cv2.selectROI(
                "选择目标区域", 
                frame,
                fromCenter=False, 
                showCrosshair=True
            )
            
            # 清理窗口
            cv2.destroyAllWindows()
            
            # 如果用户取消了选择
            if roi == (0, 0, 0, 0):
                return None

            # 如果调整了图像大小，需要调整ROI坐标
            if resize_scale != 1.0:
                roi = (
                    int(roi[0] / resize_scale), 
                    int(roi[1] / resize_scale),
                    int(roi[2] / resize_scale), 
                    int(roi[3] / resize_scale)
                )

            return roi

        except Exception:
            return None
        finally:
            if cap is not None:
                cap.release()

    def run_video_with_retry(self, video_path: str, optional_box: Optional[List[float]] = None,
                             debug: int = 0, save_results: bool = True, max_retries: int = 3) -> bool:
        """运行视频追踪，支持失败重试

        Args:
            video_path: 视频文件路径
            optional_box: 可选的初始边界框
            debug: 调试级别
            save_results: 是否保存结果
            max_retries: 最大重试次数

        Returns:
            是否成功完成追踪
        """
        self.current_video = video_path
        current_box = optional_box

        for attempt in range(1, max_retries + 1):
            # 处理初始框选择
            if attempt > 1:
                roi = self.select_roi_interactive(video_path)
                if roi is None:
                    return False
                current_box = list(roi)
            elif current_box is None:
                roi = self.select_roi_interactive(video_path)
                if roi is None:
                    return False
                current_box = list(roi)

            try:
                # 初始化追踪器（每次尝试都重新初始化）
                self.initialize_tracker()

                # 运行追踪
                self.tracker.run_video(
                    videofilepath=video_path,
                    optional_box=current_box,
                    debug=debug,
                    save_results=save_results,
                    save_video=False
                )

                return True

            except KeyboardInterrupt:
                if attempt >= max_retries:
                    return False

            except Exception:
                if attempt >= max_retries:
                    return False

        return False


def parse_args():
    """解析命令行参数

    Returns:
        解析后的参数对象
    """
    parser = argparse.ArgumentParser(
        description='运行目标追踪器处理视频文件，支持追踪失败时重新框选。',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # 必需参数
    parser.add_argument('--videofile', type=str, required=True,
                        help='视频文件路径 (必需)')

    # 追踪器配置参数
    parser.add_argument('--tracker_name', default="ostrack", type=str,
                        help='追踪器算法名称 (默认: %(default)s)')
    parser.add_argument('--tracker_param', default="vitb_384_mae_ce_32x4_ep300", type=str,
                        help='追踪器参数配置 (默认: %(default)s)')

    # 追踪参数
    parser.add_argument('--optional_box', type=float, default=None, nargs=4,
                        metavar=('X', 'Y', 'W', 'H'),
                        help='初始边界框 (格式: x y 宽度 高度)')
    parser.add_argument('--max_retries', type=int, default=3,
                        help='最大重试次数 (默认: %(default)s)')

    # 输出和调试参数
    parser.add_argument('--save_results', action='store_true', default=True,
                        help='保存追踪结果 (默认: %(default)s)')
    parser.add_argument('--no_save_results', dest='save_results', action='store_false',
                        help='不保存追踪结果')
    parser.add_argument('--output_dir', type=str, default=None,
                        help='结果输出目录 (默认: 视频文件所在目录)')
    parser.add_argument('--debug', type=int, default=0, choices=[0, 1, 2],
                        help='调试级别: 0=关闭, 1=基本, 2=详细 (默认: %(default)s)')

    # 显示参数帮助
    parser.add_argument('--version', action='version', version='%(prog)s 1.0')

    return parser.parse_args()


def validate_args(args) -> bool:
    """验证参数有效性

    Args:
        args: 命令行参数

    Returns:
        参数是否有效
    """
    # 检查视频文件是否存在
    if not os.path.exists(args.videofile):
        return False

    # 检查可选框参数
    if args.optional_box and len(args.optional_box) != 4:
        return False

    # 检查可选框参数值
    if args.optional_box:
        x, y, w, h = args.optional_box
        if w <= 0 or h <= 0:
            return False

    # 检查最大重试次数
    if args.max_retries < 1:
        return False

    # 检查调试级别
    if args.debug not in [0, 1, 2]:
        return False

    # 检查输出目录
    if args.output_dir and not os.path.exists(args.output_dir):
        try:
            os.makedirs(args.output_dir, exist_ok=True)
        except Exception:
            return False

    return True


def main():
    """主函数"""
    # 解析命令行参数
    args = parse_args()

    # 验证参数
    if not validate_args(args):
        sys.exit(1)

    # 创建视频追踪器
    tracker = VideoTracker(args.tracker_name, args.tracker_param)

    # 运行追踪（支持重试）
    success = tracker.run_video_with_retry(
        video_path=args.videofile,
        optional_box=args.optional_box,
        debug=args.debug,
        save_results=args.save_results,
        max_retries=args.max_retries
    )

    # 退出程序
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
