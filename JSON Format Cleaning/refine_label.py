#!/usr/bin/env python3
import os
import cv2
import json
import glob
import shutil
import numpy as np


# ================================================

def extract_bbox(json_path):
    """从 labelme 的 json 文件中提取目标 bbox [x_min, y_min, x_max, y_max]"""
    if not os.path.exists(json_path):
        return None
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for shape in data.get('shapes', []):
            if shape['shape_type'] == 'rectangle':
                points = shape['points']
                x_min = min(points[0][0], points[1][0])
                y_min = min(points[0][1], points[1][1])
                x_max = max(points[0][0], points[1][0])
                y_max = max(points[0][1], points[1][1])
                return [int(x_min), int(y_min), int(x_max), int(y_max)]
    except Exception:
        pass
    return None

def calculate_iou(box1, box2):
    """计算两个边界框的 IoU"""
    if box1 is None or box2 is None:
        return 0.0
    x1_inter = max(box1[0], box2[0])
    y1_inter = max(box1[1], box2[1])
    x2_inter = min(box1[2], box2[2])
    y2_inter = min(box1[3], box2[3])

    if x1_inter >= x2_inter or y1_inter >= y2_inter:
        return 0.0

    inter_area = (x2_inter - x1_inter) * (y2_inter - y1_inter)
    box1_area = (box1[2] - box1[0]) * (box1[3] - box1[1])
    box2_area = (box2[2] - box2[0]) * (box2[3] - box2[1])
    union_area = box1_area + box2_area - inter_area
    return inter_area / union_area if union_area > 0 else 0.0

def draw_text(img, text, position, color=(255, 255, 255), font_scale=0.5, thickness=1):
    """辅助函数：在图像上画带黑色背景的小字，防止看不清"""
    font = cv2.FONT_HERSHEY_SIMPLEX
    (w, h), _ = cv2.getTextSize(text, font, font_scale, thickness)
    x, y = position
    cv2.rectangle(img, (x, y - h - 4), (x + w, y + 4), (0, 0, 0), -1)
    cv2.putText(img, text, (x, y), font, font_scale, color, thickness)

# 方向键键码：不同平台/OpenCV 版本返回值不同，统一兼容
KEY_LEFT = {ord('a'), ord('A'), 2424832, 65361}   # A / 左方向键 (Windows 0x250000 / Linux 0xFF51)
KEY_RIGHT = {ord('d'), ord('D'), 2555904, 65363}  # D / 右方向键 (Windows 0x270000 / Linux 0xFF53)

def get_key(delay):
    """读取按键，优先用 waitKeyEx 以正确识别方向键（旧版 OpenCV 回退到 waitKey）"""
    try:
        return cv2.waitKeyEx(delay)
    except AttributeError:
        return cv2.waitKey(delay)

def build_pred_index(pred_dir):
    """构建预测文件索引，兼容任意嵌套层数"""
    index = {}
    for root, dirs, files in os.walk(pred_dir):
        for f in files:
            if f.endswith(".json"):
                base = os.path.splitext(f)[0]
                seq_name = os.path.basename(root)
                index[(seq_name, base)] = os.path.join(root, f)
    return index

def main():
    print("正在扫描目录并计算 IoU，请稍候...")

    # 路径校验（Linux/Windows 路径不同，便于快速定位配置问题）
    if not os.path.isdir(PARENT_DIR_GT):
        print(f"[错误] GT 目录不存在：{PARENT_DIR_GT}")
        return
    if not os.path.isdir(PARENT_DIR_PRED):
        print(f"[错误] 预测目录不存在：{PARENT_DIR_PRED}")
        return

    # 构建预测文件索引（兼容多层嵌套目录）
    print("正在构建预测文件索引...")
    pred_index = build_pred_index(PARENT_DIR_PRED)
    print(f"索引构建完成！共找到 {len(pred_index)} 个预测文件。")

    # 1. 扫描并筛选数据
    image_paths = sorted(glob.glob(os.path.join(PARENT_DIR_GT, "*", "*.jpg")))
    review_list = []

    for img_path in image_paths:
        seq_name = os.path.basename(os.path.dirname(img_path))
        base_name = os.path.splitext(os.path.basename(img_path))[0]
        
        gt_json = os.path.join(PARENT_DIR_GT, seq_name, base_name + ".json")
        # 使用索引查找预测文件路径（兼容多层嵌套）
        pred_json = pred_index.get((seq_name, base_name))

        gt_box = extract_bbox(gt_json)
        pred_box = extract_bbox(pred_json) if pred_json else None
        
        iou = calculate_iou(gt_box, pred_box)
        
        # 筛选条件：IoU 小于等于阈值（含 0，覆盖一端漏标的情况）
        if 0 <= iou <= IOU_THRESHOLD:
            review_list.append({
                'img_path': img_path,
                'seq': seq_name,
                'frame': base_name,
                'gt_json': gt_json,
                'pred_json': pred_json,
                'gt_box': gt_box,
                'pred_box': pred_box,
                'iou': iou,
            })

    total = len(review_list)
    print(f"扫描完毕！共找到 {len(image_paths)} 张图片，其中 {total} 张 IoU <= {IOU_THRESHOLD} 需要审核。")
    if total == 0:
        return

    # 2. GUI 交互式审核
    idx = 0
    auto_play = False
    window_name = "Label Fixer (GT: Green, Pred: Red)"
    try:
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, 1280, 720)
    except cv2.error as e:
        print("[错误] 无法创建显示窗口，可能是安装了 opencv-python-headless（无 GUI 支持）。")
        print("       请执行: pip uninstall -y opencv-python-headless && pip install opencv-python")
        print(f"       详细错误: {e}")
        return

    while idx < total:
        item = review_list[idx]
        img = cv2.imread(item['img_path'])
        if img is None:
            idx += 1
            continue

        # 重新读取一次状态 (以防之前替换过，又回退来看)
        current_gt_box = extract_bbox(item['gt_json'])
        pred_box = item['pred_box']

        # 画 GT 框 (绿色 BGR)
        if current_gt_box:
            cv2.rectangle(img, (current_gt_box[0], current_gt_box[1]), 
                          (current_gt_box[2], current_gt_box[3]), (0, 255, 0), 2)
            cv2.putText(img, "GT", (current_gt_box[0], current_gt_box[1]-5), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        # 画 预测框 (红色 BGR)
        if pred_box:
            cv2.rectangle(img, (pred_box[0], pred_box[1]), 
                          (pred_box[2], pred_box[3]), (0, 0, 255), 2)
            cv2.putText(img, "Pred", (pred_box[0], pred_box[1]-5), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

        # 屏幕左上角显示前两行信息（小字体水印）
        draw_text(img, f"Progress: {idx+1}/{total}", (10, 20))
        draw_text(img, f"Seq: {item['seq']} | Frame: {item['frame']}", (10, 46))

        cv2.imshow(window_name, img)

        # 键盘事件处理逻辑
        delay = 300 if auto_play else 0
        key = get_key(delay)

        if key == 27 or key == ord('q') or key == ord('Q'):  # ESC / q 退出
            break
        elif key == ord(' '):  # 空格 播放/暂停
            auto_play = not auto_play
        elif key in KEY_LEFT:  # A 或 左方向键
            idx = max(0, idx - 1)
            auto_play = False
        elif key in KEY_RIGHT:  # D 或 右方向键
            idx = min(total - 1, idx + 1)
        elif key == 13 or key == ord('r') or key == ord('R'):  # Enter / r 替换
            if os.path.exists(item['pred_json']):
                # 执行文件覆盖
                shutil.copyfile(item['pred_json'], item['gt_json'])
                print(f"[OK] 已替换: {item['seq']}/{item['frame']}")
                # 重新计算当前帧并刷新显示
                # 故意不增加 idx，让用户能在屏幕上看到绿色 GT 框已经与红色 Pred 框重合
            else:
                print(f"[FAIL] 预测文件不存在，无法替换: {item['pred_json']}")
        elif auto_play and key == -1:  # 自动播放且超时无按键，前进一帧
            idx = min(total - 1, idx + 1)

    cv2.destroyAllWindows()
    print("审核退出。")

if __name__ == "__main__":
    # ==================== 配置区 ====================
    IOU_THRESHOLD = 0.8  # IoU 低于此值的会被筛选出来

    print("=" * 60)
    print("Label Fixer — 审核并替换标注 (GT vs 预测框)")
    print("=" * 60)

    # 交互输入两个目录路径（Linux/Windows 均可），并去掉用户可能粘贴的首尾引号/空格
    PARENT_DIR_GT = input("请输入 GT 目录（包含图片和 GT 标签的父目录）:\n> ").strip().strip('"\'')
    PARENT_DIR_PRED = input("请输入预测标签目录（包含预测标签的父目录）:\n> ").strip().strip('"\'')

    if not PARENT_DIR_GT or not PARENT_DIR_PRED:
        print("[错误] 两个目录均不能为空，程序退出。")
        import sys
        sys.exit(1)

    main()
