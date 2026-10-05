"""draw.py —— Tk Canvas 纯绘制助手（/ 早期）

本模块只做**几何计算 + canvas 绘制调用**：不绑定事件、不创建控件、不做业务判断、
不读取 Theme。调用方传入一个真实的 Tk Canvas（或任何暴露同名 `create_*` 方法的对象）。

为什么本模块**不 import tkinter**
    * 这些助手只用 canvas 的方法和字符串字面量（`'center'`、`anchor`、颜色名），
      完全不需要 tkinter 常量；不 import 就不会在缺 tkinter 的环境里 import 失败，
      `python -c "from ck1_0.renderer.tk import draw"` 与 `--help` 之类都不受影响。
    * 需要 Tk 常量时由调用方（Tk renderer 层）自己持有，本层保持后端无关的纯函数。

坐标约定：`x1 <= x2`、`y1 <= y2` 表示矩形左上/右下角；传入顺序颠倒时函数内部会归一化。
颜色/字体一律由调用方给出（通常来自 `ck1_0.core.theme.Theme`），本模块不含任何默认视觉值以外的常量。
"""


def rounded_rect(canvas, x1, y1, x2, y2, r, fill, outline=None, width=1):
    """在 canvas 上画一个圆角矩形。

    参数:
        canvas: Tk Canvas（或任何提供 `create_polygon` / `create_rectangle` 的对象）。
        x1, y1, x2, y2 (int | float): 矩形两角坐标；顺序颠倒时会自动归一化。
        r (int | float): 圆角半径（像素）；会被夹到不超过短边的一半。`r <= 0` 时退化为直角矩形。
        fill (str): 填充色（Tk 颜色名或 `#rrggbb`）。
        outline (str | None): 边框色；None 表示不画边框。
        width (int): 边框宽度（像素），仅在 `outline` 非 None 时有意义。

    返回:
        int: canvas item id（`create_polygon` 或 `create_rectangle` 的返回值）。
    """
    if x1 > x2:
        x1, x2 = x2, x1
    if y1 > y2:
        y1, y2 = y2, y1

    r = max(0, min(r, (x2 - x1) / 2.0, (y2 - y1) / 2.0))
    if r <= 0:
        return canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=outline, width=width)

    # 经典 Tk 圆角做法：用平滑多边形，在四个角各放一组重复点把转角"磨圆"
    points = [
        x1 + r, y1,
        x2 - r, y1,
        x2, y1,
        x2, y1 + r,
        x2, y2 - r,
        x2, y2,
        x2 - r, y2,
        x1 + r, y2,
        x1, y2,
        x1, y2 - r,
        x1, y1 + r,
        x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, fill=fill, outline=outline, width=width)


def shadow_rect(canvas, x1, y1, x2, y2, r, color, offset=(2, 2)):
    """画一个用于衬托主体的"投影"圆角矩形（只有填充，没有边框）。

    典型用法是先画投影、再画主体，让主体压在投影上面::

        shadow_rect(canvas, 10, 10, 110, 60, 8, '#cccccc', offset=(2, 2))
        rounded_rect(canvas, 10, 10, 110, 60, 8, '#ffffff')

    参数:
        canvas: Tk Canvas（或任何提供 `create_polygon` / `create_rectangle` 的对象）。
        x1, y1, x2, y2 (int | float): 主体矩形两角坐标；顺序颠倒时会自动归一化。
        r (int | float): 圆角半径（像素），语义同 `rounded_rect`。
        color (str): 投影颜色（Tk 颜色名或 `#rrggbb`）。
        offset (tuple[int, int]): 投影相对主体的偏移 `(dx, dy)`，默认 `(2, 2)`。

    返回:
        int: canvas item id。
    """
    dx, dy = offset
    return rounded_rect(canvas, x1 + dx, y1 + dy, x2 + dx, y2 + dy, r, color, outline=None)


def centered_text(canvas, cx, cy, text, font=None, fill='#000000', anchor='center'):
    """在 canvas 指定位置画一段文字。

    参数:
        canvas: Tk Canvas（或任何提供 `create_text` 的对象）。
        cx, cy (int | float): 文字定位点坐标；具体含义由 `anchor` 决定。
        text (str): 要显示的文字。
        font (tuple | str | None): Tk 字体（如 `('Microsoft YaHei', 10)`）；None 时使用 Tk 默认字体。
        fill (str): 文字颜色，默认 `'#000000'`。
        anchor (str): Tk 锚点，默认 `'center'`（即以 cx, cy 为中心）。

    返回:
        int: canvas item id。
    """
    kwargs = {'text': text, 'fill': fill, 'anchor': anchor}
    if font is not None:
        kwargs['font'] = font
    return canvas.create_text(cx, cy, **kwargs)
