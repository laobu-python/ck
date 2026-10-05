"""media.py —— MediaMixin：图片 / GIF / APNG（含“查看原图”式伪装图）支持

依赖：Pillow（`pip install pillow`），仅在调用 photo()/animation()/frames 相关方法时按需使用。
    - 未安装 Pillow 时，库的其余部分照常可用；
    - 块级 APNG 结构分析由 `utils/apng.py` 提供，**不装 Pillow 也能用**（只是没有逐帧像素对比）。

本文件相对早期版本的变化：
    * photo() 新增 `frame` 参数：可指定显示 APNG/GIF 的哪一帧（默认 0，即“默认图/封面”）
    * gif() 升级为通用动画播放：支持 APNG / 动态 WebP，逐帧使用各自延时，可限制循环轮数
    * 新增 animation()：更强的播放接口（起始帧、最大帧数、每帧回调）
    * 新增 apng_info() / apng_report() / is_disguised_image()：识别“默认图与动画帧不一致”的伪装 APNG
    * 新增 show_image_report() / show_frames() / export_frames()：报告窗口、逐帧预览、拆帧导出
    * 修掉旧版 `animate_gif()` 在 clear_media() 之后仍用 after() 空转的问题
"""
import os

try:
    from PIL import Image, ImageTk, ImageSequence
    _PIL_AVAILABLE = True
except ImportError:
    Image = ImageTk = ImageSequence = None
    _PIL_AVAILABLE = False

try:                                    # 作为 ck1_0 包被导入（APNG 已迁入 components/）
    from ..components.apng import parser as apng_utils
    from ..components.apng import ApngHandle
except ImportError:                     # 以脚本方式在项目根目录运行（gui 为顶层包）
    try:
        from ck1_0.components.apng import parser as apng_utils
        from ck1_0.components.apng import ApngHandle
    except ImportError:
        apng_utils = None
        ApngHandle = None

try:                                    # 脚本模式：cwd = 项目根，gui 为顶层包
    from ck1_0.core.theme import Theme
except ImportError:                     # 包模式：本文件即 ck1_0.gui.media
    from ..core.theme import Theme

# gui 包**内部**的依赖用相对导入（脚本模式下 `gui` 是顶层包、包模式下是 `ck1_0.gui`）。
# 本模块逐步改走 Renderer 的中立媒体 API（`_renderer_of` 取宿主 Renderer）。
try:                                    # 脚本模式：cwd = 项目根
    from ck1_0.renderer.base import Layout
except ImportError:                     # 包模式：本文件即 ck1_0.gui.media
    from ..renderer.base import Layout

from .widgets import _content_parent, _renderer_of      # noqa: E402

try:                                    # 脚本模式：cwd = 项目根
    from ck1_0.renderer.base import NotSupportedError
except ImportError:                     # 包模式：本文件即 ck1_0.gui.media
    from ..renderer.base import NotSupportedError


def _resample_filter():
    """兼容新旧 Pillow 的重采样枚举。"""
    if Image is None:
        return None
    resampling = getattr(Image, 'Resampling', None)
    if resampling is not None:
        return resampling.LANCZOS
    return getattr(Image, 'LANCZOS', 1)


class MediaMixin:
    def __init__(self, theme=None):
        # 语义 token 表：显式传入 > 宿主已有 theme > 基线主题（不覆盖 root/scrollable_frame）
        if theme is not None:
            self.theme = theme
        elif not hasattr(self, 'theme'):
            self.theme = Theme.light()
        # 初始化媒体相关状态
        self.photo_img = None
        self.frames = []
        self.delay = self.theme.media_default_frame_delay_ms
        self.frame_delays = []
        self.gif_label = None
        self.label = None
        self.now_pafl = None
        self.current_frame = 0

        # ck1.0 新增：动画控制与检查器状态
        self.max_loops = None           # 播放轮数上限（None = 无限）
        self._anim_after_id = None      # 待执行的 after 回调 id
        self._anim_playing = False      # 播放中标志
        self._anim_loop = 0             # 已完整播放的轮数
        self._anim_on_frame = None      # 每帧回调
        self._frame_thumbs = []         # 逐帧预览的 PhotoImage 引用（防止被 GC）
        self._last_image_path = None    # 最近一次加载的图片路径
        # ：中立媒体句柄（`photo` 用它记「最后一张图」；renderer 侧持有像素引用防 GC
        # ⇒ facade 不再维护 `photo_img`/`label`/`now_pafl` 这三个 Tk 专属字段）。
        self._photo_handle = None
        # ：当前动画句柄（帧循环归 backend；`stop_animation`/`clear_media` 经它停表）
        self._anim_handle = None
        # ：逐帧预览的**中立句柄**（首版的 `_frame_thumbs` 存的是 PhotoImage，
        # 用来防 GC；现在像素引用由 renderer 持有 ⇒ 这里记句柄/窗口，语义从「防 GC」变「可回收」）。
        self._frame_previews = []
        self.last_report = None         # 最近一次 apng_info() 的结果

    # ------------------------------------------------------------------ #
    # 清理
    # ------------------------------------------------------------------ #
    def clear_media(self):
        """清理当前显示的媒体（图像或动画），并取消未执行的动画回调。

：**释放责任**改走中立 API —— 动画用 `renderer.clear_media()`（逐个
        `stop()` + `destroy()` 并清空它的登记表），当前**图片**句柄显式 `destroy()`（图片是
        `parent` 所有、不在 的动画登记里 ⇒ 由 facade 负责，与首版销毁 label 同义）。
        `_anim_playing`/`_anim_after_id`/`frames`/`frame_delays` 等 facade 字段**继续维护**
        （外部/探针仍在读；帧循环归 backend ⇒ `_anim_after_id` 恒为 `None`）。
       容错与首版一致：整个清理过程不抛（首版是 `try/except: pass`）。
        """
        self._anim_playing = False
        self._anim_on_frame = None
        self._anim_after_id = None
        try:
            _renderer_of(self).clear_media()
        except Exception:                  # 无 renderer 的宿主：与首版一样静默通过
            pass
        for _attr in ('_anim_handle', '_photo_handle'):
            _h = getattr(self, _attr, None)
            if _h is not None:
                try:
                    _h.destroy()
                except Exception:
                    pass
                setattr(self, _attr, None)
        # 清理引用，允许 GC（facade 侧账本；控件本身已随句柄销毁）
        self.photo_img = None
        self.frames = []
        self.frame_delays = []
        self.now_pafl = None
        self.current_frame = 0
        self._frame_thumbs = []

    # ------------------------------------------------------------------ #
    # 依赖检查
    # ------------------------------------------------------------------ #
    def _need_pillow(self):
        """Pillow 未安装时给出友好提示，返回 False 表示不可用。"""
        if _PIL_AVAILABLE:
            return True
        print("错误：显示图片/GIF 需要 Pillow 库，请先执行 pip install pillow")
        if getattr(self, 'root', None):
            show = getattr(self, 'show_message', None)
            if show:
                self.root.after(0, lambda: show("缺少依赖", "请先安装 Pillow：pip install pillow", "error"))
        return False

    def _media_parent(self):
        """图片/动画要挂在哪个容器上。"""
        parent = getattr(self, 'scrollable_frame', None)
        if parent is None:
            parent = getattr(self, 'root', None)
        return parent

    # ------------------------------------------------------------------ #
    # 静态图片（ck1.0：支持选帧）
    # ------------------------------------------------------------------ #
    def photo(self, photo_path='', text='', tcolor='#000000', tzt='Microsoft YaHei',
              tsize=20, tblod=True, frame=0, warn_animated=True):
        """显示静态图片（支持常见图片格式）。

        参数:
            photo_path (str): 图片路径
            text (str): 图片下方文字
            tcolor/tzt/tsize/tblod: 文字颜色 / 字体 / 字号 / 是否加粗
            frame (int): 显示第几帧；0 表示“默认图/封面”（APNG 里非动画查看器看到的就是它），
                         None 表示按文件默认解析结果（不主动 seek）
            warn_animated (bool): 若文件其实是多帧（APNG/GIF），是否在控制台提示帧数

        返回:
            `MediaHandle | None`：中立句柄（`.native` = 承载图片与说明的容器 Frame；
           首版直接返回一个 `tk.Label`）；Pillow 缺失 / 文件不存在 / 解码失败 ⇒ `None`
            （首版冻结语义）。
        """
        # ：**画图本身**改走 renderer 的中立 `photo(...)`—— 取帧、`PhotoImage`、
        # 像素引用防 GC、容器/说明 Label 的 token 全在 backend。
        # 保留在 facade 的三件事：① 先 `clear_media()`（首版逐字）；② 面向用户的**人话报错**
        # （renderer 的冻结语义是「静默 `None`」，故提示必须留在这里）；③ 记 `_last_image_path`
        # 与中立句柄 `_photo_handle`（`apng_info(path=None)` 依赖前者）。
        self.clear_media()
        if not self._need_pillow():
            return None
        if not os.path.isfile(photo_path or ''):
            print("错误：找不到图片文件！请检查文件名和路径。")
            if getattr(self, 'root', None):
                self.root.after(0, lambda: self.show_message("错误", "图片文件不存在！", "error"))
            return None
        self._last_image_path = os.path.abspath(photo_path)
        # `frame=None`（首版文档：「不主动 seek」）⇒ 中立契约只收 `int` ⇒ 传 `0`。
        # 语义等价：刚打开的文件本来就在第 0 帧（首版的 `else: target = 0` 也是这样记的）。
        handle = _renderer_of(self).photo(_content_parent(self), photo_path, text=text,
                                          color=tcolor, family=tzt, size=tsize, bold=tblod,
                                          frame=0 if frame is None else frame,
                                          warn_animated=warn_animated)
        if handle is None:
            print("错误：无法加载图片（格式不支持或文件已损坏）。")
            if getattr(self, 'root', None):
                self.root.after(0, lambda: self.show_message(
                    "错误", "无法加载图片，请检查文件是否损坏。", "error"))
            return None
        self._photo_handle = handle
        return handle

    # ------------------------------------------------------------------ #
    # 动画播放（GIF / APNG / 动态 WebP）
    # ------------------------------------------------------------------ #
    def animate_gif(self):
        """**已退役的兼容入口**（第 3 刀）：帧循环归 backend 的 `AnimationHandle`。

       首版里它是 facade 自己 `root.after` 的**每帧回调**（由 `animation()` 启动、
        `clear_media()`/`stop_animation()` 停止）。本版起播放由 backend 的定时器驱动
        ⇒ 再让调用方手动"推一帧"只会造成**双分发**，故这里**显式拒绝**（不静默）并
        告诉新手该用什么。

        想停表：`stop_animation()`；想从头播：`animation(...)`；想自己接管：直接拿
        `renderer.animation(...)` 返回的句柄（facade 侧经 `self._anim_handle` 也能看到它）。
        """
        raise NotSupportedError(
            "animate_gif() 已不再由 facade 驱动帧循环（本版起播放归 Renderer 的动画句柄）："
            "要停止请调用 stop_animation()，要重新播放请调用 animation(...)，"
            "需要自己接管帧循环请使用 renderer.animation(...) 返回的句柄。")

    def animation(self, path='', text='', tcolor='#000000', tzt='Microsoft YaHei',
                  tsize=20, tblod=True, start=0, max_frames=None, max_loops=None,
                  on_frame=None, frame_delay=None):
        """播放动图（GIF / APNG / 动态 WebP）。

        参数:
            path (str): 动图路径
            text/tcolor/tzt/tsize/tblod: 与 photo() 一致
            start (int): 从第几帧开始（APNG 中 0 通常是“默认图/封面”，想直接看隐藏帧可传 1）
            max_frames (int): 最多加载多少帧
            max_loops (int): 播放几轮后停止（None = 无限循环）
            on_frame (callable): 每帧回调 `on_frame(帧号, 总帧数)`
            frame_delay (int): 强制统一帧间隔（毫秒），None 表示使用文件每帧自带延时

        返回:
            int: 实际加载的帧数（Pillow 不可用或失败时为 `0`）—— **返回形状与首版逐字一致**；
            帧循环与帧数据归 backend 的 `AnimationHandle`，facade 经 `self._anim_handle` 持有它
            （`stop_animation`/`clear_media` 用它停表）。想看句柄本身请用 `renderer.animation(...)`。
        """
        # ：**播放本身**改走 renderer 的中立 `animation(...)`—— 取帧、`PhotoImage`、
        # 每帧延时（含 `media_min_frame_delay_ms` 下限）、`start`/`max_frames`/`max_loops`/
        # `on_frame`/`frame_delay` 全在 backend；**facade 只负责**：先 `clear_media()`、
        # **人话报错**（renderer 失败时是静默的 `frame_count == 0`）、把 `int` 帧数返回给调用方。
        self.clear_media()
        if not self._need_pillow():
            return 0
        if not os.path.isfile(path or ''):
            print(f"错误：找不到动图文件 '{path}'。")
            if getattr(self, 'root', None):
                self.root.after(0, lambda: self.show_message("错误", "动图文件不存在，请检查路径！", "error"))
            return 0
        self._last_image_path = os.path.abspath(path)
        handle = None
        try:
            handle = _renderer_of(self).animation(
                _content_parent(self), path, text=text, color=tcolor, family=tzt,
                size=tsize, bold=tblod, start=start, max_frames=max_frames,
                max_loops=max_loops, on_frame=on_frame, frame_delay=frame_delay)
            n_frames = int(handle.frame_count)
        except Exception as e:                      # 说人话的兜底（首版同位置同风格）
            print(f"设置动画标签时出错: {e}")
            if getattr(self, 'root', None):
                self.root.after(0, lambda: self.show_message(
                    "错误", f"动图加载失败：{type(e).__name__}", "error"))
            return 0
        if not n_frames:
            # 中立层的失败哨兵：容器**仍被创建**（契约要求调用方自行 `destroy()`）⇒ 这里销毁它，
            # 与首版「失败时不建任何控件」的可观察结果对齐。
            print(f"设置动画标签时出错: 无法加载 '{os.path.basename(str(path))}' 的帧。")
            if getattr(self, 'root', None):
                self.root.after(0, lambda: self.show_message(
                    "错误", "动图加载失败，请检查文件是否损坏。", "error"))
            try:
                handle.destroy()
            except Exception:
                pass
            return 0
        self._anim_handle = handle
        self._anim_playing = True                   # 兼容字段：帧循环归 backend，标志仍如实为「播放中」
        self._anim_after_id = None                  # facade 不再持有 after id（backend 的定时器）
        self._anim_on_frame = on_frame
        self.max_loops = max_loops
        self.current_frame = 0
        self._anim_loop = 0
        return n_frames

    def gif(self, gif_path='', text='', tcolor='#000000', tzt='Microsoft YaHei',
            tsize=20, tblod=True, **kwargs):
        """加载并播放 GIF 动画（ck1.0：同时支持 APNG / 动态 WebP，签名保持兼容）。

        额外关键字参数会透传给 animation()：start / max_frames / max_loops / on_frame / frame_delay。
        """
        return self.animation(gif_path, text=text, tcolor=tcolor, tzt=tzt,
                              tsize=tsize, tblod=tblod, **kwargs)

    def apng(self, path='', text='', tcolor='#000000', tzt='Microsoft YaHei',
             tsize=20, tblod=True, autoplay=True, start=0, max_frames=None,
             max_loops=None, frame_delay=None):
        """**APNG 统一入口**—— 返回 `ApngHandle | None`。

        初学者只需要三件事：`handle.play()` / `handle.export()` / `handle.report()`；
        高级用户可以直接读写 `handle.frames` —— **改它不会影响正在播的动画**，因为播放器
        始终按 `path` 独立重新加载帧副本。

       返回规则（`设计说明`，逐条实现）：

        * Pillow 缺失 / 空路径 / 文件不存在或读不了 / **不是 PNG** / 解析失败（malformed acTL·fcTL）
          ⇒ `None`（**不返回半有效对象**）；
        * **PNG 但不是 APNG**（单帧）⇒ 返回**有效 handle**：`frames=[img]`、
          `delays=[默认帧延时]`、`loop_count == 1`；
        * 合法 APNG ⇒ 返回 handle，`info`/`is_disguised` 来自既有 `apng_info()`/
          `is_disguised_image()`（**不重新定义报告格式**）。

        委托（**不复制任何既有逻辑**）：播放 → `animation()`、停止 → `stop_animation()`、
        导出 → `export_frames()`、报告 → `apng_info()`/`apng_report()`/`show_image_report()`、
        逐帧预览 → `show_frames()`。

        参数:
            path (str): APNG/PNG 文件路径（空 ⇒ `None`；**不**回落"最近一次加载的图片"）
            text/tcolor/tzt/tsize/tblod: 与 `photo()`/`animation()` 一致的显示参数
            autoplay (bool): `True` ⇒ 经 `animation()` 建标签并开播；`False` ⇒ 只显示第 0 帧、不开播
            start (int): 播放起始帧（初始静态显示仍是第 0 帧）
            max_frames (int | None): 最多加载/纳入 handle 的帧数
            max_loops (int | None): 播放轮数；`None` ⇒ 用文件声明的 loop 语义
            frame_delay (int | None): 强制统一帧间隔（毫秒）；`None` ⇒ 用文件每帧延时

        返回:
            `ApngHandle | None`
        """
        # ① 依赖与路径（缺 Pillow 不抛 —— Pillow 始终是可选依赖）
        if not self._need_pillow() or ApngHandle is None:
            return None
        if not path or not os.path.isfile(path):
            return None
        # ② 必须是 PNG（按**文件签名**判，不靠扩展名）
        try:
            with open(path, 'rb') as _fh:
                if _fh.read(8) != b'\x89PNG\r\n\x1a\n':
                    return None
        except OSError:
            return None
        # ③ 结构化报告 + 伪装判定：**委托既有方法**；解析失败（malformed）统一 None
        try:
            info = self.apng_info(path, max_frames=max_frames)
            disguised = self.is_disguised_image(path)
        except Exception:                  # noqa: BLE001 —— 包含 ValueError/RuntimeError/解析异常
            return None
        # ④ handle 的"高级用户"帧视图：一次读取 + `Image.copy()`（与播放器用的副本**分离**）
        try:
            with Image.open(path) as image:
                total = getattr(image, 'n_frames', 1)
                if max_frames:
                    total = min(total, max_frames)
                # APNG：`info['loop'] == 0` ⇒ 无限循环；静态 PNG 没有该键 ⇒ 1（PLAN）
                loop_count = int(image.info.get('loop', 1))
                frames, delays = [], []
                for _i in range(total):
                    image.seek(_i)
                    frames.append(image.copy())
                    _d = image.info.get('duration') or self.theme.media_default_frame_delay_ms
                    delays.append(max(self.theme.media_min_frame_delay_ms, int(_d)))
        except Exception as _exc:          # noqa: BLE001 —— 统一 None，不抛半有效对象
            print(f'APNG 解析失败: {_exc}')
            return None
        if not frames:
            return None
        handle = ApngHandle(self, os.path.abspath(path), frames, delays, loop_count,
                            info, bool(disguised), len(frames),
                            text=text, tcolor=tcolor, tzt=tzt, tsize=tsize,
                            tblod=tblod, start=start, max_frames=max_frames,
                            frame_delay=frame_delay)
        if autoplay:
            handle.play(start=start, max_loops=max_loops)      # 委托 `animation()`
        else:
            # 只显示第 0 帧、**不**开播（`photo()` 也是既有方法；同样委托，不自建控件）
            self.photo(path, text=text, tcolor=tcolor, tzt=tzt, tsize=tsize,
                       tblod=tblod, frame=0)
        return handle

    def stop_animation(self):
        """停止当前动画播放（控件保留）。

：帧循环归 `AnimationHandle` ⇒ 停表经中立 `handle.stop()`（幂等）；
        facade 的 `_anim_playing`/`_anim_after_id` 同步成"已停"，供既有代码/探针读取。
        """
        self._anim_playing = False
        self._anim_after_id = None
        _h = getattr(self, '_anim_handle', None)
        if _h is not None:
            try:
                _h.stop()
            except Exception:
                pass

    # ------------------------------------------------------------------ #
    # APNG / 伪装图检查
    # ------------------------------------------------------------------ #
    def apng_info(self, path=None, deep=True, max_frames=None):
        """分析图片结构，返回报告 dict（详见 utils/apng.analyze）。

        参数:
            path (str): 图片路径；None 表示最近一次 photo()/animation() 加载的文件
            deep (bool): 是否逐帧做像素对比（需要 Pillow）
            max_frames (int): 逐帧分析的最大帧数

        返回:
            dict
        """
        path = path or self._last_image_path
        if not path:
            raise ValueError('未指定图片路径，且此前没有加载过图片')
        if apng_utils is None:
            raise RuntimeError('缺少 utils/apng.py，无法分析图片结构')
        info = apng_utils.analyze(path, deep=deep, max_frames=max_frames)
        self.last_report = info
        return info

    def apng_report(self, path=None, deep=True, max_frames=None):
        """返回人类可读的中文文本报告（字符串）。"""
        info = self.apng_info(path, deep=deep, max_frames=max_frames)
        return apng_utils.format_report(info)

    def is_disguised_image(self, path=None, deep=True):
        """判断是否为“默认图与动画帧不一致”的伪装 APNG（“查看原图”式骗图）。"""
        path = path or self._last_image_path
        if not path or apng_utils is None:
            return False
        try:
            return bool(apng_utils.is_disguised(path, deep=deep))
        except Exception:
            return False

    def show_image_report(self, path=None, deep=True, max_frames=None,
                          title='图片结构检查报告'):
        """弹出报告窗口（只读文本 + 双向滚动条 + 「复制报告 / 拆帧导出… / 关闭」三个按钮），
        返回报告文本。

：窗口本体改走 renderer 的 `report_window(title, text)`（它按契约只负责
        **展示**，几何/只读正文/滚动条/token 都在 backend）；首版那三个按钮是**业务组合**，
       按的说明由本层用 `container` + `button` + 窗口句柄拼出来（`关闭` = `handle.destroy()`）。
       摆法与首版逐字相同：按钮条 `grid(row=2, columnspan=2, sticky='ew')`，
        按钮在条内 `pack(side='left'/'right', padx=…, pady=…)`（token `media_report_button_padx/pady`）。
       无 `root` 时仍只打印报告并返回（首版冻结语义）。
        """
        report = self.apng_report(path=path, deep=deep, max_frames=max_frames)
        if not getattr(self, 'root', None):
            print(report)
            return report
        renderer = _renderer_of(self)
        win = renderer.report_window(title, report)
        bottom = renderer.container(win, layout=Layout.grid(row=2, column=0, columnspan=2,
                                                             sticky='ew'))
        btn_padx, btn_padx_small = self.theme.media_report_button_padx
        btn_pady = self.theme.media_report_button_pady
        _copy = renderer.button(bottom, '复制报告', command=lambda: self._copy_text(report))
        _copy.layout(Layout.pack(side='left', padx=btn_padx, pady=btn_pady))
        _exp = renderer.button(bottom, '拆帧导出…', command=lambda: self.export_frames(path=path))
        _exp.layout(Layout.pack(side='left', padx=btn_padx_small, pady=btn_pady))
        _close = renderer.button(bottom, '关闭', command=win.destroy)
        _close.layout(Layout.pack(side='right', padx=btn_padx, pady=btn_pady))
        self._report_handles = getattr(self, '_report_handles', [])
        self._report_handles.append((win, bottom, _copy, _exp, _close))
        return report

    def _copy_text(self, content):
        """把文本放入系统剪贴板（失败时静默 —— 首版就是 `try/except: pass`）。

：改写**中立**剪贴板 API `renderer.set_clipboard_text(...)`；
       首版的 `root.update_idletasks()` 是 Tk 的剪贴板落盘手法，中立层由 backend 负责，
        facade 不再调它。提示气泡仍走 `show_toast(...)`。
        """
        try:
            _renderer_of(self).set_clipboard_text(content)
            toast = getattr(self, 'show_toast', None)
            if toast:
                toast('报告已复制到剪贴板', kind='success')
        except Exception:
            pass

    def show_frames(self, path=None, columns=3, thumb_width=240, labels=True,
                    parent=None, max_frames=None):
        """把各帧平铺预览出来（重点：把「默认图/封面」和动画帧分开标注）。

        参数:
            path (str): 图片路径；None 表示最近加载过的图片
            columns (int): 每行几张
            thumb_width (int): 缩略图宽度（像素）
            labels (bool): 是否显示帧号/尺寸/延时标注
            parent: 容器（**中立句柄或原生控件都收**），默认用宿主的内容容器
            max_frames (int): 最多预览多少帧

        返回:
            `Handle`（容器句柄；`.native` 是承载缩略图网格的 Frame）或 `None`
            （Pillow 缺失 / 缺路径 / 解码失败）—— 首版返回 `tk.Frame`。
        """
        # ：缩略图网格改走 renderer 的中立 `frame_preview(...)`—— 取帧、缩放、
        # 「默认图 vs 动画帧」标注、格间距、字体/颜色 token 全在 backend；
        # **像素引用由 renderer 持有**（首版靠 facade 的 `_frame_thumbs` 防 GC）。
        if not self._need_pillow():
            return None
        path = path or self._last_image_path
        if not path:
            raise ValueError('未指定图片路径，且此前没有加载过图片')
        renderer = _renderer_of(self)
        # 入参兼容：句柄直接用；首版风格的原生控件现包一次（与 `advanced_widgets._as_handle`
        # 同一手法 —— 本模块只有这一处需要，故内联；将来若第三处需要就上移到 `gui/widgets.py`）。
        if parent is None:
            _parent = _content_parent(self)
        elif hasattr(parent, 'native'):
            _parent = parent
        else:
            _parent = type(renderer.root)(parent)
        handle = renderer.frame_preview(_parent, path, columns=columns,
                                       thumb_width=thumb_width, labels=labels,
                                       max_frames=max_frames)
        if handle is None:
            print(f'逐帧预览失败: 无法渲染 {os.path.basename(str(path))} 的帧')
            return None
        self._frame_previews.append(handle)
        update = getattr(self, '_update_scrollregion', None)
        if callable(update):
            update()
        return handle

    def export_frames(self, path=None, outdir=None, include_default=True, prefix='frame'):
        """把多帧图片按帧导出为独立 PNG（拆帧）。

        参数:
            path (str): 源文件；None 表示最近加载过的图片
            outdir (str): 输出目录；None 时弹出目录选择框
            include_default (bool): 是否包含默认图（帧 0）
            prefix (str): 输出文件名前缀

        返回:
            list[str]: 写出的文件路径（失败/取消返回空列表）
        """
        if not self._need_pillow():
            return []
        path = path or self._last_image_path
        if not path:
            raise ValueError('未指定图片路径，且此前没有加载过图片')

        if not outdir:
            # ：目录选择改走 renderer 的中立 `ask_directory(...)`（取消 ⇒ `None`）。
            outdir = _renderer_of(self).ask_directory(title=self.theme.media_export_dialog_title)
            if not outdir:
                return []

        try:
            if apng_utils is None:      # 理论上不会发生
                raise RuntimeError('缺少 utils/apng.py')
            written = apng_utils.save_frames(path, outdir, prefix=prefix,
                                             include_default=include_default)
            toast = getattr(self, 'show_toast', None)
            if toast:
                toast(f'已导出 {len(written)} 帧到 {outdir}', kind='success')
            return written
        except Exception as e:
            print(f'拆帧导出失败: {e}')
            if getattr(self, 'root', None):
                self.root.after(0, lambda: self.show_message('错误', f'拆帧导出失败：{e}', 'error'))
            return []
