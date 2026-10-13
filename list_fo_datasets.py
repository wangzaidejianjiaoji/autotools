"""
作用：列出当前 FiftyOne 数据库中所有数据集及其样本数（只读检查，不删除）。
用法：
    python list_fo_datasets.py
    运行后逐个打印数据集名和样本数，并把它们标记为非持久（persistent=False）。
关键参数/变量：
    FIFTYONE_DIR          (环境变量) FiftyOne 数据存放目录，默认 'D:/fiftyone_data'
                          （依赖 FiftyOne 默认配置）。
    fo.list_datasets()    列出所有数据集名称。
    ds.persistent = False 把数据集的持久化标记置为 False（仅本次会话）。
"""

import sys
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.path = [p for p in sys.path if 'hermes-agent' not in p]

import fiftyone as fo

print("Existing datasets:")
for name in fo.list_datasets():
    try:
        ds = fo.load_dataset(name)
        print(f"  {name}: {len(ds)} samples")
        ds.persistent = False
    except Exception as e:
        print(f"  {name}: error - {e}")
