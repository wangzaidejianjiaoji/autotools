import argparse
import json
import shutil
import sys
from pathlib import Path

ALLOWED_IDS = {"avata", "drone", "m300", "mavic", "p4"}


def should_keep(item: dict) -> bool:
    cid = item.get("classification_ID")
    if not isinstance(cid, str):
        return False
    return cid.lower() in ALLOWED_IDS


def filter_json(data: dict) -> bool:
    """过滤 DetbyStatus.real，返回是否保留该 JSON。"""
    detby = data.get("DetbyStatus")
    if not isinstance(detby, dict):
        return False
    real_list = detby.get("real")
    if not isinstance(real_list, list):
        return False

    filtered = [item for item in real_list if should_keep(item)]
    if not filtered:
        return False

    detby["real"] = filtered
    return True


def process_pair(jpg_path: Path, json_path: Path, output_dir: Path) -> bool:
    try:
        with json_path.open("r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        size = json_path.stat().st_size if json_path.exists() else -1
        reason = "JSON 文件为空" if size == 0 else f"JSON 格式错误（文件大小 {size} 字节）"
        print(f"警告：跳过 {json_path}: {reason}。原始错误：{e}", file=sys.stderr)
        return False
    except OSError as e:
        print(f"警告：读取 JSON 失败 {json_path}: {e}", file=sys.stderr)
        return False

    if not filter_json(data):
        return False

    output_dir.mkdir(parents=True, exist_ok=True)

    out_json = output_dir / json_path.name
    out_jpg = output_dir / jpg_path.name

    try:
        with out_json.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent="\t")
        shutil.copy2(jpg_path, out_jpg)
        return True
    except OSError as e:
        print(f"错误：写入输出文件失败: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description="按 classification_ID 过滤 debug.json 并复制关联图片")
    parser.add_argument("input_path", nargs="?", help="输入文件夹路径")
    args = parser.parse_args()

    input_path = args.input_path
    if not input_path:
        input_path = input("请输入输入文件夹路径：").strip()

    input_dir = Path(input_path)
    if not input_dir.is_dir():
        print(f"错误：输入路径不存在或不是目录：{input_dir}", file=sys.stderr)
        sys.exit(1)

    output_dir = input_dir / "二次分类结果上报数据"
    jpg_files = sorted(input_dir.glob("*.jpg"))

    valid_jpgs = set()
    valid_json_count = 0

    for jpg_path in jpg_files:
        stem = jpg_path.stem
        any_valid = False

        for json_path in sorted(input_dir.glob(f"{stem}_*.json")):
            if process_pair(jpg_path, json_path, output_dir):
                valid_json_count += 1
                any_valid = True

        if any_valid:
            valid_jpgs.add(jpg_path.name)

    print(f"处理完成。保留图片：{len(valid_jpgs)} 张，保留 JSON：{valid_json_count} 个。")
    print(f"输出目录：{output_dir}")


if __name__ == "__main__":
    main()
