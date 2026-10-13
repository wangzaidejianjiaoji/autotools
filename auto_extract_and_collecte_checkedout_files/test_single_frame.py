#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
作用：
    简易启动器：直接通过 os.system 调用同目录下的 auto_multi_frame_collect4.0.py，
    等价于「运行 4.0 版多帧提取工具」。适合在 IDE 中点击运行本脚本即可触发主流程，
    不必每次去命令行敲路径。
    注：此脚本未对 auto_multi_frame_collect4.0.py 的入参做封装，所有交互输入由主脚本负责。

用法：
    python test_single_frame.py
    （无命令行参数；运行后即调用同目录下的 auto_multi_frame_collect4.0.py）

关键参数：
    - __file__：当前脚本所在目录，通过 os.path.dirname(__file__) 取得
    - target_script：自动拼接得到的脚本路径
      {脚本所在目录}/auto_multi_frame_collect4.0.py
    - 调用方式：os.system(f"python {target_script}")
    - 默认 Python 解释器：依赖环境变量中名为 python 的可执行命令
      （Windows 推荐确保 python 指向与 IDE 相同的解释器）
"""

import sys
import os

# 直接运行主脚本
os.system(f"python {os.path.join(os.path.dirname(__file__), 'auto_multi_frame_collect4.0.py')}")
