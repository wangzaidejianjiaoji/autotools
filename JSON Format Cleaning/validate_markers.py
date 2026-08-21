#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
r"""
标记 JSON 校验脚本 (validate_markers.py)
====================================================================
依据文档: 同目录下 示例及字典.json (字段字典) 与 完整示例.json (样例)
功能: 遍历输入路径(交互输入或命令行参数)及其所有下级目录, 对每个 JSON 文件
      与每个子目录名 校验:
        1. 文件名/目录名: 是否符合 13 段下划线拼接命名规范, 各段取值是否在字典内
                   (多值段用 '-' 连接; 去重后缀 __N; 允许 image/jpg、video/MP4 等价;
                    lens 字典值 huanyu_ir/hope_ir 内含下划线, 按单段计不拆)
                   (所有层级子目录名均按同样规范校验, 目录名须严格 13 段)
        2. 内容  : 13 个必填字段是否齐全, 各字段取值是否在字典内
                   (date 校验 YYMMDD; distance 校验 <起>-<止>m / <数值>m;
                    zoom 校验 <起>-<止>zoom / <数值>zoom, 兼容 x 后缀)
      问题(缺失字段 / 不在字典内的取值 / 命名不规范 / 文件名与内容不一致 /
            JSON 解析失败) 均输出文件的完整路径。
      文件名与内容一致性比对时, lens 与 spectral 联动归一化: 光谱段为红外时,
      huanyu/huanyu_ir、hope/hope_ir 视为等效取值, 不误报不一致。
      段数异常的命名会给出"改建建议"(完整 13 段建议名 + 缺失字段说明),
      配合 --apply 可一键按建议重命名。
兼容性: Windows / Linux 均无第三方依赖, 纯标准库; Windows 盘符路径(D:\...)
        在 Linux 下自动尝试 /mnt/<盘符>/... 挂载点, 找不到时给出明确提示,
        不会抛出异常中断。
用法:
    python validate_markers.py [输入路径] [选项]
    不带路径参数时进入交互输入提示。
选项:
    --dict FILE         指定字典 JSON (默认取脚本同目录 示例及字典.json)
    --extra-dict FILE   追加允许取值, 形如 {"location": ["miyun", ...]}
    --output FILE       将完整报告同时写入该文件
    --strict-unknow     严格模式: unknow 仅在字段自身字典显式列出时允许
    --show-ok           同时列出完全通过的 JSON 文件
    --show-skipped      同时列出被跳过的非标记 JSON 文件
    --apply             一键按"改建建议"重命名 (重名自动追加 __N 去重后缀)
退出码: 0 = 全部通过; 1 = 存在校验问题; 2 = 输入路径无效/参数错误
"""

import os
import re
import sys
import json

# ============================================================
# 常量与字段定义 (对齐 示例及字典.json)
# ============================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DICT = os.path.join(SCRIPT_DIR, "示例及字典.json")

# 13 段字段顺序 (与 数据标记JSON生成方案.md §2 / generate_markers.py 一致)
FIELD_ORDER = [
    "device", "complexBg", "bgType", "captureTime", "weather",
    "location", "date", "distance", "zoom", "lens",
    "mediaType", "spectral", "targetType",
]
FIELD_SET = set(FIELD_ORDER)

UNK = "unknow"

# 字典文件中非字段定义键 (样例/说明, 解析时跳过)
NON_FIELD_KEYS = {"图片标记样例", "视频标记样例", "说明", "必填项"}

# 格式字段正则
DATE_RE = re.compile(r"^\d{6}$")                 # YYMMDD
DISTANCE_RE = re.compile(r"^\d+(?:-\d+)?m$")     # <起>-<止>m 或 <数值>m
ZOOM_RE = re.compile(r"^\d+(?:-\d+)?(?:zoom|x)$", re.I)  # <起>-<止>zoom / <数值>zoom, 兼容 1x

# 文件名 mediaType 段的等价写法: 规范值 image/video <-> 样例写法 jpg/MP4
MEDIA_TYPE_ALIAS = {
    "image": "image", "jpg": "image", "jpeg": "image",
    "video": "video", "mp4": "video",
}

# 由内容生成建议文件名时, mediaType 段按实际命名惯例取 jpg/MP4 (对齐 完整示例.json)
MEDIA_TYPE_NAME_ALIAS = {
    "image": "jpg", "video": "MP4",
}

# 命名去重后缀: 如 _bird__48.json / 同名追加 __2
DEDUP_RE = re.compile(r"__\d+$")
# 超长压缩命名: 如 mavic+5 (generate_markers.py compact 模式)
COMPACT_RE = re.compile(r"\+(\d+)$")

# 终端高亮: 缺失位置以红色字段名提示 (写文件时剥离 ANSI)
RED = "\033[31m"
RESET = "\033[0m"
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def red_text(s):
    """终端红色文本。"""
    return "%s%s%s" % (RED, s, RESET)

# ============================================================
# 字典解析
# ============================================================
def load_dict(path):
    """解析字典 JSON, 返回 {字段: {"allowed": 可选值set, "fmt": 格式/None, "name": 中文名}}。"""
    with open(path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("字典文件顶层必须是对象")
    meta = {}
    for key, val in data.items():
        if key in NON_FIELD_KEYS or not isinstance(val, dict):
            continue
        if not any(k in val for k in ("可选值", "格式")):
            continue
        allowed = set()
        if "可选值" in val:
            opt = val["可选值"]
            if isinstance(opt, dict):
                allowed = set(opt.keys())
            elif isinstance(opt, list):
                allowed = set(str(v) for v in opt)
        meta[key] = {
            "name": val.get("中文名", key),
            "allowed": allowed,
            "fmt": val.get("格式"),
        }
    missing = [k for k in FIELD_ORDER if k not in meta]
    if missing:
        raise ValueError("字典文件缺少字段定义: %s" % ", ".join(missing))
    return meta


def load_extra_dict(path):
    """追加允许取值, 形如 {"字段": [值, ...]}。"""
    with open(path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("--extra-dict 文件顶层必须是对象")
    return {k: set(str(v) for v in vals) for k, vals in data.items()
            if isinstance(vals, (list, set, tuple))}


# ============================================================
# 路径解析 (跨平台: Windows 盘符路径在 Linux 下尝试 /mnt/<盘符>)
# ============================================================
def resolve_path(raw):
    """规范化输入路径。返回 (绝对路径, 提示信息或None)。"""
    raw = (raw or "").strip().strip('"').strip("'")
    if not raw:
        return None, "输入路径为空"
    raw = os.path.expanduser(raw)

    # 在 Linux / macOS 下遇到 Windows 盘符路径 (D:\... 或 D:/...) 时尝试挂载点
    if os.name != "nt":
        m = re.match(r"^([A-Za-z]):[\\/](.*)$", raw, re.S)
        if m:
            drive, rest = m.group(1).lower(), m.group(2)
            rest = rest.replace("\\", os.sep).replace("/", os.sep)
            cand = os.path.join(os.sep + "mnt", drive, rest)
            if os.path.exists(cand):
                return os.path.abspath(cand), "已转换 Windows 盘符路径: %s -> %s" % (raw, cand)
            return os.path.abspath(raw), ("Windows 盘符路径在 Linux 下未找到挂载点 "
                                          "(已尝试 %s), 请确认盘符已挂载或直接输入 Linux 路径" % cand)

    p = os.path.abspath(raw)
    if not os.path.exists(p):
        return p, None
    return p, None


# ============================================================
# 标记 JSON 识别
# ============================================================
def is_marker_filename(fname):
    """按文件名判断: 光谱段含 可见光/红外 即视为标记 JSON (与生成脚本口径一致)。"""
    return "可见光" in fname or "红外" in fname


def looks_like_marker_content(obj):
    """按内容判断: 扁平对象含任一 13 字段键, 或 "图片标记样例"/"视频标记样例" 包装
    格式的 "内容" 对象含任一 13 字段键, 视为标记 JSON (兜底文件名不规范的情况)。"""
    if not isinstance(obj, dict):
        return False
    if FIELD_SET.intersection(obj.keys()):
        return True
    for wkey in ("图片标记样例", "视频标记样例"):
        w = obj.get(wkey)
        if isinstance(w, dict) and isinstance(w.get("内容"), dict) \
                and FIELD_SET.intersection(w["内容"].keys()):
            return True
    return False


# ============================================================
# 单值 / 单段校验
# ============================================================
def check_value(field, value, meta, strict_unknow):
    """校验单个取值(字符串)是否合法。返回违规说明列表, 空列表表示合法。"""
    value = value.strip()
    issues = []
    if value == UNK:
        if strict_unknow and UNK not in meta[field]["allowed"]:
            issues.append("取值不在字典: %s = \"%s\" (字典含: %s)"
                          % (field, value, allowed_preview(meta[field])))
        return issues
    if value in meta[field]["allowed"]:
        return issues
    fmt = meta[field]["fmt"]
    if fmt and field == "date" and DATE_RE.match(value):
        return issues
    if fmt and field == "distance" and DISTANCE_RE.match(value):
        return issues
    if fmt and field == "zoom" and ZOOM_RE.match(value):
        return issues
    issues.append("取值不在字典: %s = \"%s\" (字典含: %s)"
                  % (field, value, allowed_preview(meta[field])))
    return issues


def check_segment(field, seg, meta, strict_unknow):
    """校验文件名中的一个下划线段。段内多值用 '-' 连接, 也可能为范围值(如 50-150m)。
    策略: 整段合法 -> 通过; 否则拆 '-' 逐值校验。返回违规说明列表。"""
    issues = []
    seg = seg.strip()
    if not seg:
        return ["命名段为空: 字段 %s" % field]
    compact = COMPACT_RE.search(seg)
    core = COMPACT_RE.sub("", seg) if compact else seg
    # 整段先试 (范围值如 50-150m / 1-3zoom 整段即合法, 避免误拆)
    if not check_value(field, core, meta, strict_unknow):
        return issues
    if "-" in core:
        for part in core.split("-"):
            issues.extend(check_value(field, part, meta, strict_unknow))
    if compact:
        issues.append("命名段为压缩格式(compact): %s = \"%s\", 无法与内容逐一比对"
                      % (field, seg))
    return issues


def allowed_preview(field_meta):
    """取字典可选值的展示文本。"""
    vals = sorted(field_meta["allowed"])
    preview = ", ".join(vals[:8])
    if len(vals) > 8:
        preview += ", ..."
    if field_meta["fmt"]:
        preview += " [格式: %s]" % field_meta["fmt"]
    return preview


# ============================================================
# 文件名校验
# ============================================================
def _try_merge_underscore(segs, meta):
    """相邻两段按 '_' 拼回字典中的合法值(如 lens 的 huanyu_ir / hope_ir),
    使段数精确回到 13。仅当合并后恰好对齐字段数时生效, 否则返回 None。
    例如 14 段的 ...huanyu_ir_jpg... 实际为 13 段: lens=huanyu_ir。"""
    need = len(segs) - len(FIELD_ORDER)
    if need <= 0:
        return None
    candidates = []
    for i in range(len(segs) - 1):
        cand = segs[i] + "_" + segs[i + 1]
        if any(cand in meta[f]["allowed"] for f in FIELD_ORDER):
            candidates.append((i, cand))
    picks, used = [], set()
    for i, cand in candidates:
        if i in used or i + 1 in used:
            continue
        picks.append((i, cand))
        used.update((i, i + 1))
        if len(picks) == need:
            break
    if len(picks) != need:
        return None
    by_idx = dict(picks)
    out = []
    for idx, s in enumerate(segs):
        if idx in by_idx:
            out.append(by_idx[idx])
        elif idx - 1 in by_idx:
            continue  # 已被前一段合并吞掉
        else:
            out.append(s)
    return out if len(out) == len(FIELD_ORDER) else None


def parse_filename(fname, meta=None):
    """解析标记文件名。返回 (字段段dict, 问题列表)。
    期望 13 段; 先剥离 .json 与 __N 去重后缀。
    meta 非空时, 若拆分段数 > 13, 尝试把含下划线的字典合法值(lens 的
    huanyu_ir / hope_ir)合并回单段, 避免被误计为多段。"""
    issues = []
    base = fname[:-5] if fname.lower().endswith(".json") else fname
    base = DEDUP_RE.sub("", base)
    segs = base.split("_")
    if meta is not None and len(segs) != len(FIELD_ORDER):
        merged = _try_merge_underscore(segs, meta)
        if merged is not None:
            segs = merged
    if len(segs) != len(FIELD_ORDER):
        return None, ["文件名段数异常: 期望 %d 段, 实际 %d 段" % (len(FIELD_ORDER), len(segs))]
    return dict(zip(FIELD_ORDER, segs)), issues


def _seg_matches_field(s, field, meta):
    """判断段 s 是否可作为字段 field 的合法取值(用于对齐生成建议名)。"""
    if s == UNK:
        return True  # unknow 通用允许(非严格模式)
    if s in meta[field]["allowed"]:
        return True
    if field == "mediaType" and s.lower() in MEDIA_TYPE_ALIAS:
        return True
    if field == "date" and DATE_RE.match(s):
        return True
    if field == "distance" and DISTANCE_RE.match(s):
        return True
    if field == "zoom" and ZOOM_RE.match(s):
        return True
    return False


def _inherited_value(field, parents_parsed, meta):
    """从上层目录(近->远)解析出的字段段中, 取第一个能作为 field 合法取值的值。"""
    for segs in parents_parsed:
        if segs and field in segs and _seg_matches_field(segs[field], field, meta):
            return segs[field]
    return None


def _try_load_json(path):
    """读取 JSON, UTF-8 优先 GBK 回退; 失败返回 None。"""
    for enc in ("utf-8-sig", "gbk"):
        try:
            with open(path, "r", encoding=enc) as f:
                return json.load(f)
        except (UnicodeDecodeError, json.JSONDecodeError, OSError):
            continue
    return None


def infer_dir_values(dirpath, meta):
    """从目录内容推断缺失字段值, 返回 {字段: 值}。
    来源(仅当取值唯一时采纳):
      1. 目录内标记JSON内容(含 13 字段键)的各字段取值;
      2. 本目录及下级媒体文件扩展名 -> mediaType (jpg/png..=image, mp4/avi..=video);
      3. 本目录及下级文件名/子目录名中的 可见光/红外 -> spectral。"""
    IMG_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}
    VID_EXT = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv", ".m4v"}
    vals = {}
    media_hits = set()
    spectral_hits = set()
    for dp, dns, fns in os.walk(dirpath):
        for fn in fns:
            low = fn.lower()
            ext = os.path.splitext(low)[1]
            if ext in IMG_EXT:
                media_hits.add("image")
            elif ext in VID_EXT:
                media_hits.add("video")
            for k in ("红外", "可见光"):
                if k in fn:
                    spectral_hits.add(k)
            if ext == ".json":
                obj = _try_load_json(os.path.join(dp, fn))
                if isinstance(obj, dict) and FIELD_SET.intersection(obj):
                    for f in FIELD_ORDER:
                        if f in obj and f not in vals:
                            v = str(obj[f])
                            if f == "mediaType":
                                v = MEDIA_TYPE_ALIAS.get(v.lower(), v)
                                v = "image" if v == "image" else ("video" if v == "video" else v)
                            vals[f] = v
        for dn in dns:
            for k in ("红外", "可见光"):
                if k in dn:
                    spectral_hits.add(k)
    if "mediaType" not in vals and len(media_hits) == 1:
        vals["mediaType"] = media_hits.pop()
    if "spectral" not in vals and len(spectral_hits) == 1:
        vals["spectral"] = spectral_hits.pop()
    return vals


def _fill_missing(field, parents_parsed, extra_vals, meta):
    """缺失字段取值: 目录内容推断 > 上层目录继承 > unknow。返回 (值, 来源)。"""
    if extra_vals and field in extra_vals:
        v = extra_vals[field]
        if _seg_matches_field(v, field, meta):
            return v, "inferred"
    v = _inherited_value(field, parents_parsed, meta)
    if v is not None:
        return v, "inherited"
    return UNK, "missing"


def find_marker_json_name(dirpath, meta):
    """递归扫描目录, 返回第一个命名合规(13 段)的标记 JSON 文件名(去扩展名), 无则 None。"""
    for dp, dns, fns in os.walk(dirpath):
        for fn in sorted(fns):
            if fn.lower().endswith(".json"):
                segs, _ = parse_filename(fn, meta)
                if segs is not None:
                    return fn[:-5] if fn.lower().endswith(".json") else fn
    return None


def match_json_to_dir(name, json_names, meta):
    """在合规标记 JSON 文件名中匹配与目录名字段重合度最高的一个。
    返回 json 名(去扩展名)或 None(无可靠匹配)。"""
    base = DEDUP_RE.sub("", name)
    segs = base.split("_")
    if len(segs) != len(FIELD_ORDER):
        merged = _try_merge_underscore(segs, meta)
        if merged is not None:
            segs = merged
    best, best_score = None, -1
    for jn in json_names:
        jsegs, _ = parse_filename(jn, meta)
        if jsegs is None:
            continue
        score, total = 0, 0
        i = 0
        for field in FIELD_ORDER:
            if i >= len(segs):
                break
            if field == "targetType":
                # 目录 targetType 多值(误用 '_')中包含 json 值即算匹配
                if any(p == jsegs[field] for p in segs[i:]):
                    score += 1
                break
            s = segs[i]
            if _seg_matches_field(s, field, meta):
                if field == "distance" and s != jsegs[field]:
                    total = 0  # 距离段不一致, 该 JSON 不视为匹配
                    break
                total += 1
                if s == jsegs[field]:
                    score += 1
                i += 1
        if total and score / total >= 0.7 and score > best_score:
            best_score, best = score, jn
    return best


def suggest_from_reference(name, ref_segs, meta):
    """以合规标记 JSON 文件名为参考生成目录名改建建议。
    建议名各段取参考 JSON 值, 原目录缺失(或与参考不一致)的位置红色标注。
    返回 (彩色建议名, 纯文本建议名, 缺失字段列表)。"""
    base = DEDUP_RE.sub("", name)
    if base.lower().endswith(".json"):
        base = base[:-5]  # 兼容传入带 .json 的文件名
    segs = base.split("_")
    if len(segs) != len(FIELD_ORDER):
        merged = _try_merge_underscore(segs, meta)
        if merged is not None:
            segs = merged
    missing = []
    i = 0
    for field in FIELD_ORDER:
        if i >= len(segs):
            missing.append(field)
            continue
        if field == "targetType":
            # 剩余段(可能多值误用 '_' 连接)与参考目标类型比对, 不一致才计缺失
            leftover = segs[i:]
            if not leftover or "-".join(leftover) != ref_segs[field]:
                missing.append(field)
            i = len(segs)
            continue
        s = segs[i]
        if _seg_matches_field(s, field, meta):
            i += 1
        else:
            missing.append(field)
    plain_parts, colored_parts = [], []
    for field in FIELD_ORDER:
        v = ref_segs[field]
        if field in missing:
            plain_parts.append(v)
            colored_parts.append(red_text(v))
        else:
            plain_parts.append(v)
            colored_parts.append(v)
    return "_".join(colored_parts), "_".join(plain_parts), missing


def suggest_rename(name, meta, parents=(), extra_vals=None):
    """为段数不合规的命名生成改建建议名。返回 (彩色建议名, 纯文本建议名,
    缺失字段, 继承字段, 内容推断字段)。
    缺失字段取值来源(优先): 目录内容推断(extra_vals) > 上层目录(parents) 继承;
    均无则该位置以红色字段名标注(如 targetType), 提示缺哪个字段。
    补上的值(继承/推断)同样视为原命名缺失, 建议中红色标注。"""
    ext = ".json" if name.lower().endswith(".json") else ""
    base = name[:-5] if ext else name
    base = DEDUP_RE.sub("", base)
    segs = base.split("_")
    if len(segs) != len(FIELD_ORDER):
        merged = _try_merge_underscore(segs, meta)
        if merged is not None:
            segs = merged
    if len(segs) == len(FIELD_ORDER):
        return None  # 段数已合规, 取值问题另报, 无需改名建议

    # 解析上层目录名(近->远), 用于缺失字段取值继承
    parents_parsed = []
    for p in parents:
        psegs, _ = parse_filename(p, meta)
        parents_parsed.append(psegs)

    parts = []
    missing = []    # 原命名缺失且未推断/继承到值
    inherited = []  # 原命名缺失, 值继承自上层目录
    inferred = []   # 原命名缺失, 值来自目录内容/下级推断
    i = 0
    for field in FIELD_ORDER:
        if i >= len(segs):
            val, src = _fill_missing(field, parents_parsed, extra_vals, meta)
            if src == "inherited":
                inherited.append(field)
            elif src == "inferred":
                inferred.append(field)
            else:
                missing.append(field)
            parts.append(val)
            continue
        if field == "targetType":
            # 剩余段均视为目标类型(可能多值误用 '_' 连接), 全部消费并改 '-' 连接;
            # 若剩余段与目标类型字典不符(如 aaa), 视为缺失, 从上层目录/推断取值
            leftover = segs[i:]
            if leftover and all(_seg_matches_field(p, field, meta) for p in leftover):
                parts.append("-".join(leftover))
                i = len(segs)
                break
            val, src = _fill_missing(field, parents_parsed, extra_vals, meta)
            if src == "inherited":
                inherited.append(field)
            elif src == "inferred":
                inferred.append(field)
            else:
                missing.append(field)
            parts.append(val)
            i = len(segs)
            break
        s = segs[i]
        if _seg_matches_field(s, field, meta):
            parts.append(s)
            i += 1
        else:
            val, src = _fill_missing(field, parents_parsed, extra_vals, meta)
            if src == "inherited":
                inherited.append(field)
            elif src == "inferred":
                inferred.append(field)
            else:
                missing.append(field)
            parts.append(val)
    if len(parts) != len(FIELD_ORDER):
        return None

    plain_parts, colored_parts = [], []
    for field, part in zip(FIELD_ORDER, parts):
        if field in missing:
            plain_parts.append(field)
            colored_parts.append(red_text(field))
        elif field in inherited or field in inferred:
            plain_parts.append(part)
            colored_parts.append(red_text(part))
        else:
            plain_parts.append(part)
            colored_parts.append(part)
    plain = "_".join(plain_parts) + ext
    colored = "_".join(colored_parts) + ext
    return colored, plain, missing, inherited, inferred


def check_filename(fname, meta, strict_unknow):
    """校验文件名各段取值。返回 (字段段dict, 问题列表)。"""
    segs, issues = parse_filename(fname, meta)
    if segs is None:
        return segs, issues
    for field in FIELD_ORDER:
        seg = segs[field]
        if field == "mediaType":
            # 文件名段允许 image/video 与样例写法 jpg/MP4
            tok = seg.lower()
            if tok not in MEDIA_TYPE_ALIAS and tok != UNK:
                issues.append("取值不在字典: %s = \"%s\" (文件名段允许: image/video/jpg/MP4/%s)"
                              % (field, seg, UNK))
            elif strict_unknow and tok == UNK and UNK not in meta[field]["allowed"]:
                issues.append("取值不在字典: %s = \"%s\" (字典含: %s)"
                              % (field, seg, allowed_preview(meta[field])))
            continue
        issues.extend(check_segment(field, seg, meta, strict_unknow))
    return segs, issues


# ============================================================
# 内容校验
# ============================================================
def check_content(obj, meta, strict_unknow):
    """校验 JSON 内容: 13 必填字段齐全 + 取值在字典内。返回问题列表。
    缺失字段名以红色标注(终端高亮), 与目录改建建议风格一致。"""
    issues = []
    if not isinstance(obj, dict):
        return ["内容不是扁平对象(顶层非 object), 无法按标记规范校验"]
    missing = [k for k in FIELD_ORDER if k not in obj]
    if missing:
        issues.append("缺失字段: %s (共 %d 项必填)"
                      % (", ".join(red_text(k) for k in missing), len(FIELD_ORDER)))
    extra = [k for k in obj if k not in FIELD_SET]
    if extra:
        issues.append("存在非字典字段: %s" % ", ".join(str(k) for k in extra))

    for field in FIELD_ORDER:
        if field not in obj:
            continue
        val = obj[field]
        if isinstance(val, (list, tuple)):
            vals = [str(v) for v in val]
        elif isinstance(val, str):
            vals = [val]
        else:
            vals = [str(val)]
        for v in vals:
            issues.extend(check_value(field, v, meta, strict_unknow))
    return issues


# ============================================================
# 文件名 <-> 内容一致性
# ============================================================
def segment_str_from_content(obj, field):
    """按生成脚本口径, 由内容字段值构造命名段 (多值用 '-' 连接)。"""
    if field not in obj:
        return None
    val = obj[field]
    if isinstance(val, (list, tuple)):
        vals = [str(v) for v in val]
    else:
        vals = [str(val)]
    if not vals:
        return None
    if field == "mediaType":
        # 归一化 image<->jpg, video<->MP4 后比较
        norm = []
        for v in vals:
            vn = MEDIA_TYPE_ALIAS.get(v.lower(), v)
            norm.append("image" if vn == "image" else ("video" if vn == "video" else v))
        return "-".join(norm)
    return "-".join(vals)


def content_to_segments(obj, meta):
    """由内容字段构造完整命名的 13 段段值dict (mediaType 段按文件名惯例 jpg/MP4;
    lens 段按内容光谱段归一化, 红外时取 _ir 变体)。任一必填字段缺失时返回 None。
    用于包装格式/内容完整时生成改建建议。"""
    segs = {}
    for f in FIELD_ORDER:
        seg = segment_str_from_content(obj, f)
        if seg is None:
            return None
        if f == "mediaType":
            seg = MEDIA_TYPE_NAME_ALIAS.get(seg, seg)
        if f == "lens":
            spectral = obj.get("spectral")
            if isinstance(spectral, str) and spectral in ("红外", "可见光"):
                seg = _lens_effective(seg, spectral)
        segs[f] = seg
    return segs


def _lens_effective(value, spectral):
    """按光谱段求镜头有效值, 用于文件名<->内容一致性比对:
    spectral=红外 时 huanyu/huanyu_ir 等效, spectral=可见光 时同理。
    例如 红外+huanyu 与 huanyu_ir 表达同一含义, 归一化后应视为一致。"""
    if spectral == "红外":
        if value.endswith("_ir"):
            return value
        return value + "_ir" if value in ("hope", "huanyu") else value
    # 可见光
    if value.endswith("_ir"):
        return value[:-3]
    return value


def check_consistency(segs, obj, meta):
    """文件名各段与内容字段逐一比对 (去重后缀已剥离)。返回问题列表。
    lens 与 spectral 联动: 按内容光谱段归一化后再比较, 避免 huanyu_ir(文件名)
    vs huanyu(内容)+红外 这类本应等效的取值被误报为不一致。"""
    if segs is None:
        return []
    issues = []
    for field in FIELD_ORDER:
        content_seg = segment_str_from_content(obj, field)
        if content_seg is None:
            continue  # 内容缺失该字段 -> 已由 check_content 报告
        name_seg = segs[field]
        # mediaType 归一化后比较
        if field == "mediaType":
            name_norm = MEDIA_TYPE_ALIAS.get(name_seg.lower(), name_seg)
            name_norm = "image" if name_norm == "image" else ("video" if name_norm == "video" else name_norm)
            if name_norm != content_seg:
                issues.append("文件名与内容不一致: %s = \"%s\"(文件名) vs \"%s\"(内容)"
                              % (red_text(field), name_seg, content_seg))
            continue
        if COMPACT_RE.search(name_seg):
            continue  # 压缩命名无法逐值比对, 已由 check_segment 提示
        compare_name, compare_content = name_seg, content_seg
        if field == "lens":
            # 镜头值随光谱段联动, 归一化后比较 (内容缺失 spectral 时不做归一化);
            # 提示信息仍展示原始取值, 便于人工核对
            spectral = obj.get("spectral")
            if isinstance(spectral, str) and spectral in ("红外", "可见光"):
                compare_name = _lens_effective(name_seg, spectral)
                compare_content = _lens_effective(content_seg, spectral)
        if compare_name != compare_content:
            issues.append("文件名与内容不一致: %s = \"%s\"(文件名) vs \"%s\"(内容)"
                          % (red_text(field), name_seg, content_seg))
    return issues


# ============================================================
# 遍历与汇总
# ============================================================
def iter_json_files(root, report, skip_hidden=True):
    """深度优先遍历, 产出所有 .json 文件绝对路径; 目录访问失败仅记录不中断。"""
    def onerror(err):
        report.append("[警告] 无法访问目录: %s (%s)" % (err.filename, err.strerror or err))
    for dirpath, dirnames, filenames in os.walk(root, onerror=onerror):
        if skip_hidden:
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        dirnames.sort()
        for f in sorted(filenames):
            if f.lower().endswith(".json"):
                yield os.path.join(dirpath, f)


def iter_dirs(root, report, skip_hidden=True):
    """深度优先遍历, 产出所有子目录 (绝对路径, 上层目录名列表[近->远])。
    不含根本身; 目录访问失败仅记录不中断。"""
    root_abs = os.path.abspath(root)
    def onerror(err):
        report.append("[警告] 无法访问目录: %s (%s)" % (err.filename, err.strerror or err))
    for dirpath, dirnames, filenames in os.walk(root_abs, onerror=onerror):
        if skip_hidden:
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        dirnames.sort()
        for d in dirnames:
            full = os.path.join(dirpath, d)
            parents = []
            cur = dirpath
            while os.path.abspath(cur) != root_abs:
                parents.append(os.path.basename(cur))
                cur = os.path.dirname(cur)
            yield full, parents


def parent_names(path, root):
    """返回 path 所在目录的上层目录名列表(近->远), 不含根本身。"""
    parents = []
    cur = os.path.dirname(path)
    root_abs = os.path.abspath(root)
    while os.path.abspath(cur) != root_abs:
        parents.append(os.path.basename(cur))
        cur = os.path.dirname(cur)
    return parents


def apply_suggestion(path, plain_name):
    """将文件/目录重命名为"改建建议"的纯文本名 (重名自动追加 __N 去重后缀)。
    返回新绝对路径; 建议名与原命名相同或重命名失败时返回 None。"""
    target_dir = os.path.dirname(path)
    new_path = os.path.join(target_dir, plain_name)
    if os.path.abspath(new_path) == os.path.abspath(path):
        return None
    n = 2
    while os.path.exists(new_path):
        stem, ext = os.path.splitext(plain_name)
        new_path = os.path.join(target_dir, "%s__%d%s" % (stem, n, ext))
        n += 1
    try:
        os.rename(path, new_path)
    except OSError:
        return None
    return new_path


def validate_file(path, meta, strict_unknow, parents=()):
    """校验单个 JSON 文件。返回 (是否标记JSON, 问题列表, 是否通过, 纯文本建议名或None)。
    parents: 所在目录的上层目录名列表(近->远), 用于段数异常时生成改建建议。"""
    fname = os.path.basename(path)
    issues = []

    # 读取内容 (优先 UTF-8, 失败回退 GBK, 再失败判定为不可读)
    obj = None
    read_ok = False
    for enc in ("utf-8-sig", "gbk"):
        try:
            with open(path, "r", encoding=enc) as f:
                obj = json.load(f)
            read_ok = True
            if enc != "utf-8-sig":
                issues.append("编码非 UTF-8(按 %s 解析成功), 建议统一为 UTF-8" % enc)
            break
        except (UnicodeDecodeError, json.JSONDecodeError, OSError):
            continue
    if not read_ok:
        return None, ["JSON 无法解析(编码或格式错误)"], False, None

    # 识别是否标记 JSON
    if not (is_marker_filename(fname) or looks_like_marker_content(obj)):
        return False, issues, True, None  # 非标记 JSON, 跳过

    # 兼容 "图片标记样例"/"视频标记样例" 包装格式: 以其中 "内容" 对象作为实际内容校验,
    # 并提示应展开为顶层扁平对象 (改建建议按目录逻辑给出完整命名)
    content_obj = obj
    wrapper_note = None
    wrapped = False
    if isinstance(obj, dict):
        for wkey in ("图片标记样例", "视频标记样例"):
            w = obj.get(wkey)
            if isinstance(w, dict) and isinstance(w.get("内容"), dict):
                content_obj = w["内容"]
                wrapped = True
                wrapper_note = ("内容为 \"%s\" 包装格式, 请将其中 \"内容\" 字段"
                                "展开为顶层扁平对象" % wkey)
                break

    # 1. 文件名校验
    segs, name_issues = check_filename(fname, meta, strict_unknow)
    suggestion = None
    parent_dir = os.path.basename(os.path.dirname(path))
    ext = ".json" if fname.lower().endswith(".json") else ""
    # 包装格式: 先给问题说明, 再按内容生成完整命名建议 (与目录改建建议格式对齐)
    if wrapped:
        name_issues.append(wrapper_note)
        content_segs = content_to_segments(content_obj, meta)
        if content_segs:
            colored, plain, missing = suggest_from_reference(fname, content_segs, meta)
            name_issues.append("改建建议: %s%s" % (colored, ext))
            if missing:
                name_issues.append("    (缺失字段: %s; 依据内容字段)"
                                   % ", ".join(sorted(set(missing))))
            if plain + ext != fname:
                suggestion = plain + ext
    # 段数异常: 规范要求文件名与数据目录同名。上级目录名合规时以其为权威建议, 否则兜底建议
    if suggestion is None and any("段数异常" in it for it in name_issues):
        ref_segs = None
        if parents:
            ref_segs, _ = parse_filename(parents[0], meta)
        if ref_segs:
            colored, plain, missing = suggest_from_reference(fname, ref_segs, meta)
            name_issues.append("改建建议: %s%s" % (colored, ext))
            if missing:
                name_issues.append("    (缺失字段: %s; 依据上级目录名)"
                                   % ", ".join(sorted(set(missing))))
            suggestion = plain + ext
        else:
            sug = suggest_rename(fname, meta, parents or (parent_dir,))
            if sug:
                colored, plain, missing, inherited, inferred = sug
                name_issues.append("改建建议: %s" % colored)
                all_missing = sorted(set(missing) | set(inherited) | set(inferred))
                if all_missing:
                    notes = []
                    if inherited:
                        notes.append("%s 已从上层目录继承" % ", ".join(inherited))
                    if inferred:
                        notes.append("%s 已从目录内容/下级推断" % ", ".join(inferred))
                    note = "缺失字段: %s" % ", ".join(all_missing)
                    if notes:
                        note += " (%s)" % "; ".join(notes)
                    name_issues.append("    (%s)" % note)
                suggestion = plain
    issues.extend(name_issues)

    # 2. 内容校验 (包装格式按其中 "内容" 对象校验, 缺失字段红字标注)
    issues.extend(check_content(content_obj, meta, strict_unknow))

    # 3. 文件名与内容一致性
    issues.extend(check_consistency(segs, content_obj, meta))

    # 去重(同一问题可能由整段+拆分重复报告)并保持顺序
    seen, deduped = set(), []
    for it in issues:
        if it not in seen:
            seen.add(it)
            deduped.append(it)
    return True, deduped, not deduped, suggestion


def validate_dirname(path, meta, strict_unknow, parents=(), root_json_names=()):
    """校验目录名是否严格符合 13 段标记命名规范。返回 (问题列表, 纯文本建议名或None)。
    parents: 上层目录名列表(近->远)。建议依据优先: 目录内/根下关联的合规标记
    JSON 文件名 > 目录内容/下级推断 > 上层目录继承。"""
    name = os.path.basename(path)
    segs, issues = check_filename(name, meta, strict_unknow)
    # 目录名不叫"文件名", 文案对齐
    issues = [it.replace("文件名段数异常", "目录名段数异常") for it in issues]
    if issues and any("段数异常" in it for it in issues):
        # 1. 合规标记 JSON 文件名即权威建议 (规范: 文件名须与数据目录同名)
        ref = find_marker_json_name(path, meta)
        ref_from_root = False
        if ref is None and root_json_names:
            ref = match_json_to_dir(name, root_json_names, meta)
            ref_from_root = ref is not None
        if ref:
            ref_segs, _ = parse_filename(ref, meta)
            if ref_segs:
                colored, plain, missing = suggest_from_reference(name, ref_segs, meta)
                issues.append("改建建议: %s" % colored)
                if missing:
                    src = "依据根目录标记JSON文件名" if ref_from_root else "依据目录内标记JSON文件名"
                    issues.append("    (缺失字段: %s; %s)" % (", ".join(sorted(set(missing))), src))
                return issues, plain
        # 2. 目录内容/下级推断 + 上层目录继承
        extra = infer_dir_values(path, meta)
        sug = suggest_rename(name, meta, parents, extra)
        if sug:
            colored, plain, missing, inherited, inferred = sug
            issues.append("改建建议: %s" % colored)
            all_missing = sorted(set(missing) | set(inherited) | set(inferred))
            if all_missing:
                notes = []
                if inherited:
                    notes.append("%s 已从上层目录继承" % ", ".join(inherited))
                if inferred:
                    notes.append("%s 已从目录内容/下级推断" % ", ".join(inferred))
                note = "缺失字段: %s" % ", ".join(all_missing)
                if notes:
                    note += " (%s)" % "; ".join(notes)
                issues.append("    (%s)" % note)
            return issues, plain
    return issues, None


# ============================================================
# 报告输出
# ============================================================
def format_report(root, dict_path, opts, results):
    """汇总打印报告。results 为 (path, is_marker, issues, passed, note) 列表。"""
    lines = []
    lines.append("=" * 70)
    lines.append("标记 JSON 校验报告")
    lines.append("=" * 70)
    lines.append("输入路径 : %s" % root)
    lines.append("字典文件 : %s" % dict_path)
    if opts.get("extra"):
        lines.append("附加字典 : %s" % opts["extra"])
    lines.append("严格unknow: %s" % ("是" if opts["strict_unknow"] else "否 (unknow 通用允许)"))
    lines.append("-" * 70)

    n_marker = sum(1 for r in results if r[1] is True)
    n_skip = sum(1 for r in results if r[1] is False)
    n_unread = sum(1 for r in results if r[1] is None)
    n_bad = sum(1 for r in results if r[1] is True and not r[3])
    n_ok = n_marker - n_bad
    n_dir = sum(1 for r in results if r[4] == "目录")

    for idx, (path, is_marker, issues, passed, note) in enumerate(results, 1):
        kind = "(目录)" if note == "目录" else ""
        if is_marker is True:
            if passed:
                if opts["show_ok"]:
                    lines.append("[%d] 通过   %s %s" % (idx, path, kind))
            else:
                lines.append("[%d] 存在问题 %s" % (idx, kind))
                lines.append("    %s" % path)
                for it in issues:
                    lines.append("      - %s" % it)
        elif is_marker is False:
            if opts["show_skipped"]:
                lines.append("[%d] 跳过(非标记JSON) %s%s" % (idx, path, note or ""))
        else:
            lines.append("[%d] 无法读取" % idx)
            lines.append("    %s" % path)
            for it in issues:
                lines.append("      - %s" % it)

    lines.append("-" * 70)
    lines.append("标记对象总数 : %d (目录 %d / JSON文件 %d)" % (n_marker, n_dir, n_marker - n_dir))
    lines.append("  通过       : %d" % n_ok)
    lines.append("  存在问题   : %d" % n_bad)
    lines.append("非标记JSON(跳过): %d" % n_skip)
    lines.append("无法读取    : %d" % n_unread)
    if not n_marker and not n_skip and not n_unread:
        lines.append("(目录下未发现任何 .json 文件)")
    lines.append("=" * 70)
    return lines, n_bad


# ============================================================
# 入口
# ============================================================
def parse_args(argv):
    opts = {
        "dict": DEFAULT_DICT, "extra": None, "output": None,
        "strict_unknow": False, "show_ok": False, "show_skipped": False,
        "apply": False,
    }
    positional = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--dict" and i + 1 < len(argv):
            opts["dict"], i = argv[i + 1], i + 2
        elif a == "--extra-dict" and i + 1 < len(argv):
            opts["extra"], i = argv[i + 1], i + 2
        elif a == "--output" and i + 1 < len(argv):
            opts["output"], i = argv[i + 1], i + 2
        elif a == "--strict-unknow":
            opts["strict_unknow"], i = True, i + 1
        elif a == "--show-ok":
            opts["show_ok"], i = True, i + 1
        elif a == "--show-skipped":
            opts["show_skipped"], i = True, i + 1
        elif a == "--apply":
            opts["apply"], i = True, i + 1
        elif a in ("-h", "--help"):
            print(__doc__)
            sys.exit(0)
        else:
            positional.append(a)
            i += 1
    return opts, positional


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    # Windows 控制台编码兜底, 避免中文输出时抛异常
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    # 启用 Windows 控制台 ANSI 转义 (红色字段名高亮), 不影响 Linux/macOS
    if os.name == "nt":
        os.system("")

    opts, positional = parse_args(argv)
    if positional:
        root = positional[0]
        note = None
    else:
        try:
            root = input("请输入要校验的数据路径: ").strip()
        except EOFError:
            root = ""
        note = None

    root, path_note = resolve_path(root)
    if path_note:
        print("[提示] %s" % path_note)
    if not root or not os.path.isdir(root):
        print("[错误] 输入路径不存在或不是目录: %r" % (positional[0] if positional else root), file=sys.stderr)
        print("       请确认路径正确 (Windows 示例: D:\\data\\Labeled_data)", file=sys.stderr)
        return 2

    try:
        meta = load_dict(opts["dict"])
    except Exception as e:
        print("[错误] 加载字典失败 %s: %s" % (opts["dict"], e), file=sys.stderr)
        return 2
    if opts["extra"]:
        try:
            for field, vals in load_extra_dict(opts["extra"]).items():
                if field in meta:
                    meta[field]["allowed"] |= vals
        except Exception as e:
            print("[错误] 加载附加字典失败 %s: %s" % (opts["extra"], e), file=sys.stderr)
            return 2

    reports = []
    results = []
    renames = []  # (path, 纯文本建议名) 待 --apply 一键替换
    # 收集数据范围内命名合规(13 段)的标记 JSON 文件名, 作为目录改名建议依据
    root_json_names = []
    for jp in iter_json_files(root, reports):
        fn = os.path.basename(jp)
        segs, _ = parse_filename(fn, meta)
        if segs is not None:
            root_json_names.append(fn[:-5] if fn.lower().endswith(".json") else fn)
    # 1. 所有层级子目录名按 13 段规范校验 (传入上层目录名用于缺失字段继承)
    for path, parents in iter_dirs(root, reports):
        issues, suggestion = validate_dirname(path, meta, opts["strict_unknow"], parents, root_json_names)
        results.append((path, True, issues, not issues, "目录"))
        if suggestion:
            renames.append((path, suggestion))
    # 2. JSON 文件校验
    for path in iter_json_files(root, reports):
        parents = parent_names(path, root)
        is_marker, issues, passed, suggestion = validate_file(path, meta, opts["strict_unknow"], parents)
        results.append((path, is_marker, issues, passed, None))
        if suggestion:
            renames.append((path, suggestion))

    lines, n_bad = format_report(root, opts["dict"], opts, results)
    text = "\n".join(lines)
    print(text, flush=True)
    for w in reports:
        print(w, flush=True)
    if opts["output"]:
        try:
            with open(opts["output"], "w", encoding="utf-8", newline="") as f:
                f.write(ANSI_RE.sub("", text) + "\n")  # 写文件时剥离 ANSI 颜色
            print("[已写] 报告已保存到: %s" % opts["output"], flush=True)
        except OSError as e:
            print("[错误] 报告写入失败 %s: %s" % (opts["output"], e), file=sys.stderr)
            return 2

    # --apply: 一键按"改建建议"重命名 (先重命名深层路径, 避免父级改名后子路径失效)
    if opts["apply"] and renames:
        print("\n[一键替换] 按\"改建建议\"重命名 (重名自动追加 __N):", flush=True)
        applied = 0
        for path, plain in sorted(renames, key=lambda r: r[0].count(os.sep), reverse=True):
            new_path = apply_suggestion(path, plain)
            if new_path:
                applied += 1
                print("  %s" % path, flush=True)
                print("    -> %s" % new_path, flush=True)
        print("共重命名 %d 项。" % applied, flush=True)
    return 1 if n_bad else 0


if __name__ == "__main__":
    sys.exit(main())
