# -*- coding: utf-8 -*-
"""按窗口标题抓取「该窗口自己」的渲染结果（PrintWindow PW_RENDERFULLCONTENT）。

用途：诊断「新手启动器看着是空的」——桌面上有其它窗口（资源管理器等）遮挡，
直接抓屏会把遮挡窗口的像素算进来，无法判断启动器自己画了什么。

用法: python _grab_window.py <标题子串> <输出png> [可选: 启动的命令行]
"""
import ctypes
import ctypes.wintypes as wt
import subprocess
import sys
import time

from PIL import Image

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
user32.SetProcessDPIAware()


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ('biSize', wt.DWORD), ('biWidth', wt.LONG), ('biHeight', wt.LONG),
        ('biPlanes', wt.WORD), ('biBitCount', wt.WORD), ('biCompression', wt.DWORD),
        ('biSizeImage', wt.DWORD), ('biXPelsPerMeter', wt.LONG),
        ('biYPelsPerMeter', wt.LONG), ('biClrUsed', wt.DWORD), ('biClrImportant', wt.DWORD),
    ]


def find_windows(substr):
    out = []

    def cb(hwnd, _l):
        if user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            if n:
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, buf, n + 1)
                if substr in buf.value:
                    out.append((hwnd, buf.value))
        return True

    user32.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)(cb), 0)
    return out


def grab(hwnd, path):
    r = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    w, h = r.right - r.left, r.bottom - r.top
    hdc = user32.GetWindowDC(hwnd)
    mdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    old = gdi32.SelectObject(mdc, bmp)
    ok = user32.PrintWindow(hwnd, mdc, 2)
    bi = BITMAPINFOHEADER()
    bi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bi.biWidth, bi.biHeight = w, -h
    bi.biPlanes, bi.biBitCount, bi.biCompression = 1, 32, 0
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bi), 0)
    img = Image.frombuffer('RGBA', (w, h), buf, 'raw', 'BGRA', 0, 1).convert('RGB')
    img.save(path)
    gdi32.SelectObject(mdc, old)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mdc)
    user32.ReleaseDC(hwnd, hdc)
    return ok, (r.left, r.top, r.right, r.bottom), img


COLORS = {
    '#2196f3': (33, 150, 243),
    '#4caf50': (76, 175, 80),
    '#ff9800': (255, 152, 0),
    '#8e24aa': (142, 36, 170),
}


def survey(img, label):
    px = img.load()
    W, H = img.size
    print('%s 尺寸 %dx%d' % (label, W, H))
    for name, rgb in COLORS.items():
        xs, ys = [], []
        for y in range(H):
            for x in range(W):
                p = px[x, y]
                if abs(p[0] - rgb[0]) <= 12 and abs(p[1] - rgb[1]) <= 12 and abs(p[2] - rgb[2]) <= 12:
                    xs.append(x)
                    ys.append(y)
        if xs:
            print('  %s 像素 %5d  包围盒 x=%d..%d y=%d..%d' %
                  (name, len(xs), min(xs), max(xs), min(ys), max(ys)))
        else:
            print('  %s 像素 0  **该颜色在窗口里完全不存在**' % name)


def main():
    title_sub, out = sys.argv[1], sys.argv[2]
    cmd = sys.argv[3:] or None
    proc = None
    if cmd:
        proc = subprocess.Popen(cmd, cwd='.')
        time.sleep(float(sys.argv[0] and 5))
    wins = find_windows(title_sub)
    print('匹配「%s」的可见窗口: %s' % (title_sub, [w[1] for w in wins]))
    if not wins:
        print('未找到窗口')
        return 1
    hwnd, title = wins[0]
    ok, rect, img = grab(hwnd, out)
    print('PrintWindow 返回 %s；矩形 %s；已存 %s' % (bool(ok), rect, out))
    survey(img, '【窗口自身渲染】')
    if proc:
        proc.terminate()
    return 0


if __name__ == '__main__':
    sys.exit(main())
