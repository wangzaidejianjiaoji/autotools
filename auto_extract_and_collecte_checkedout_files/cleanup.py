"""
作用：
    一次性清理脚本：删除硬编码路径下的空目录（仅当目录存在且完全为空时调用 os.rmdir
    删除；目录不存在或不为空则只打印提示并不删除）。脚本非常简单，仅适合作为
    「多帧提取工具」运行后的辅助清理。

用法：
    python cleanup.py
    （脚本中目标目录硬编码，直接运行即可，无需命令行参数）

关键参数：
    - dir_path：硬编码目标目录 r"D:\\data\\Night\\multi_frame_test_set\\20260408_135424"
    - 删除条件：目录存在且 os.listdir(dir_path) 为空（使用 os.rmdir，非递归删除）
    - 状态输出：
        * 已删除空目录：{dir_path}
        * 目录不为空：{dir_path}
        * 目录不存在：{dir_path}
    - 脚本结束始终打印：清理完成
"""

import os

# 删除空目录
dir_path = r"D:\data\Night\multi_frame_test_set\20260408_135424"

if os.path.exists(dir_path):
    if not os.listdir(dir_path):
        os.rmdir(dir_path)
        print(f"已删除空目录：{dir_path}")
    else:
        print(f"目录不为空：{dir_path}")
else:
    print(f"目录不存在：{dir_path}")

print("清理完成")