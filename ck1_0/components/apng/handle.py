"""handle.py —— ApngHandle：APNG 句柄（只做委托，不做解析、不做渲染）

位置（迁移）：本模块原为 `gui/apng_handle.py`，现为 `ck1_0/components/apng/handle.py`；
旧路径 `gui.apng_handle` 保留为 **deprecated 别名**（一个版本周期），实现只有这一份。

Advanced users can operate on .frames directly. Beginners only need .play(), .export(), .report(). Modifying .frames does NOT affect the currently playing animation, because the player uses an independently loaded frame copy.

高级用户可以直接操作 .frames。初学者只需要使用 .play()、.export()、.report()。修改 .frames 不会影响当前播放，因为播放器使用独立加载的帧副本。

设计约束（对应 ck1.0/设计约定 第 1.2 / 1.4 节）：

    * 本模块**不导入** PIL、tkinter 或 `.parser`：它既不解析 APNG，也不创建任何控件、
      不启动任何 after() 循环，因此不承担 APNG disposal 逻辑或帧调度。
    * 播放委托 ``host.animation()``，停止委托 ``host.stop_animation()``，
      导出委托 ``host.export_frames()``，报告委托 ``host.apng_report()`` /
      ``host.show_image_report()``，逐帧预览委托 ``host.show_frames()``。
      handle 只负责保存元数据与生命周期，不复制任何已有媒体逻辑。
    * 构造时传入的 ``frames`` / ``delays`` 已由调用方（``MediaMixin.apng()``）从 ``path``
      独立加载，这里**原样保存、不做 Image.copy()**；播放器每次都是按 ``path`` 重新加载
      自己的帧副本，所以高级用户修改 ``.frames`` 不会影响当前或之后的播放。

冻结文档文本（不得削弱语义，中英双语均已包含在上方）：

    Advanced users can operate on .frames directly. Beginners only need .play(),
    .export(), .report(). Modifying .frames does NOT affect the currently playing
    animation, because the player uses an independently loaded frame copy.

    高级用户可以直接操作 .frames。初学者只需要使用 .play()、.export()、.report()。
    修改 .frames 不会影响当前播放，因为播放器使用独立加载的帧副本。
"""


class ApngHandle:
    """APNG / 多帧图片句柄：面向初学者的扁平入口，面向高级用户的原始帧视图。

    典型的初学者用法::

        handle = app.apng('2345.png')       # 由 MediaMixin.apng() 返回（可以返回 None）
        if handle:
            handle.play()                   # 播放
            handle.export(outdir)           # 拆帧导出
            print(handle.report())          # 结构报告
            handle.close()                  # 停止并释放

    高级用户可以直接读写 ``handle.frames`` / ``handle.delays``（原始对象），
    但播放器始终按 ``path`` 独立加载帧副本，因此这些修改不会影响播放。

    生命周期契约:

        * 构造完成后即可反复 ``stop()`` / ``play()``，不要求重新创建 handle。
        * ``close()`` 是幂等的：先委托 ``host.stop_animation()`` 取消待执行的 after
          定时器，然后释放 handle 对 frames/delays/info 的引用，但**不会**销毁 host
          窗口或 host 本身。
        * ``close()`` 之后 ``play()`` / ``export()`` / ``report()`` / ``show_frames()``
          一律抛 ``RuntimeError("ApngHandle is closed")``；``stop()`` / ``close()``
          保持幂等（静默 no-op）。
    """

    def __init__(self, host, path, frames, delays, loop_count, info,
                 is_disguised, total_frames, *, text='', tcolor='#000000',
                 tzt='Microsoft YaHei', tsize=20, tblod=True,
                 start=0, max_frames=None, frame_delay=None):
        """保存宿主引用与既有分析结果，不做任何解析、不做帧拷贝。

        参数:
            host: 宿主（MediaMixin / MainWindow），所有实际动作都委托给它。
            path (str): 已解析的图片路径；播放/导出/报告都按它重新加载。
            frames (list): 原始图像对象列表，供高级用户直接操作；
                已由调用方从 path 独立加载，这里原样保存（不 Image.copy()）。
            delays (list): 每帧延时（毫秒），长度与可用 frames 对齐。
            loop_count (int): 文件声明的循环次数；0 表示无限循环，非 APNG 单帧 PNG 为 1。
            info (dict): host.apng_info(path) 的结构化报告，格式不在本模块重新定义。
            is_disguised (bool): host.is_disguised_image(path) 的结果。
            total_frames (int): 该 handle 实际持有的帧数，通常等于 len(frames)。
            text/tcolor/tzt/tsize/tblod: 与 photo() / animation() 一致的显示参数。
            start (int): 默认播放起始帧，play() 未显式传参时使用。
            max_frames (int | None): 该 handle 的帧元数据上限；
                注意 play() 不把它传给 host.animation()（保持最小委托实参表，
                播放器按 path 重新加载完整帧序列）。
            frame_delay (int | None): 强制统一帧间隔（毫秒）；None 使用文件帧延时。
        """
        # 宿主与路径
        self.host = host
        self.path = path

        # 原始帧数据（调用方已独立加载，这里不复制）
        self.frames = frames
        self.delays = delays

        # 既有分析结果（不重新定义格式）
        self.loop_count = loop_count
        self.info = info
        self.is_disguised = is_disguised
        self.total_frames = total_frames

        # 显示与播放参数
        self.text = text
        self.tcolor = tcolor
        self.tzt = tzt
        self.tsize = tsize
        self.tblod = tblod
        self.start = start
        self.max_frames = max_frames
        self.frame_delay = frame_delay

        # 生命周期标志
        self._closed = False

    # ------------------------------------------------------------------ #
    # 播放 / 停止
    # ------------------------------------------------------------------ #
    def play(self, start=None, max_loops=None) -> None:
        """播放动画（委托 ``host.animation()``，不实现第二套帧循环）。

        参数:
            start (int | None): 起始帧；None 表示使用构造时的 ``self.start``。
            max_loops (int | None): 播放轮数；None 表示使用文件的 loop 语义
                （``loop_count == 0`` → 无限循环，映射为 ``max_loops=None``；
                否则使用 ``loop_count`` 作为轮数上限）。

        返回:
            None。实际加载的帧数由 ``host.animation()`` 返回，本方法按合同忽略它。

        说明:
            ``host.animation()`` 会按 ``self.path`` 重新独立加载帧，因此 handle 的
            ``.frames`` 仅是可查看/可操作的原始列表，修改它不会影响本次播放。
            本方法不传 ``max_frames``（保持最小委托实参表）；``handle.max_frames``
            只描述该 handle 的帧元数据。
        """
        if self._closed:
            raise RuntimeError("ApngHandle is closed")

        eff_start = self.start if start is None else start
        eff_max_loops = max_loops
        if eff_max_loops is None:
            # 文件 loop 语义：0 = 无限循环；其余用文件声明的轮数
            eff_max_loops = None if self.loop_count == 0 else self.loop_count

        self.host.animation(self.path, start=eff_start, max_loops=eff_max_loops,
                            frame_delay=self.frame_delay, text=self.text,
                            tcolor=self.tcolor, tzt=self.tzt, tsize=self.tsize,
                            tblod=self.tblod)

    def stop(self) -> None:
        """停止播放（幂等）：委托 ``host.stop_animation()``，保留 handle 以便再次 play()。

        已关闭（closed）时静默 no-op，不抛异常。
        """
        if self._closed:
            return
        self.host.stop_animation()

    # ------------------------------------------------------------------ #
    # 导出 / 报告 / 预览
    # ------------------------------------------------------------------ #
    def export(self, outdir=None, include_default=True, prefix='frame') -> list:
        """拆帧导出为独立 PNG（委托 ``host.export_frames()``）。

        参数:
            outdir (str | None): 输出目录；None 时由宿主弹出目录选择框。
            include_default (bool): 是否包含默认图（帧 0）。
            prefix (str): 输出文件名前缀。

        返回:
            list[str]: 写出的文件路径；取消或失败时为空列表（沿用宿主行为）。
        """
        if self._closed:
            raise RuntimeError("ApngHandle is closed")
        return self.host.export_frames(path=self.path, outdir=outdir,
                                       include_default=include_default, prefix=prefix)

    def report(self, deep=True, max_frames=None, show=False) -> str:
        """返回结构报告文本（委托 ``host.apng_report()``，不复制报告生成逻辑）。

        参数:
            deep (bool): 是否逐帧做像素对比（需要 Pillow）。
            max_frames (int | None): 逐帧分析的最大帧数。
            show (bool): True 时先调用 ``host.show_image_report()`` 弹出报告窗口。

        返回:
            str: 报告文本，始终来自 ``host.apng_report()``。
        """
        if self._closed:
            raise RuntimeError("ApngHandle is closed")
        if show:
            self.host.show_image_report(self.path, deep=deep, max_frames=max_frames)
        return self.host.apng_report(self.path, deep=deep, max_frames=max_frames)

    def show_frames(self, columns=3, thumb_width=240, labels=True, parent=None,
                    max_frames=None):
        """平铺预览各帧（委托 ``host.show_frames()``）。

        参数:
            columns (int): 每行几张。
            thumb_width (int): 缩略图宽度（像素）。
            labels (bool): 是否显示帧号/尺寸/延时标注。
            parent: 容器；None 时由宿主选择默认容器。
            max_frames (int | None): 最多预览多少帧。

        返回:
            tk.Frame | None: 宿主返回的预览容器。
        """
        if self._closed:
            raise RuntimeError("ApngHandle is closed")
        return self.host.show_frames(self.path, columns=columns, thumb_width=thumb_width,
                                     labels=labels, parent=parent, max_frames=max_frames)

    # ------------------------------------------------------------------ #
    # 生命周期
    # ------------------------------------------------------------------ #
    def close(self) -> None:
        """停止播放并释放 handle 引用（幂等）；不会销毁 host / root。

        行为:
            * 已关闭时直接返回（no-op）。
            * 委托 ``host.stop_animation()`` 取消待执行的 after 定时器。
            * 清空 ``frames`` / ``delays`` / ``info``，置 ``_closed = True``。
        """
        if self._closed:
            return
        self.host.stop_animation()
        self.frames = []
        self.delays = []
        self.info = {}
        self._closed = True
