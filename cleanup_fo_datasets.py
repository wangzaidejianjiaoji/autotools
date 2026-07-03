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
