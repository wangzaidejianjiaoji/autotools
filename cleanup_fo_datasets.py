"""
作用：列出并删除 FiftyOne 数据库中的全部数据集（清理 FiftyOne 数据存储）。
用法：
    python cleanup_fo_datasets.py
    脚本会自动遍历 fo.list_datasets() 并逐一删除，最后打印剩余数据集。
关键参数/变量：
    FIFTYONE_DIR          (环境变量) FiftyOne 数据存放目录，默认 'D:/fiftyone_data'
                          （由调用方或 FiftyOne 自身默认配置决定）。
    fo.list_datasets()    列出当前 FiftyOne 数据库中所有数据集名称的函数。
"""

import sys
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.path = [p for p in sys.path if 'hermes-agent' not in p]

import fiftyone as fo

print("Cleaning up datasets...")
for name in fo.list_datasets():
    try:
        ds = fo.load_dataset(name)
        ds.delete()
        print(f"  Deleted: {name}")
    except Exception as e:
        print(f"  Failed to delete {name}: {e}")

print(f"Remaining datasets: {fo.list_datasets()}")
