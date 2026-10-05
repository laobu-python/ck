"""parser.py —— APNG / “查看原图”式伪装图检查器（不依赖 tkinter，不依赖 GUI，可单独在命令行使用）

位置（迁移）：本模块原为 `utils/apng.py`，现为 `ck1_0/components/apng/parser.py`；
旧路径 `utils.apng` 保留为 **deprecated 别名**（一个版本周期），实现只有这一份。

本模块解决一个很常见的坑：一张 `.png` 文件，用 PS / 系统照片查看器 / 聊天列表缩略图
打开是一张图，拖进浏览器却变成另一张图。原因是它是 **APNG（动态 PNG）**，并且把
**IDAT 默认图** 当成“封面”、把真正的图放在 **动画帧（fcTL + fdAT）** 里：

    IHDR → acTL → tEXt(伪装标记) → IDAT(封面) → fcTL+fdAT(帧1) → fcTL+fdAT(帧2) → IEND

    - 不支持 APNG 的解码器（PS / 缩略图 / 照片查看器）只解析 IDAT → 看到“封面”
    - 支持 APNG 的解码器（浏览器 / APNG 查看器）会播放动画 → 看到“隐藏图”

本模块提供：
    analyze(path)        结构 + 逐帧 + 差异的综合报告（dict）
    format_report(info)  把报告格式化成人类可读的中文文本
    is_disguised(path)   快速判断是否属于“默认图与动画帧不一致”的伪装图
    save_frames(...)     拆帧导出（可选择是否包含默认图）
    inspect_text(text)   只做块级解析（不需要文件，用于分析十六进制/文本副本）

块级解析只用标准库；逐帧像素对比、拆帧需要 Pillow（可选依赖）。
"""
import hashlib
import json
import os
import struct

PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'

#: 已知的聊天软件 / 工具用于“把 APNG 伪装成静态图”的元数据关键字
APNG_DISGUISE_KEYS = (
    'ChatBarApngDisguise',
    'ApngDisguise',
    'Disguise',
)

#: 判定“两张图不同”的阈值（有差异像素占比，单位 %）
DIFF_PIXEL_THRESHOLD = 5.0


# --------------------------------------------------------------------------- #
# 块级解析（只依赖标准库）
# --------------------------------------------------------------------------- #
def _decode_text_chunk(ctype, body):
    """解析 tEXt / zTXt / iTXt，返回 (关键字, 文本) 或 None。"""
    try:
        if ctype == 'tEXt':
            keyword, _, text = body.partition(b'\x00')
            return keyword.decode('latin-1'), text.decode('latin-1')

        if ctype == 'zTXt':
            import zlib
            keyword, _, rest = body.partition(b'\x00')
            if not rest:
                return keyword.decode('latin-1'), ''
            return keyword.decode('latin-1'), zlib.decompress(rest[1:]).decode('latin-1')

        if ctype == 'iTXt':
            import zlib
            keyword, _, rest = body.partition(b'\x00')
            if len(rest) < 2:
                return keyword.decode('latin-1'), ''
            compressed = rest[0] == 1
            rest = rest[2:]                       # 跳过压缩标志 + 压缩方法
            _, _, rest = rest.partition(b'\x00')  # 语言标签
            translated, _, text = rest.partition(b'\x00')
            if compressed:
                text = zlib.decompress(text)
            return keyword.decode('latin-1'), text.decode('utf-8', 'replace')
    except Exception:
        return None
    return None


def parse_bytes(data):
    """解析 PNG/APNG 的块结构。

    参数:
        data (bytes): 文件完整字节

    返回:
        dict: 结构信息（不含逐帧像素对比）
    """
    info = {
        'signature_ok': data[:8] == PNG_SIGNATURE,
        'size_bytes': len(data),
        'complete': False,          # 是否读到 IEND（文件未截断）
        'chunks': [],               # [(类型, 长度, 偏移)]
        'width': None, 'height': None,
        'bit_depth': None, 'color_type': None,
        'interlace': None,
        'is_apng': False,
        'num_frames': None,         # acTL 声明的动画帧数
        'num_plays': None,          # 0 表示无限循环
        'frame_controls': [],       # fcTL 列表
        'fdat_count': 0,
        'idat_count': 0,
        'idat_bytes': 0,
        'texts': {},                # 元数据键值
        'disguise_markers': {},     # 命中伪装关键字的元数据
        'has_default_image': False, # IDAT 不属于动画 → “封面”
        'errors': [],
    }
    if not info['signature_ok']:
        info['errors'].append('文件头不是 PNG 签名（可能不是 PNG，或被文本编辑器破坏）')
        return info

    off = 8
    last_idat_index = None
    first_fctl_index = None
    index = 0

    while off + 12 <= len(data):
        (length,) = struct.unpack('>I', data[off:off + 4])
        ctype = data[off + 4:off + 8].decode('latin-1', 'replace')
        body = data[off + 8:off + 8 + length]
        if len(body) < length:
            info['errors'].append(f'块 {ctype} 数据不完整（文件被截断）')
            break

        info['chunks'].append((ctype, length, off))

        if ctype == 'IHDR' and length >= 13:
            (w, h, depth, color, _, _, interlace) = struct.unpack('>IIBBBBB', body[:13])
            info.update(width=w, height=h, bit_depth=depth,
                        color_type=color, interlace=interlace)
        elif ctype == 'acTL' and length >= 8:
            num_frames, num_plays = struct.unpack('>II', body[:8])
            info['is_apng'] = True
            info['num_frames'] = num_frames
            info['num_plays'] = num_plays
        elif ctype == 'fcTL' and length >= 26:
            (seq, w, h, xo, yo, dnum, dden, dispose, blend) = struct.unpack('>IIIIIHHBB', body[:26])
            info['frame_controls'].append({
                'sequence': seq, 'width': w, 'height': h,
                'x_offset': xo, 'y_offset': yo,
                'delay_num': dnum, 'delay_den': dden,
                'delay_seconds': (dnum / dden) if dden else (0.0 if dnum == 0 else None),
                'dispose_op': dispose, 'blend_op': blend,
            })
            if first_fctl_index is None:
                first_fctl_index = index
        elif ctype == 'fdAT':
            info['fdat_count'] += 1
        elif ctype == 'IDAT':
            info['idat_count'] += 1
            info['idat_bytes'] += length
            last_idat_index = index
        elif ctype in ('tEXt', 'zTXt', 'iTXt'):
            pair = _decode_text_chunk(ctype, body)
            if pair:
                info['texts'][pair[0]] = pair[1]
        elif ctype == 'IEND':
            info['complete'] = True
            break

        off += 12 + length
        index += 1

    # 第一个 fcTL 出现在 IDAT 之后 → IDAT 不属于动画，是“默认图/封面”
    if info['idat_count'] and first_fctl_index is not None and last_idat_index is not None:
        info['has_default_image'] = first_fctl_index > last_idat_index
    elif info['idat_count'] and first_fctl_index is None:
        # 有 acTL 却没有 fcTL：结构异常
        info['has_default_image'] = info['is_apng']

    for key, value in info['texts'].items():
        if any(k.lower() in key.lower() for k in APNG_DISGUISE_KEYS):
            info['disguise_markers'][key] = value

    return info


def inspect_text(text, encoding='utf-8'):
    """把“被文本编辑器另存过的图片内容”当字节流做块级解析（尽力而为）。

    提示：记事本另存会把 NUL 变成空格、丢掉 CR、把 >=0x80 的字节按 ANSI 重新编码，
    因此这种副本通常**无法还原**，只能粗略看出它是什么文件。
    """
    if isinstance(text, str):
        text = text.encode(encoding, 'replace')
    return parse_bytes(text)


def read_bytes(path):
    with open(path, 'rb') as f:
        return f.read()


def parse_png(path):
    """解析磁盘上的 PNG/APNG 文件结构。"""
    info = parse_bytes(read_bytes(path))
    info['path'] = os.path.abspath(path)
    info['file_name'] = os.path.basename(path)
    return info


# --------------------------------------------------------------------------- #
# 逐帧分析（需要 Pillow）
# --------------------------------------------------------------------------- #
def pil_available():
    try:
        from PIL import Image  # noqa: F401
        return True
    except Exception:
        return False


def _frame_stats(frame):
    """单帧轻量统计：md5、平均色、近白/近黑像素占比。"""
    rgba = frame.convert('RGBA')
    small = rgba.resize((96, 96)).convert('RGB')
    pixels = list(small.getdata())
    total = len(pixels)
    near_white = sum(1 for r, g, b in pixels if r > 235 and g > 235 and b > 235)
    near_black = sum(1 for r, g, b in pixels if r < 20 and g < 20 and b < 20)
    gray = [ (r * 299 + g * 587 + b * 114) // 1000 for r, g, b in pixels ]
    return {
        'md5': hashlib.md5(rgba.tobytes()).hexdigest()[:16],
        'mean_brightness': round(sum(gray) / total, 1),
        'near_white_pct': round(near_white * 100.0 / total, 1),
        'near_black_pct': round(near_black * 100.0 / total, 1),
    }


def frame_stats(path, max_frames=None):
    """逐帧统计（需要 Pillow）。返回 list[dict]，第 0 帧是默认图（若存在）。"""
    if not pil_available():
        return None
    from PIL import Image

    frames = []
    with Image.open(path) as im:
        n = getattr(im, 'n_frames', 1)
        default_image = bool(im.info.get('default_image')) or (
            n > 1 and im.info.get('default_image') is None and False)
        for i in range(n):
            if max_frames is not None and i >= max_frames:
                break
            im.seek(i)
            stats = _frame_stats(im)
            stats.update({
                'index': i,
                'duration_ms': im.info.get('duration'),
                'size': im.size,
                'is_default_image': i == 0 and default_image,
            })
            frames.append(stats)

        base_info = {
            'format': im.format, 'mode': im.mode, 'size': im.size,
            'is_animated': bool(getattr(im, 'is_animated', False)),
            'n_frames': n,
            'loop': im.info.get('loop'),
            'default_image': default_image,
            'pillow_info': {k: v for k, v in im.info.items() if k != 'icc_profile'},
        }
    return {'frames': frames, 'pil': base_info}


def frame_diffs(path, max_frames=None):
    """比较各帧差异（需要 Pillow）。

    返回 list[dict]: [{'from': i, 'to': j, 'pixel_diff_pct': x, 'mean_diff_pct': y}]
    只比较第 0 帧与其它帧、以及相邻帧，够用且省时。
    """
    if not pil_available():
        return None
    from PIL import Image, ImageChops, ImageStat

    pairs = []
    with Image.open(path) as im:
        n = getattr(im, 'n_frames', 1)
        if max_frames is not None:
            n = min(n, max_frames)
        images = []
        for i in range(n):
            im.seek(i)
            images.append(im.convert('RGB').copy())

    def _compare(i, j):
        diff = ImageChops.difference(images[i], images[j])
        stat = ImageStat.Stat(diff)
        mean_pct = sum(stat.mean) / (3 * 255) * 100.0
        # 像素级差异占比：任一通道差值 > 8 即视为有差异
        mask = diff.convert('L').point(lambda v: 255 if v > 8 else 0)
        changed = sum(mask.histogram()[255:])
        total = images[i].size[0] * images[i].size[1]
        return {
            'from': i, 'to': j,
            'pixel_diff_pct': round(changed * 100.0 / total, 2),
            'mean_diff_pct': round(mean_pct, 2),
            'identical': changed == 0,
        }

    for j in range(1, len(images)):
        pairs.append(_compare(0, j))
    for j in range(2, len(images)):
        pairs.append(_compare(j - 1, j))
    return pairs


# --------------------------------------------------------------------------- #
# 综合报告
# --------------------------------------------------------------------------- #
def analyze(path, deep=True, max_frames=None):
    """综合分析一张图片，返回报告 dict（结构 + 逐帧 + 差异 + 结论）。

    参数:
        path (str): 图片路径
        deep (bool): 是否做逐帧像素对比（需要 Pillow）
        max_frames (int): 逐帧分析的最大帧数（None 表示全部）

    返回:
        dict
    """
    info = parse_png(path)
    info['deep'] = False
    info['conclusion'] = []

    if deep and info['signature_ok']:
        stats = frame_stats(path, max_frames=max_frames)
        if stats:
            info['pil'] = stats['pil']
            info['frames'] = stats['frames']
            info['diffs'] = frame_diffs(path, max_frames=max_frames)
            info['deep'] = True
        else:
            info['errors'].append('未安装 Pillow，已跳过逐帧像素对比（pip install pillow）')

    info['conclusion'] = _make_conclusion(info)
    return info


def _make_conclusion(info):
    """根据分析结果生成中文结论文本列表。"""
    out = []
    if not info.get('signature_ok'):
        return ['这不是一个完整的 PNG 文件（可能不是图片，或被文本编辑器另存过）']

    if not info.get('is_apng'):
        out.append('普通静态 PNG：没有 acTL 块，不存在“点开原图变另一张图”的多帧结构。')
        if info.get('texts'):
            out.append('含元数据：' + '，'.join(f'{k}={v}' for k, v in info['texts'].items()))
        return out

    frames = info.get('pil', {}).get('n_frames', info.get('num_frames'))
    out.append(f'这是 APNG（动态 PNG）：动画帧 {info.get("num_frames")} 帧，'
               f'循环次数 {info.get("num_plays")}（0 = 无限循环）。')

    if info.get('has_default_image'):
        out.append('⚠ 第一个 fcTL 出现在 IDAT 之后：IDAT 是“默认图/封面”，不属于动画。')
        out.append('  → 不支持 APNG 的解码器（PS、聊天列表缩略图、系统照片查看器）只会显示这张默认图；')
        out.append('  → 支持 APNG 的解码器（Edge/Chrome 等浏览器、APNG 查看器）会播放动画，露出隐藏帧。')
    else:
        out.append('第一个 fcTL 在 IDAT 之前：默认图就是动画第 1 帧，不存在“封面与动画不一致”的伪装。')

    if info.get('disguise_markers'):
        for k, v in info['disguise_markers'].items():
            out.append(f'⚠ 命中聊天软件/工具伪装标记：{k} = {v}')

    # 空补丁帧：某些工具只写 1x1 之类的极小帧，用来“拖时间”，效果就是静止画面
    fcs = info.get('frame_controls') or []
    full_area = (info.get('width') or 0) * (info.get('height') or 0)
    if full_area:
        small = [(i + 1, fc['width'], fc['height']) for i, fc in enumerate(fcs)
                 if fc['width'] * fc['height'] < full_area]
        if small:
            detail = '、'.join(f'第 {i} 个动画帧只覆盖 {w}x{h} 像素' for i, w, h in small)
            out.append(f'⚠ {detail} → 属于“空补丁帧”，作用是延长上一帧的显示时间'
                       f'（所以动画看起来是静止的，拆帧工具也常常把它当成一张独立图片）。')

    if info.get('deep'):
        frames_list = info.get('frames') or []
        if frames_list:
            default_frame = frames_list[0]
            out.append(f'Pillow 视角共 {info["pil"]["n_frames"]} 帧'
                       f'（0 = 默认图，1… 为动画帧），尺寸 {frames_list[0]["size"][0]}x{frames_list[0]["size"][1]}。')
        diffs = [d for d in (info.get('diffs') or []) if d['from'] == 0 and d['to'] >= 1]
        if diffs:
            worst = max(diffs, key=lambda d: d['pixel_diff_pct'])
            if worst['pixel_diff_pct'] >= DIFF_PIXEL_THRESHOLD:
                out.append(f'⚠ 默认图与动画帧不是同一张图：帧0 vs 帧{worst["to"]} 有 '
                           f'{worst["pixel_diff_pct"]}% 的像素不同 → 典型的“查看原图”式变脸伪装。')
            else:
                out.append(f'默认图与动画帧几乎一致（最大差异 {worst["pixel_diff_pct"]}%），'
                           f'“变脸”效果不明显。')
        identical_pairs = [d for d in (info.get('diffs') or [])
                           if d['to'] == d['from'] + 1 and d['identical']]
        if identical_pairs and len(frames_list) > 2:
            seqs = ', '.join(f'帧{d["from"]}=帧{d["to"]}' for d in identical_pairs)
            out.append(f'注意：{seqs} 像素完全相同，所谓“动画”其实是静止画面（常见于拆帧工具生成的空增量帧）。')

    if _is_disguised_from_info(info):
        out.append('结论：这属于“APNG 多帧伪装”。想看到全部内容，必须按帧读取，'
                   '不能只用 PS / 缩略图 / 照片查看器。')
    elif info.get('is_apng'):
        out.append('结论：这是普通动图（默认图即动画第 1 帧），'
                   '各查看器看到的内容一致，没有“封面/隐藏帧”之分。')
    return out


def _is_disguised_from_info(info):
    """根据 analyze() 的结果判断是否为伪装（供 is_disguised 与结论生成共用）。

    判定要点：
      1. 命中聊天软件/工具伪装标记 → 是伪装；
      2. 否则必须是“IDAT 默认图不属于动画”的结构，**并且**默认图与动画帧确实不是同一张图；
      3. 普通动图（默认图就是动画第 1 帧）一律不算伪装，哪怕各帧颜色差别很大。
    """
    if not info.get('is_apng'):
        return False
    if info.get('disguise_markers'):
        return True
    if not info.get('has_default_image'):
        return False
    diffs = [d for d in (info.get('diffs') or []) if d['from'] == 0 and d['to'] >= 1]
    if diffs:
        return max(d['pixel_diff_pct'] for d in diffs) >= DIFF_PIXEL_THRESHOLD
    return False        # 没有逐帧对比能力时不轻易下结论


def is_disguised(path, deep=True):
    """快速判断：文件是否为“默认图与动画帧不一致”的伪装 APNG。

    参数:
        path (str): 图片路径
        deep (bool): 是否做逐帧像素对比（False 时只能靠伪装标记判断）

    返回:
        bool
    """
    return _is_disguised_from_info(analyze(path, deep=deep, max_frames=4))


# --------------------------------------------------------------------------- #
# 拆帧导出
# --------------------------------------------------------------------------- #
def save_frames(path, outdir, prefix='frame', include_default=True,
                indices=None, max_frames=None):
    """把各帧导出为独立 PNG 文件（需要 Pillow）。

    参数:
        path (str): 源图片
        outdir (str): 输出目录（不存在会自动创建）
        prefix (str): 输出文件名前缀，如 `frame` → `frame_0.png`
        include_default (bool): 是否包含 APNG 的默认图（帧 0）
        indices (list[int]): 只导出这些帧号（None 表示全部）
        max_frames (int): 最多导出多少帧

    返回:
        list[str]: 实际写出的文件路径列表
    """
    if not pil_available():
        raise RuntimeError('拆帧导出需要 Pillow，请先执行 pip install pillow')
    from PIL import Image

    os.makedirs(outdir, exist_ok=True)
    written = []
    with Image.open(path) as im:
        n = getattr(im, 'n_frames', 1)
        if max_frames is not None:
            n = min(n, max_frames)
        for i in range(n):
            if indices is not None and i not in indices:
                continue
            if i == 0 and not include_default and n > 1 and im.info.get('default_image'):
                continue
            im.seek(i)
            out = os.path.join(outdir, f'{prefix}_{i}.png')
            im.convert('RGBA').save(out)
            written.append(out)
    return written


def to_json(info):
    """把 analyze() 的结果序列化成 JSON 文本（去掉不可序列化字段）。"""
    def _clean(obj):
        if isinstance(obj, dict):
            return {k: _clean(v) for k, v in obj.items() if k != 'chunks'}
        if isinstance(obj, (list, tuple)):
            return [_clean(v) for v in obj]
        if isinstance(obj, (str, int, float, bool)) or obj is None:
            return obj
        return str(obj)

    return json.dumps(_clean(info), ensure_ascii=False, indent=2)


# --------------------------------------------------------------------------- #
# 文本报告
# --------------------------------------------------------------------------- #
def format_report(info, verbose=True):
    """把 analyze() 的结果格式化成中文文本报告。"""
    lines = []
    add = lines.append
    add('=' * 62)
    add(' APNG / 伪装图检查报告  (ck1.0 components.apng)')
    add('=' * 62)
    add(f'文件    : {info.get("file_name") or info.get("path") or "(bytes)"}')
    if info.get('path'):
        add(f'路径    : {info["path"]}')
    add(f'大小    : {info.get("size_bytes"):,} 字节')

    if not info.get('signature_ok'):
        add('签名    : 不是 PNG 签名 → 分析终止')
        for e in info.get('errors', []):
            add(f'  ! {e}')
        return '\n'.join(lines)

    add(f'图像尺寸: {info.get("width")}x{info.get("height")}，'
        f'位深 {info.get("bit_depth")}，颜色类型 {info.get("color_type")}，'
        f'隔行 {info.get("interlace")}')
    add(f'文件完整: {"是" if info.get("complete") else "否（未读到 IEND，可能被截断）"}')

    if info.get('is_apng'):
        add(f'APNG    : 是（acTL：动画帧 {info.get("num_frames")} 帧，'
            f'循环 {info.get("num_plays")} 次 / 0 表示无限）')
    else:
        add('APNG    : 否（纯静态 PNG）')

    add(f'数据块  : IDAT {info.get("idat_count")} 个（{info.get("idat_bytes"):,} 字节）、'
        f'fcTL {len(info.get("frame_controls") or [])} 个、fdAT {info.get("fdat_count")} 个')
    add(f'默认图  : {"有（IDAT 不属于动画 → 非 APNG 查看器只会看到它）" if info.get("has_default_image") else "无 / 默认图即动画第 1 帧"}')

    if info.get('texts'):
        add('元数据  :')
        for k, v in info['texts'].items():
            mark = '  <== 伪装标记' if k in (info.get('disguise_markers') or {}) else ''
            add(f'    {k} = {v}{mark}')

    fcs = info.get('frame_controls') or []
    if fcs and verbose:
        add('帧控制  :')
        for i, fc in enumerate(fcs):
            delay = fc.get('delay_seconds')
            delay_txt = '（暂停/静止帧）' if not delay else f'{delay:.3f}s'
            add(f'    动画帧 {i + 1}: {fc["width"]}x{fc["height"]} '
                f'偏移({fc["x_offset"]},{fc["y_offset"]}) 延时 {delay_txt} '
                f'dispose={fc["dispose_op"]} blend={fc["blend_op"]}')

    frames = info.get('frames')
    if frames:
        add('-' * 62)
        add(f'逐帧明细（Pillow 视角共 {info["pil"]["n_frames"]} 帧'
            f'{"，含默认图" if info["pil"].get("default_image") else ""}）:')
        for f in frames:
            tag = '默认图/封面' if f.get('is_default_image') else f'动画帧 {f["index"]}'
            dur = f.get('duration_ms')
            dur_txt = f'{dur}ms' if dur else '（无）'
            add(f'  帧{f["index"]:<3} {tag:<10} {f["size"][0]}x{f["size"][1]}  '
                f'延时 {dur_txt:<8} md5 {f["md5"]}  '
                f'亮度 {f["mean_brightness"]:.0f} 近白 {f["near_white_pct"]}% 近黑 {f["near_black_pct"]}%')

    diffs = info.get('diffs')
    if diffs:
        add('-' * 62)
        add('帧间差异:')
        for d in diffs:
            if d['from'] > 0 and d['to'] == d['from'] + 1:
                label = f'相邻 帧{d["from"]} → 帧{d["to"]}'
            else:
                label = f'对比 帧{d["from"]} → 帧{d["to"]}'
            if d['identical']:
                add(f'  {label}: 完全相同')
            else:
                add(f'  {label}: {d["pixel_diff_pct"]}% 像素不同'
                    f'（平均色差 {d["mean_diff_pct"]}%）')

    if info.get('errors'):
        add('-' * 62)
        for e in info.get('errors', []):
            add(f'! {e}')

    add('-' * 62)
    add('结论:')
    for line in info.get('conclusion') or []:
        add(f'  {line}')
    add('=' * 62)
    return '\n'.join(lines)
