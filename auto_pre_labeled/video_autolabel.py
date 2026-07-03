import os
import sys
import argparse
import warnings
warnings.filterwarnings("ignore")

prj_path = os.path.join(os.path.dirname(__file__), '..')
if prj_path not in sys.path:
    sys.path.append(prj_path)

try:
    # 尝试从 OSTrack 目录导入
    import sys
    ostrack_path = os.path.join(os.path.dirname(__file__), '..', 'wanghd', 'OSTrack')
    sys.path.append(ostrack_path)
    from lib.test.evaluation.tracker_autolabel import Tracker
except ImportError:
    print("错误: 无法导入 Tracker 类")
    print(f"请确保 OSTrack 目录存在且包含 lib.test.evaluation.tracker_autolabel 模块")
    print(f"当前 OSTrack 路径: {ostrack_path}")
    sys.exit(1)


class VideoTracker:
    """视频追踪器类，支持追踪失败时重新框选"""

    def __init__(self, tracker_name, tracker_param):
        """初始化追踪器

        Args:
            tracker_name: 追踪器名称
            tracker_param: 追踪器参数
        """
        self.tracker_name = tracker_name
        self.tracker_param = tracker_param
        self.tracker = None

    def initialize_tracker(self):
        """初始化追踪器实例"""
        self.tracker = Tracker(self.tracker_name, self.tracker_param, "video")

    def run_video_with_retry(self, videofile, optional_box=None, debug=None, save_results=False, fps_boost=False):
        """运行视频追踪，支持追踪失败时重新选择目标

        Args:
            videofile: 视频文件路径
            optional_box: 可选的初始边界框
            debug: 调试级别
            save_results: 是否保存结果
            fps_boost: 是否启用帧率提升模式
        """
        while True:
            try:
                # 初始化追踪器
                self.initialize_tracker()
                
                print("\n开始追踪...")
                print("追踪过程中按 'r' 键可以重新选择目标")
                print("按 'q' 键退出程序")
                
                # 运行追踪
                self.tracker.run_video(
                    videofilepath=videofile, 
                    optional_box=optional_box, 
                    debug=debug, 
                    save_results=save_results,
                    save_video=False,
                    fps_boost=fps_boost
                )
                
                # 追踪完成
                print("\n追踪完成!")
                break
                
            except KeyboardInterrupt:
                print("\n用户中断了追踪")
                break
                
            except Exception as e:
                print(f"\n追踪过程中出错: {e}")
                print("是否重新选择目标并继续追踪？")
                print("按 'y' 重新选择目标，按 'n' 退出")
                
                user_input = input().strip().lower()
                if user_input == 'n':
                    print("用户退出追踪")
                    break
                elif user_input == 'y':
                    print("准备重新选择目标...")
                    # 重置 optional_box 为 None，这样会重新提示选择目标
                    optional_box = None
                else:
                    print("无效输入，退出追踪")
                    break


def main():
    parser = argparse.ArgumentParser(description='Run the tracker on your webcam.')
    parser.add_argument('--tracker_name', default="ostrack", type=str, help='Name of tracking method.')
    parser.add_argument('--tracker_param', default="vitb_384_mae_ce_32x4_ep300", type=str, help='Name of parameter file.')
    parser.add_argument('--videofile', type=str, required=True, help='path to a video file.')
    parser.add_argument('--optional_box', type=float, default=None, nargs="+", help='optional_box with format x y w h.')
    parser.add_argument('--debug', type=int, default=0, help='Debug level.')
    parser.add_argument('--save_results', dest='save_results', action='store_true', default=True, help='Save bounding boxes')
    parser.add_argument('--fps_boost', dest='fps_boost', action='store_true', default=False, help='Enable FPS boost mode')

    args = parser.parse_args()
    print(args)

    # 创建视频追踪器
    tracker = VideoTracker(args.tracker_name, args.tracker_param)
    
    # 运行追踪（支持重试）
    tracker.run_video_with_retry(
        videofile=args.videofile, 
        optional_box=args.optional_box, 
        debug=args.debug, 
        save_results=args.save_results,
        fps_boost=args.fps_boost
    )


if __name__ == '__main__':
    main()
