# _smoke_apng.py —— ck1.0 新功能验证：APNG / 伪装图检查器 + media 升级
"""自造三种夹具（静态PNG / 普通APNG / “查看原图”式伪装APNG），逐项验证。

伪装夹具与真实样本同构：IDAT 是封面，动画帧是另一张图，且**两个动画帧完全相同**
（Pillow 写入时会把重复帧合并，所以这里用字节级手术把 fcTL/fdAT 复制一份，模拟真实文件）。

在 ck1.0 文件夹里运行：
    python _smoke_apng.py
若桌面上存在真实样本 2345.png，也会一并验证。
"""
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import traceback
import zlib

PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'
REAL_SAMPLE = os.path.expanduser('~/Desktop/2345.png')

errors = []


def check(name, fn):
    """执行一项检查：抛异常即失败，返回字符串会作为说明打印。"""
    try:
        result = fn()
        if result is False:
            raise AssertionError('检查返回 False')
        print(f"[OK]   {name}" + (f"  -> {result}" if result not in (None, True) else ""))
        return result
    except Exception:
        print(f"[FAIL] {name}")
        traceback.print_exc()
        errors.append(name)
        return None


# --------------------------------------------------------------------------- #
# APNG 字节级工具（仅测试用）
# --------------------------------------------------------------------------- #
def _read_chunks(data):
    """返回 [(类型, 载荷)]。"""
    out = []
    off = 8
    while off + 12 <= len(data):
        (length,) = struct.unpack('>I', data[off:off + 4])
        ctype = data[off + 4:off + 8].decode('latin-1')
        out.append((ctype, data[off + 8:off + 8 + length]))
        off += 12 + length
        if ctype == 'IEND':
            break
    return out


def _pack_chunk(ctype, payload):
    return (struct.pack('>I', len(payload)) + ctype.encode('latin-1') + payload
            + struct.pack('>I', zlib.crc32(ctype.encode('latin-1') + payload) & 0xFFFFFFFF))


def make_disguised_apng(path, workdir):
    """构造与真实样本同构的伪装 APNG：封面(IDAT) + 两个完全相同的动画帧(fcTL/fdAT)。"""
    from PIL import Image, ImageDraw, PngImagePlugin

    cover = Image.new('RGB', (200, 260), (25, 25, 35))
    ImageDraw.Draw(cover).text((16, 120), 'ORIGINAL', fill='white')
    hidden = Image.new('RGB', (200, 260), (240, 240, 240))
    ImageDraw.Draw(hidden).text((16, 120), 'HIDDEN PICTURE', fill=(30, 30, 30))

    pnginfo = PngImagePlugin.PngInfo()
    pnginfo.add_text('ChatBarApngDisguise', '1;STATIC;1')

    base = os.path.join(workdir, '_base_disguised.png')
    cover.save(base, save_all=True, append_images=[hidden], default_image=True,
               duration=100, loop=0, pnginfo=pnginfo)

    with open(base, 'rb') as f:
        chunks = _read_chunks(f.read())

    fctl_payload = next(p for c, p in chunks if c == 'fcTL')
    fdat_payload = next(p for c, p in chunks if c == 'fdAT')

    out = [PNG_SIGNATURE]
    for ctype, payload in chunks:
        if ctype == 'acTL':
            out.append(_pack_chunk('acTL', struct.pack('>II', 2, 0)))      # 改成 2 个动画帧
        elif ctype == 'IEND':
            # 追加第二个动画帧：内容与第一个动画帧完全一致（模拟“假动画”）
            out.append(_pack_chunk('fcTL', struct.pack('>I', 2) + fctl_payload[4:]))
            out.append(_pack_chunk('fdAT', struct.pack('>I', 3) + fdat_payload[4:]))
            out.append(_pack_chunk('IEND', b''))
        else:
            out.append(_pack_chunk(ctype, payload))

    with open(path, 'wb') as f:
        f.write(b''.join(out))
    return path


def make_fixtures(tmpdir):
    """生成夹具，返回路径 dict。需要 Pillow。"""
    from PIL import Image, ImageDraw

    paths = {}

    # 1) 普通静态 PNG
    static = Image.new('RGB', (120, 90), (200, 60, 60))
    ImageDraw.Draw(static).text((10, 10), 'STATIC', fill='white')
    paths['static'] = os.path.join(tmpdir, 'static.png')
    static.save(paths['static'])

    # 2) 普通 APNG（第一帧就是动画第一帧，没有“封面/隐藏帧”之分）
    frames = [Image.new('RGB', (120, 90), c) for c in ((255, 0, 0), (0, 200, 0), (0, 0, 255))]
    for i, f in enumerate(frames):
        ImageDraw.Draw(f).text((10, 10), f'FRAME {i}', fill='white')
    paths['plain_apng'] = os.path.join(tmpdir, 'plain_apng.png')
    frames[0].save(paths['plain_apng'], save_all=True,
                   append_images=frames[1:], duration=120, loop=0)

    # 3) 伪装 APNG
    paths['disguised'] = make_disguised_apng(os.path.join(tmpdir, 'disguised_apng.png'), tmpdir)
    return paths


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #
def main():
    print('=' * 66)
    print(' ck1.0 冒烟测试：APNG / 伪装图检查器 + media 升级')
    print('=' * 66)

    try:
        from ck1_0.components.apng import parser as apng_utils   #：原 utils.apng
        from gui.main_window import MainWindow
    except Exception:
        print('[FAIL] 导入 ck1_0.components.apng.parser / gui.main_window 失败')
        traceback.print_exc()
        return 1
    print('[OK]   导入 ck1_0.components.apng.parser 与 gui.main_window')

    have_pil = apng_utils.pil_available()
    print(f'       Pillow 可用: {have_pil}')
    if not have_pil:
        print('       未安装 Pillow，只做块级解析相关检查')

    tmpdir = tempfile.mkdtemp(prefix='ck1_0_apng_')
    paths = check('生成夹具（静态PNG / 普通APNG / 伪装APNG）', lambda: make_fixtures(tmpdir))
    if not paths:
        print('夹具生成失败，终止')
        return 1

    # ---------------- 块级解析 ----------------
    static_info = apng_utils.parse_png(paths['static'])
    check('静态 PNG: is_apng 为 False', lambda: static_info['is_apng'] is False)
    check('静态 PNG: 无 acTL、尺寸正确',
          lambda: assert_true(static_info['num_frames'] is None and static_info['width'] == 120))

    plain = apng_utils.analyze(paths['plain_apng'])
    check('普通 APNG: is_apng 为 True', lambda: assert_true(plain['is_apng'] is True))
    check('普通 APNG: acTL 声明 3 帧', lambda: assert_true(plain['num_frames'] == 3))
    check('普通 APNG: 没有“默认图/封面”（第一个 fcTL 在 IDAT 之前）',
          lambda: assert_true(plain['has_default_image'] is False))
    check('普通 APNG: 不判为伪装', lambda: assert_true(apng_utils.is_disguised(paths['plain_apng']) is False))

    dis = apng_utils.analyze(paths['disguised'])
    check('伪装 APNG: is_apng 为 True', lambda: assert_true(dis['is_apng'] is True))
    check('伪装 APNG: acTL 声明 2 个动画帧', lambda: assert_true(dis['num_frames'] == 2))
    check('伪装 APNG: has_default_image 为 True（IDAT 是封面，不属于动画）',
          lambda: assert_true(dis['has_default_image'] is True))
    check('伪装 APNG: 命中伪装标记 ChatBarApngDisguise',
          lambda: assert_true('ChatBarApngDisguise' in dis['disguise_markers']))
    check('伪装 APNG: is_disguised=True',
          lambda: assert_true(apng_utils.is_disguised(paths['disguised']) is True))
    check('伪装 APNG: Pillow 看到 3 帧（封面 + 2 动画帧）',
          lambda: assert_true(dis.get('pil', {}).get('n_frames') == 3, dis.get('pil', {}).get('n_frames')))
    check('伪装 APNG: 帧0 被标记为默认图',
          lambda: assert_true((dis.get('frames') or [{}])[0].get('is_default_image') is True))

    # ---------------- 帧间差异 ----------------
    def cover_vs_hidden():
        pairs = [d for d in (dis.get('diffs') or []) if d['from'] == 0 and d['to'] == 1]
        assert pairs, '缺少帧0 vs 帧1 的对比结果'
        pct = pairs[0]['pixel_diff_pct']
        assert pct >= 5.0, f'封面与隐藏帧差异应明显，实际 {pct}%'
        return f"帧0 vs 帧1 有 {pct}% 像素不同"
    check('伪装 APNG: 封面帧与隐藏帧差异明显', cover_vs_hidden)

    def hidden_frames_identical():
        pairs = [d for d in (dis.get('diffs') or []) if d['from'] == 1 and d['to'] == 2]
        assert pairs, '缺少帧1 vs 帧2 的对比结果'
        assert pairs[0]['identical'], f"帧1 与帧2 应完全相同，实际差异 {pairs[0]['pixel_diff_pct']}%"
        return '帧1 == 帧2（空增量/重复帧）'
    check('伪装 APNG: 识别出“假动画”（帧1==帧2）', hidden_frames_identical)

    def report_mentions_fake_animation():
        text = apng_utils.format_report(dis)
        assert '完全相同' in text, '报告应提示存在完全相同的帧'
        return '报告已提示“完全相同的帧”'
    check('报告会指出重复帧', report_mentions_fake_animation)

    # ---------------- 报告文本 / JSON ----------------
    report = apng_utils.format_report(dis)
    check('报告含“默认图”说明', lambda: assert_true('默认图' in report))
    check('报告含伪装标记', lambda: assert_true('ChatBarApngDisguise' in report))
    check('报告含结论段', lambda: assert_true('结论' in report and 'APNG' in report))

    def json_ok():
        data = json.loads(apng_utils.to_json(dis))
        assert data['is_apng'] is True
        assert data['num_frames'] == 2, data['num_frames']
        assert len(data['frames']) == 3
        return 'JSON 可解析且帧数正确'
    check('to_json 可被 json.loads 解析', json_ok)

    # ---------------- 文本副本也能粗略解析 ----------------
    def text_copy():
        with open(paths['disguised'], 'rb') as f:
            text = f.read().decode('latin-1')
        info = apng_utils.inspect_text(text, encoding='latin-1')
        assert info['signature_ok'] and info['is_apng'], '文本副本应仍能识别出 APNG 结构'
        assert info['disguise_markers'], '文本副本应仍能识别出伪装标记'
        return '文本副本可判定为伪装 APNG'
    check('inspect_text：被另存的文本副本仍可粗略解析', text_copy)

    # ---------------- 拆帧导出 ----------------
    out_all = os.path.join(tmpdir, 'frames_all')
    written_all = apng_utils.save_frames(paths['disguised'], out_all)
    check('save_frames 导出 3 帧（含封面）',
          lambda: assert_true(len(written_all) == 3, len(written_all)))
    check('导出文件确实存在', lambda: assert_true(all(os.path.isfile(p) for p in written_all)))

    written_nd = apng_utils.save_frames(paths['disguised'],
                                        os.path.join(tmpdir, 'frames_nodefault'),
                                        include_default=False)
    check('save_frames(include_default=False) 只导出动画帧',
          lambda: assert_true(len(written_nd) == 2, len(written_nd)))

    # ---------------- GUI 侧：MainWindow + media 新接口 ----------------
    import tkinter as tk
    from ck1_0.renderer.base import Handle      #：`photo` 的返回形状已中立化

    app = MainWindow('ck1.0 apng smoke', 900, 700)
    app.show_message = lambda *a, **k: None          # 屏蔽弹窗

    # `photo` 现在返回**中立句柄**（`.native` = 承载图片/说明的容器 Frame）⇒
    # 形状断言按已生效的迁移走（=(i) 同口径：基线探针跟着迁移改形状断言），
    # 行为断言（哪一帧、能不能加载）一条未动。
    check('media.photo(frame=1) 显示隐藏帧并返回中立句柄',
          lambda: assert_true(isinstance(app.photo(paths['disguised'], '隐藏帧', frame=1), Handle)))
    check('media.photo(frame=0) 显示默认图',
          lambda: assert_true(isinstance(app.photo(paths['disguised'], frame=0), Handle)))

    def anim():
        n = app.animation(paths['disguised'], max_loops=1, text='动画')
        assert n == 3, f'应加载 3 帧，实际 {n}'
        app.root.update()
        return f'加载 {n} 帧'
    check('media.animation() 支持 APNG（3 帧）', anim)

    check('media.gif() 仍向后兼容（透传到 animation）',
          lambda: assert_true(app.gif(paths['plain_apng']) == 3))
    check('animation 播放标志已启动', lambda: assert_true(app._anim_playing is True))

    def clear_stops_animation():
        app.clear_media()
        app.root.update()
        assert app._anim_playing is False, '_anim_playing 应为 False'
        assert app._anim_after_id is None, 'after 回调 id 应被清空'
        return 'after 循环已取消（旧版泄漏已修）'
    check('clear_media() 会取消动画 after 循环', clear_stops_animation)

    check('media.apng_info() 返回 dict', lambda: assert_true(isinstance(app.apng_info(paths['disguised']), dict)))
    check('media.apng_report() 返回文本',
          lambda: assert_true('默认图' in app.apng_report(paths['disguised'])))
    check('media.is_disguised_image() 判定为伪装',
          lambda: assert_true(app.is_disguised_image(paths['disguised']) is True))
    # `show_frames` 现在返回**中立句柄**（`.native` 是承载缩略图网格的容器 Frame），
    # 且**像素引用改由 renderer 持有**（首版靠 facade 的 `_frame_thumbs` 防 GC）⇒
    # 形状断言与「引用被保留」的读数按已生效的迁移改（=(i) 同口径）。
    check('media.show_frames() 返回中立句柄',
          lambda: assert_true(isinstance(app.show_frames(paths['disguised'], thumb_width=120, columns=2), Handle)))
    check('media.show_frames() 的预览句柄被 facade 记下（像素引用在 renderer 侧）',
          lambda: assert_true(len(app._frame_previews) == 1, len(app._frame_previews)))

    out_gui = os.path.join(tmpdir, 'frames_gui')
    check('media.export_frames() 拆帧导出',
          lambda: assert_true(len(app.export_frames(paths['disguised'], outdir=out_gui)) == 3))

    app.root.update()
    # 同一进程里**再建**窗口前必须先**释放** Renderer（只 `root.destroy()` 会留下
    # 失效的单例登记 ⇒ 下面的 `apng_tool.run_gui()` 建窗口时会抛底层 `TclError`）。
    app.close()
    print('[OK]   MainWindow 相关检查完成')

    # ---------------- apng_tool.py（CLI + GUI 构建） ----------------
    try:
        import apng_tool
    except Exception:
        print('[FAIL] 导入 apng_tool 失败')
        traceback.print_exc()
        errors.append('导入 apng_tool')
        apng_tool = None

    if apng_tool is not None:
        def tool_cli():
            code = apng_tool.cli(paths['disguised'])
            assert code == 0, f'cli 应返回 0，实际 {code}'
            return 'CLI 报告模式正常'
        check('apng_tool.cli() 打印报告并返回 0', tool_cli)

        def tool_cli_frames():
            code = apng_tool.cli(paths['disguised'], do_frames=True)
            assert code == 0, f'--frames 应返回 0，实际 {code}'
            outdir = os.path.splitext(paths['disguised'])[0] + '_frames'
            assert os.path.isdir(outdir), f'应生成 {outdir}'
            return f'拆帧输出目录已生成（{len(os.listdir(outdir))} 个文件）'
        check('apng_tool.cli(--frames) 拆帧导出', tool_cli_frames)

        def tool_cli_gbk_console():
            """**回归守卫（GBK 控制台）**：中文 Windows 的控制台/管道默认 GBK，
            报告里的 `⚠` 曾让 `print()` 抛 `UnicodeEncodeError`（新手只看到一句看不懂的英文）。

            守卫口径：**把 `PYTHON*` 环境变量全部剥掉**（强制走 GBK 默认）+ stdout 接管道，
            跑真的子进程 ⇒ 必须 rc=0 且 stderr 里**没有** UnicodeEncodeError/Traceback。
            """
            env = {k: v for k, v in os.environ.items() if not k.startswith('PYTHON')}
            proc = subprocess.run([sys.executable, 'apng_tool.py', paths['disguised']],
                                  capture_output=True, text=True, encoding='utf-8',
                                  errors='replace', env=env, timeout=300)
            err = proc.stderr or ''
            assert proc.returncode == 0, f'GBK 环境下 CLI 应 rc=0，实际 {proc.returncode}'
            assert 'UnicodeEncodeError' not in err, 'GBK 环境下仍抛 UnicodeEncodeError'
            assert 'Traceback' not in err, f'GBK 环境下有崩溃：{err[-200:]}'
            return 'GBK 控制台/管道下 CLI 不再崩（守卫）'
        check('apng_tool.cli() 在 GBK 控制台/管道下不崩', tool_cli_gbk_console)

        def tool_gui():
            tool_app = apng_tool.run_gui(paths['disguised'], autorun=False)
            assert tool_app is not None, 'autorun=False 应返回 MainWindow 实例'
            tool_app.root.update()
            # 同上：释放（而非只销毁 root），保证本进程后续不会再被失效槽位挡住。
            tool_app.close()
            return 'GUI 界面构建成功（未进入主循环）'
        check('apng_tool.run_gui(autorun=False) 能建好界面', tool_gui)

        def tool_missing_file():
            assert apng_tool.cli(os.path.join(tmpdir, '不存在.png')) == 2
            return '缺失文件返回退出码 2'
        check('apng_tool.cli() 对不存在的文件返回 2', tool_missing_file)

    # ---------------- 包模式导入（模拟 pip install -e . 之后的 ck1_0） ----------------
    def package_mode_import():
        """包模式导入：把**真正的库包** `ck1_0/` 与 facade `gui/` 复制到临时根。

        （：原检查假设"仓库根就是 `ck1_0` 包"—— 那是更早版本的布局；
        把 APNG 迁进 `ck1_0/components/` 之后该前提不复存在，故检查改为**当前真实布局**：
        库包与 facade 分开、facade 靠双模导入找到库包。）
        """
        import importlib

        src = os.path.dirname(os.path.abspath(__file__))
        pkg_parent = os.path.join(tmpdir, 'pkgroot')
        _ignore = shutil.ignore_patterns('__pycache__', '*.pyc')
        shutil.copytree(os.path.join(src, 'ck1_0'), os.path.join(pkg_parent, 'ck1_0'),
                        ignore=_ignore)
        shutil.copytree(os.path.join(src, 'gui'), os.path.join(pkg_parent, 'gui'),
                        ignore=_ignore)

        if pkg_parent not in sys.path:
            sys.path.insert(0, pkg_parent)
        module = importlib.import_module('ck1_0')
        assert module.__version__ == '1.0', module.__version__
        apng = importlib.import_module('ck1_0.components.apng')
        assert apng.parser.PNG_SIGNATURE.startswith(b'\x89PNG')
        mw = importlib.import_module('gui.main_window')
        assert hasattr(mw, 'MainWindow')
        media = importlib.import_module('gui.media')
        assert media.apng_utils is not None, 'gui.media 的双模导入（→ ck1_0.components.apng）失败'

    check('包模式：库包 `ck1_0` + facade `gui` 都可导入、相对/双模导入正常', package_mode_import)

    # ---------------- 真实样本（可选） ----------------
    if os.path.isfile(REAL_SAMPLE):
        print('-' * 66)
        print(f'真实样本验证: {REAL_SAMPLE}')
        info = apng_utils.analyze(REAL_SAMPLE)
        print(f"  is_apng={info['is_apng']}  acTL帧数={info['num_frames']}  "
              f"Pillow帧数={info.get('pil', {}).get('n_frames')}  "
              f"默认图={info['has_default_image']}")
        print(f"  伪装标记={info['disguise_markers']}  is_disguised={apng_utils.is_disguised(REAL_SAMPLE)}")
        if info.get('frames'):
            print('  帧明细: ' + ' | '.join(
                f"帧{f['index']}({'封面' if f.get('is_default_image') else '动画'}) "
                f"亮度{f['mean_brightness']:.0f} 近白{f['near_white_pct']}%"
                for f in info['frames']))

        def real_sample_ok():
            assert info['is_apng'] is True
            assert info['has_default_image'] is True
            assert info['pil']['n_frames'] == 3
            assert apng_utils.is_disguised(REAL_SAMPLE) is True
            pairs = [d for d in info['diffs'] if d['from'] == 1 and d['to'] == 2]
            assert pairs and pairs[0]['identical'], '真实样本的帧1/帧2 应完全相同'
            return '真样本：封面+2隐藏帧（帧1==帧2）全部识别正确'
        check('真实样本 2345.png 被正确识别', real_sample_ok)
    else:
        print('-' * 66)
        print(f'（未找到真实样本 {REAL_SAMPLE}，跳过）')

    shutil.rmtree(tmpdir, ignore_errors=True)

    print('-' * 66)
    if errors:
        print(f'结果: {len(errors)} 项失败 -> {errors}')
        return 1
    print('结果: 全部通过')
    return 0


def assert_true(cond, extra=None):
    """断言为真，返回便于阅读的说明。"""
    assert cond, f'期望为真，实际 {cond!r}' + (f'（{extra}）' if extra is not None else '')
    return True


if __name__ == '__main__':
    sys.exit(main())
