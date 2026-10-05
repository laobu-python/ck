# apng_tool.py —— ck1.0 自带的“看图 / 伪装图检查”小工具
"""一个用 ck1.0 自己写的小工具：识别“点开原图变另一张图”的 APNG 伪装。

用法（在 ck1.0 文件夹里执行）:

    python apng_tool.py 图片.png              在控制台打印检查报告
    python apng_tool.py 图片.png --json       以 JSON 输出报告
    python apng_tool.py 图片.png --frames     顺便把每一帧导出到 <图片名>_frames/
    python apng_tool.py --gui                 打开图形界面
    python apng_tool.py                       不带参数 = --gui

图形界面里可以：选择图片 → 显示默认图/封面 → 播放动画 → 逐帧预览（标注封面与隐藏帧）
              → 拆帧导出 → 查看/复制结构报告。
"""
import os
import sys

try:                                    # 在项目目录内直接运行（APNG 已迁入 components/）
    from gui.main_window import MainWindow
    from ck1_0.components.apng import parser as apng_utils
except ImportError:                     # 已安装为包（package-dir 映射的 components/apng）
    from ck1_0 import MainWindow
    from ck1_0.components.apng import parser as apng_utils


IMAGE_TYPES = (
    ('图片文件', '*.png *.gif *.webp *.jpg *.jpeg *.bmp'),
    ('PNG / APNG', '*.png'),
    ('所有文件', '*.*'),
)


# --------------------------------------------------------------------------- #
# 命令行模式
# --------------------------------------------------------------------------- #
def cli(path, as_json=False, do_frames=False, max_frames=None):
    """在控制台输出检查报告，返回退出码。

：报告里含 `⚠` 等符号，而中文 Windows 的
    控制台/管道默认是 **GBK** ⇒ `print(...)` 会抛 `UnicodeEncodeError`，新手只看到一句
    看不懂的英文报错。这里把标准输出**显式切到 UTF-8**（`errors='replace'` 兜底，
    不会因为个别字符打不出来而中断）。**只影响编码，不改变任何输出内容与返回值。**
    """
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:                       # noqa: BLE001（重定向到非文本流时无 reconfigure）
            pass
    if not os.path.isfile(path):
        print(f'找不到文件: {path}')
        return 2

    info = apng_utils.analyze(path, deep=True, max_frames=max_frames)
    if as_json:
        print(apng_utils.to_json(info))
    else:
        print(apng_utils.format_report(info))
        if info.get('is_apng'):
            print(f"快速判定 is_disguised_image() = {apng_utils.is_disguised(path)}")

    if do_frames:
        outdir = os.path.splitext(path)[0] + '_frames'
        try:
            written = apng_utils.save_frames(path, outdir)
            print(f'\n已导出 {len(written)} 帧到: {outdir}')
            for w in written:
                print(f'  {os.path.basename(w)}')
        except Exception as e:
            print(f'\n拆帧失败: {e}')
            return 1
    return 0


# --------------------------------------------------------------------------- #
# 图形界面模式
# --------------------------------------------------------------------------- #
def run_gui(initial_path=None, autorun=True):
    """用 ck1.0 组件搭一个检查器窗口。

    参数:
        initial_path (str): 启动时自动加载的图片
        autorun (bool): True = 进入主循环；False = 只把界面建好并返回（便于自动化测试）

    返回:
        MainWindow 实例（autorun=False 时）
    """
    import tkinter as tk
    from tkinter import filedialog

    app = MainWindow('ck1.0 图片 / 伪装图检查器', 980, 800)
    app.center_window()

    state = {'path': initial_path or ''}

    app.label_ck('APNG 伪装图检查器', tsize=22)
    tk.Label(app.scrollable_frame,
             text='“点开原图就变另一张图”？把文件拖到这里打开，一键看清封面帧与隐藏帧。',
             fg='#666', font=('Microsoft YaHei', 10)).pack(pady=(0, 6))

    status_widget, set_status = app.create_status_bar('就绪：请先打开一张图片')

    # ---------------- 报告文本框 ----------------
    report_box = tk.Text(app.scrollable_frame, height=18, width=104, wrap='none',
                         font=('Consolas', 10), bg='#1e1e1e', fg='#e0e0e0',
                         insertbackground='#e0e0e0')
    report_box.pack(padx=10, pady=8, fill='both', expand=False)
    report_scroll = tk.Scrollbar(app.scrollable_frame, orient='vertical',
                                 command=report_box.yview)
    report_box.configure(yscrollcommand=report_scroll.set)
    report_scroll.pack(side='right', fill='y')

    def set_report(text):
        report_box.configure(state='normal')
        report_box.delete('1.0', 'end')
        report_box.insert('1.0', text)
        report_box.configure(state='disabled')

    def current_path(require=True):
        path = state['path']
        if require and not path:
            app.show_toast('请先打开一张图片', kind='warning')
        return path

    # ---------------- 各按钮动作 ----------------
    def choose_file():
        path = filedialog.askopenfilename(title='选择图片', filetypes=IMAGE_TYPES)
        if not path:
            return
        state['path'] = path
        set_status(f'已加载: {os.path.basename(path)}')
        do_check()

    def do_check():
        path = current_path()
        if not path:
            return
        report = app.apng_report(path)
        set_report(report)
        info = app.last_report or {}
        if info.get('is_apng'):
            disguised = app.is_disguised_image(path)
            set_status(f'APNG：共 {info.get("pil", {}).get("n_frames", info.get("num_frames"))} 帧'
                       f'{"，检测到“查看原图”式伪装" if disguised else "，未发现封面/隐藏帧不一致"}')
            if disguised:
                app.show_toast('检测到伪装 APNG：默认图与动画帧不是同一张图！', kind='warning')
        else:
            set_status('普通静态 PNG：没有多帧结构')

    def show_default_image():
        """只显示默认图/封面 —— 相当于 PS / 缩略图 / 照片查看器看到的那张。"""
        path = current_path()
        if not path:
            return
        app.photo(path, text='默认图 / 封面（非 APNG 查看器只显示这张）', frame=0, tsize=12)
        set_status('已显示默认图 / 封面（帧 0）')

    def show_hidden_frame():
        """直接跳到第 1 帧 —— 浏览器里“变脸”后看到的那张。"""
        path = current_path()
        if not path:
            return
        info = app.apng_info(path)
        n = info.get('pil', {}).get('n_frames', 1)
        if n < 2:
            app.show_toast('这不是多帧图片，没有隐藏帧', kind='info')
            return
        app.photo(path, text=f'第 1 帧（隐藏图，共 {n} 帧）', frame=1, tsize=12)
        set_status('已显示第 1 帧（隐藏图）')

    def play_animation():
        path = current_path()
        if not path:
            return
        count = app.animation(path, text='动画播放中', max_loops=5)
        set_status(f'播放中：{count} 帧（5 轮后自动停止）' if count else '播放失败（需要 Pillow）')

    def preview_frames():
        path = current_path()
        if not path:
            return
        app.clear_media()
        app.show_frames(path, columns=3, thumb_width=260)
        info = app.apng_info(path)
        set_status(f'逐帧预览：共 {info.get("pil", {}).get("n_frames", 1)} 帧，'
                   f'红字标注的是封面帧')

    def export_frames():
        path = current_path()
        if not path:
            return
        default_dir = os.path.splitext(path)[0] + '_frames'
        written = app.export_frames(path, outdir=default_dir)
        set_status(f'已导出 {len(written)} 帧到 {default_dir}' if written else '拆帧已取消')

    def copy_report():
        app._copy_text(report_box.get('1.0', 'end'))
        set_status('报告已复制到剪贴板')

    def show_about():
        app.show_message('关于',
                         'ck1.0 图片 / 伪装图检查器\n\n'
                         '· 结构分析：utils/apng.py（块级解析，不装 Pillow 也能用）\n'
                         '· 逐帧对比与拆帧：Pillow\n'
                         '· 界面：基于 ck1.0 的 MainWindow / 工具栏 / 状态栏 / Toast\n\n'
                         '用途：识别“查看原图”式 APNG 伪装（默认图 ≠ 动画帧）。')

    # ---------------- 工具栏 ----------------
    app.create_toolbar([
        ('打开图片', choose_file, 'button'),
        ('重新检查', do_check, 'button'),
        ('拆帧导出', export_frames, 'button'),
        ('关于', show_about, 'button'),
    ])

    # ---------------- 操作按钮区 ----------------
    def make_button(text, color, command):
        btn = tk.Button(app.scrollable_frame, text=text, bg=color, fg='white',
                        font=('Microsoft YaHei', 11, 'bold'), width=18, pady=6,
                        cursor='hand2', relief='flat', activebackground=color,
                        activeforeground='white', command=command)
        btn.pack(side='left', padx=5, pady=6)
        return btn

    row = tk.Frame(app.scrollable_frame)
    row.pack(pady=4)
    make_button('显示默认图', '#455a64', show_default_image)
    make_button('显示隐藏帧', '#c62828', show_hidden_frame)
    make_button('播放动画', '#1565c0', play_animation)
    make_button('逐帧预览', '#2e7d32', preview_frames)

    row2 = tk.Frame(app.scrollable_frame)
    row2.pack(pady=2)
    tk.Button(row2, text='复制报告', command=copy_report, width=14).pack(side='left', padx=5)
    tk.Button(row2, text='清空显示', command=lambda: (app.clear_media(), set_status('已清空')),
              width=14).pack(side='left', padx=5)
    tk.Button(row2, text='退出', command=app.root.destroy, width=14).pack(side='left', padx=5)

    if state['path']:
        do_check()
    else:
        set_report('请点击左上角“打开图片”，或把图片拖进本窗口…\n'
                   '（提示：本工具只读取文件，不会修改你的图片）')

    if autorun:
        app.run()
        return None
    app.root.update()          # 供测试使用：建好界面但不进入主循环
    return app


# --------------------------------------------------------------------------- #
# 入口
# --------------------------------------------------------------------------- #
def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ('--gui', '-g'):
        run_gui()
        return 0

    path = argv[0]
    as_json = '--json' in argv
    do_frames = '--frames' in argv
    max_frames = None
    if '--max-frames' in argv:
        try:
            max_frames = int(argv[argv.index('--max-frames') + 1])
        except (IndexError, ValueError):
            print('--max-frames 需要一个整数参数')
            return 2
    return cli(path, as_json=as_json, do_frames=do_frames, max_frames=max_frames)


if __name__ == '__main__':
    sys.exit(main())
