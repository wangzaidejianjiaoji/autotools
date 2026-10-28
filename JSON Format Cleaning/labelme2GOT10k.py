"""
labelme 标注 → GOT-10k 格式转换工具
流程：扫描图像 → 解析 labelme JSON 提取 drone bbox → 按遮挡/断层/长度规则动态切分序列
     → 输出 GOT-10k 目录（图像 + groundtruth.txt + absence/cover/cut_by_image.label + meta_info.ini）
    groundtruth.txt -- An N×4 matrix with each line representing object location [xmin, ymin, width, height] in one frame.
    cover.label -- An N×1 array representing object visible ratios, with levels ranging from 0~8. 0:完全不可见  8:完全可见
    absense.label -- An binary N×1 array indicating whether an object is absent or present in each frame. 0:目标缺席  1:目标在场
    cut_by_image.label -- An binary N×1 array indicating whether an object is cut by image in each frame. 0:未截断  1:是截断
    meta_info.ini -- Meta information about the sequence, including object and motion classes, video URL and more.
"""
import os
import json
import shutil
from tqdm import tqdm
import re
# ================= 配置区域 =================
FPS_ORIGINAL = 25  # 原始视频帧率
FRAME_STEP = 1  # 抽帧间隔 (每隔5帧抽1帧)

ABSENCE_THRESH_SEC = 30.0  # 【情况 B】长时遮挡/消失 阈值 (秒)
MAX_SEQ_LENGTH = 50000  # 【情况 C】最大序列长度 (帧)
MIN_SEQ_LENGTH = 50  # 强制切分后的最低序列长度限制 (帧)
FRAME_GAP_THRESH = 300  # 【情况 D】图像帧断层物理阈值 (>100帧自动切分)

EDGE_THRESHOLD = -1  # 截断判断阈值 cut_by_image设为1
IMG_FORMATS = ["bmp", "dng", "jpeg", "jpg", "mpo", "png", "tif", "tiff", "webp", "pfm"]

# ============================================

def parse_labelme_json(json_path, img_path=None):
    """解析单个 labelme JSON，返回 (img_w, img_h, class_name, bbox[x,y,w,h])
    无 drone 标注或解析失败时 bbox 返回 None（代表目标缺席帧）"""
    img_w, img_h = None, None
    class_name = "unknown"
    bbox = None

    # try:
    #     with Image.open(img_path) as img:
    #         img_w, img_h = img.size
    # except:
    #     pass

    if not os.path.exists(json_path):
        return img_w, img_h, class_name, None

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        img_w = data.get('imageWidth', img_w)
        img_h = data.get('imageHeight', img_h)

        shapes = data.get('shapes', [])
        if not shapes:
            return img_w, img_h, class_name, None

        # 优先取 "drone" 类型的 shape（忽略其他目标）
        shape = None
        for tmp_shape in shapes:
            cls_name = tmp_shape.get('label',"unknown")
            if cls_name.lower() in ["drone"]:
                shape = tmp_shape
                break

        if shape is None:
            return img_w, img_h, class_name, None

        class_name = shape.get('label', 'unknown')
        points = shape['points']

        # 由多边形/矩形顶点计算 xywh，并裁剪到图像边界内
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        x_min = max(0.0, min(xs))
        y_min = max(0.0, min(ys))
        x_max = min(float(img_w) if img_w else max(xs), max(xs))
        y_max = min(float(img_h) if img_h else max(ys), max(ys))

        bbox = [x_min, y_min, x_max - x_min, y_max - y_min]
    except Exception as e:
        pass

    return img_w, img_h, class_name, bbox


def save_got10k_sequence(seq_data, seq_name, output_dir,drop_edge=False):
    """将一个序列写出为 GOT-10k 标准目录：
    拷贝图像 + groundtruth.txt + absence/cover/cut_by_image.label + meta_info.ini
    drop_edge=True 时，bbox 触边的帧按缺席处理（全零框 + absence=1）"""
    seq_dir = os.path.join(output_dir, seq_name)
    os.makedirs(seq_dir, exist_ok=True)

    gt_lines, abs_lines, cover_lines, cut_lines = [], [], [], []
    # 用首个有效宽高作为元信息兜底值
    img_w_meta = seq_data[0].get('img_w') or 1920
    img_h_meta = seq_data[0].get('img_h') or 1080
    class_name_meta = "unknown"

    for item in seq_data:

        # 拷贝图像到序列目录（目标与源为同一文件时跳过，支持就地转换）
        dst_path = os.path.join(seq_dir, item['fname'])
        if os.path.abspath(dst_path) != os.path.abspath(item['fpath']):
            shutil.copy(item['fpath'], dst_path)

        # 记录首个有效类别名作为序列类别
        if item['class_name'] != "unknown":
            class_name_meta = item['class_name']
        img_w = item['img_w'] or img_w_meta
        img_h = item['img_h'] or img_h_meta

        if item['bbox'] is not None:
            x, y, w, h = item['bbox']

            # 判断 bbox 是否触碰图像边缘
            is_on_edge = (x <= EDGE_THRESHOLD or y <= EDGE_THRESHOLD or
                    (x + w) >= (img_w - EDGE_THRESHOLD) or
                    (y + h) >= (img_h - EDGE_THRESHOLD))

            if is_on_edge and drop_edge:
                # 触边且需丢弃 → 视为缺席帧
                gt_lines.append("0.0000,0.0000,0.0000,0.0000")
                abs_lines.append("1")
                cover_lines.append("0")
                cut_lines.append("0")
            else:
                # 正常帧；触边但保留时仅标记 cut_by_image=1
                gt_lines.append(f"{x:.4f},{y:.4f},{w:.4f},{h:.4f}")
                abs_lines.append("0")
                cover_lines.append("8")
                cut_lines.append("1" if is_on_edge else "0")
        else:
            # 无标注 → 缺席帧（GOT-10k 规范：全零框 + absence=1）
            gt_lines.append("0.0000,0.0000,0.0000,0.0000")
            abs_lines.append("1")
            cover_lines.append("0")
            cut_lines.append("0")

    def write_file(filename, lines):
        with open(os.path.join(seq_dir, filename), 'w') as f:
            f.write("\n".join(lines) + "\n")

    write_file('groundtruth.txt', gt_lines)
    write_file('absence.label', abs_lines)
    write_file('cover.label', cover_lines)
    write_file('cut_by_image.label', cut_lines)

    anno_fps = int(FPS_ORIGINAL / FRAME_STEP)
    meta_content = f"""[METAINFO]
url: 
begin: {seq_data[0]['fname'].replace('.jpg', '')}
end: {seq_data[-1]['fname'].replace('.jpg', '')}
anno_fps: {anno_fps}
object_class: {class_name_meta}
motion_class: fly
major_class: fly
root_class: {class_name_meta}
motion_adverb: fast
resolution: ({img_w_meta},{img_h_meta})
"""
    with open(os.path.join(seq_dir, 'meta_info.ini'), 'w') as f:
        f.write(meta_content)


def main(INPUT_DIR, OUTPUT_DIR,drop_edge=False):
    """主流程：扫描图像 → 自然边界切分 → 过滤/超长再切分 → 写出序列
    生成的新序列名会追加记录到 OUTPUT_DIR/tmp_list.txt"""

    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("正在扫描数据集...")

    # videos: {业务名: [(帧号, 文件名, 完整路径), ...]}
    videos = {}
    add_dirs = []
    for root, dirs, files in os.walk(INPUT_DIR):
        for file in files:
            # 只处理 jpg 图像文件
            suffix = file.rsplit('.',1)[-1].lower()
            if suffix in IMG_FORMATS:
                fpath = os.path.join(root, file)
                # 1. 提取直接父目录名称作为业务名
                # 例如 root="./raw/2024/cb_bridge"，那么 biz_name 就是 "cb_bridge"
                root = os.path.normpath(root)
                biz_name = os.path.basename(root)

                # 2. 从文件名中提取纯数字作为帧序号（替代正则表达式）
                # 无论文件叫 "0005.jpg" 还是 "img_0005.jpg"，提取出来的都是数字 5
                """
                digits = ''.join(filter(str.isdigit, file))
                frame_idx = int(digits) if digits else 0

                """
                name = os.path.splitext(os.path.basename(file))[0]
                # 取最后一个数字
                m = re.search(r'(\d+)$', name)
                frame_idx = int(m.group(1)) if m else 0

                if biz_name not in videos:
                    videos[biz_name] = []
                # 装载数据：(帧号, 文件名, 完整绝对路径)
                videos[biz_name].append((frame_idx, file, fpath))

    # 每个业务名的帧列表按帧号升序排列
    for biz_name in videos:
        videos[biz_name].sort(key=lambda x: x[0])

    if not videos:
        print(f"❌ 未在输入目录中找到任何 .jpg 图像，请检查: {INPUT_DIR}")
        return

    print("\n================ 开始动态切分与解析 ================")
    for biz_name, frames in tqdm(videos.items(), desc="处理业务序列"):

        # tqdm.write 可以在进度条上方安静地输出日志，不打断界面
        tqdm.write(f"\n▶ 正在处理原始视频池: {biz_name} (总共 {len(frames)} 张有效图像)")

        natural_tracks = []
        current_track = []
        last_seen_idx = None
        last_img_idx = None

        # ---------------- 第一阶段：扫描自然边界 ----------------
        for frame_idx, fname, fpath in frames:
            # labelme JSON 与图像同名（仅后缀不同）
            img_w, img_h, class_name, bbox = parse_labelme_json(fpath.replace(".jpg", ".json"), fpath)
            # 记录数据时多存一个 idx，用于后续打印日志
            item = {'idx': frame_idx, 'fname': fname, 'fpath': fpath,
                    'img_w': img_w, 'img_h': img_h, 'class_name': class_name, 'bbox': bbox}

            # 【情况 D】物理跳帧检测
            if last_img_idx is not None and (frame_idx - last_img_idx) > FRAME_GAP_THRESH:
                tqdm.write(
                    f"  [✂ 物理断层] 发现数据缺失: 帧号 {last_img_idx} 突然跳跃到 {frame_idx} (跨度>{FRAME_GAP_THRESH})，强制截断原序列！")
                if current_track:
                    natural_tracks.append(current_track)
                    current_track = []
                last_seen_idx = None

            last_img_idx = frame_idx

            # 序列尚未开始：等待首个可见目标帧作为起点
            if not current_track:
                if bbox is not None:
                    current_track.append(item)
                    last_seen_idx = frame_idx
                continue

            if bbox is not None:
                # 【情况 B】长时遮挡检测
                absence_time = (frame_idx - last_seen_idx) / FPS_ORIGINAL
                if absence_time > ABSENCE_THRESH_SEC:
                    tqdm.write(
                        f"  [✂ 长时遮挡] 目标从 {last_seen_idx} 帧消失到 {frame_idx} 帧再次出现，丢失 {absence_time:.1f} 秒 (>{ABSENCE_THRESH_SEC}s)，在此切分为新序列。")
                    natural_tracks.append(current_track)
                    current_track = [item]
                else:
                    # 【情况 A】短时遮挡 (内部自然容忍)
                    current_track.append(item)
                last_seen_idx = frame_idx
            else:
                # 无标注帧保留在序列内（输出时标记为缺席帧）
                current_track.append(item)

        # 收集最后一条未闭合的序列
        if current_track:
            natural_tracks.append(current_track)

        # ---------------- 第二阶段：二次过滤与收集 ----------------
        # 先完成全部切分收集最终序列，再统一命名写出
        final_tracks = []
        for track in natural_tracks:
            # 1. 剔除尾部空帧
            while track and track[-1]['bbox'] is None:
                track.pop()

            if not track:
                continue

            # 2. 短帧过滤
            if len(track) < MIN_SEQ_LENGTH:
                tqdm.write(
                    f"  [🗑 丢弃废卷] 序列区间 {track[0]['idx']}~{track[-1]['idx']} 长度仅 {len(track)} 帧 (不足{MIN_SEQ_LENGTH}帧)，被作为碎片丢弃。")
                continue

            # 3. 超长动态切分
            while len(track) > MAX_SEQ_LENGTH:
                max_k = min(MAX_SEQ_LENGTH, len(track) - MIN_SEQ_LENGTH)
                k = max_k

                # 回溯寻找可见目标帧作为下一个序列起点
                while k >= MIN_SEQ_LENGTH:
                    if track[k]['bbox'] is not None:
                        break
                    k -= 1

                sub_track = track[:k]
                tqdm.write(
                    f"  [📏 超长切分] 原序列长达 {len(track)} 帧(>{MAX_SEQ_LENGTH})！动态回溯至第 {sub_track[-1]['idx']} 帧安全切断。")

                final_tracks.append(sub_track)
                track = track[k:]

            # 4. 收集正常/剩余序列
            if len(track) >= MIN_SEQ_LENGTH:
                final_tracks.append(track)

        # ---------------- 第三阶段：统一命名并写出 ----------------
        # 仅当产出多条序列时才追加 _1/_2 序号；单序列直接用池名
        for i, seq_track in enumerate(final_tracks):
            if len(final_tracks) > 1:
                save_name = f"{biz_name}_{i + 1}"
            else:
                pool_dir = os.path.dirname(seq_track[0]['fpath'])
                if (os.path.abspath(os.path.join(OUTPUT_DIR, biz_name)) == os.path.abspath(pool_dir)
                        and len(seq_track) != len(frames)):
                    # 输出目录即源池目录、且序列未覆盖池内全部帧时，
                    # 就地写入会使 groundtruth 行数 < 目录图像数（加载错位），退回独立目录
                    save_name = f"{biz_name}_1"
                    tqdm.write(
                        f"  [⚠ 未全覆盖] 序列仅覆盖 {len(seq_track)}/{len(frames)} 帧，无法就地写入，改用独立目录 {save_name}。")
                else:
                    save_name = biz_name
            save_got10k_sequence(seq_track, save_name, OUTPUT_DIR,drop_edge=drop_edge)
            tqdm.write(
                f"  ✅ [成功生成] 序列: {save_name:<15} | 长度: {len(seq_track):<4} 帧 | 区间: {seq_track[0]['idx']} ~ {seq_track[-1]['idx']}")
            add_dirs.append(save_name)
    print("\n====================================================")
    print("🎯 全部转换已完成！数据集保存在:", OUTPUT_DIR)

    if len(add_dirs):
        add_list_file = os.path.join(OUTPUT_DIR,"tmp_list.txt")
        with open(add_list_file,"a",encoding="utf-8") as f:
            for d in add_dirs:
                f.write(d+"\n")


def create_dir_list(src_dir,sort=False):
    """将 src_dir 下所有子目录名写入 src_dir/list.txt（可选排序）"""
    dir_list = os.listdir(src_dir)
    if sort:
        dir_list = sorted(dir_list)
    file_path = os.path.join(src_dir, "list.txt")
    with open(file_path, "w") as f:
        for item in dir_list:
            full_path = os.path.join(src_dir, item)
            if os.path.isdir(full_path):
                f.write(f"{item}\n")

if __name__ == "__main__":

    INPUT_DIR = r"D:\data\Labeled_data\GR100_cb_unknow_day_unknow_合肥比测_260720_unknow_unknow_huanyu_jpg_可见光_mavic"  # 原始数据集路径（labelme 标注）
    OUTPUT_DIR = r"D:\data\Labeled_data\GR100_cb_unknow_day_unknow_合肥比测_260720_unknow_unknow_huanyu_jpg_可见光_mavic"    # GOT-10k 格式输出路径
    main(INPUT_DIR, OUTPUT_DIR,drop_edge=True)  # drop_edge=True: 触边目标按缺席处理
    #create_dir_list(OUTPUT_DIR)