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
