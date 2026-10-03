# -*- coding: utf-8 -*-
"""HDR 合成: Debevec / 线性加权合并 + 稳健显示。

GUI 与命令行共用。命令行:
    python vc71_hdr.py                       # 用 settings.xml 的默认曝光序列
    python vc71_hdr.py --shutters 100 1000 10000 100000 1000000
    python vc71_hdr.py --scale 1.0
"""
import os
import sys
import time
import argparse

import numpy as np
import cv2

from MultiCam import MC
from vc71_camera import (SETTINGS, W, H, OUTDIR, configure_channel, grab_frame,
                         CameraSerial, format_shutter)

SAT = SETTINGS.sat


# ---------------- 合成 ----------------
def merge_debevec(imgs8, times):
    t = np.array(times, dtype=np.float32)
    response = cv2.createCalibrateDebevec().process(imgs8, t)
    hdr = cv2.createMergeDebevec().process(imgs8, t, response)
    return hdr.astype(np.float32), response


def merge_linear(imgs12, times):
    """线性加权合并: E = Σ w·(I/t) / Σ w, 帽子权重 w=min(I, sat-I)。"""
    num = np.zeros_like(imgs12[0], dtype=np.float64)
    den = np.zeros_like(imgs12[0], dtype=np.float64)
    for I, t in zip(imgs12, times):
        I = I.astype(np.float64)
        w = np.minimum(I, SAT - I)
        num += w * (I / t)
        den += w
    return num / np.maximum(den, 1e-9)


def tonemap(hdr, method='reinhard'):
    hdr32 = hdr.astype(np.float32)
    hdr3 = cv2.merge([hdr32, hdr32, hdr32]) if hdr32.ndim == 2 else hdr32
    tm = {'mantiuk': cv2.createTonemapMantiuk,
          'reinhard': cv2.createTonemapReinhard,
          'drago': cv2.createTonemapDrago}[method]()
    ldr = tm.process(hdr3)
    if ldr.ndim == 3:
        ldr = ldr[:, :, 0]
    return np.clip(ldr, 0, 1)


def log_compress(E, lo_pct=1.0, hi_pct=99.0):
    """稳健归一化: 清洗 NaN/Inf -> 对数压缩 -> 百分位裁剪 -> [0,1]。"""
    x = np.nan_to_num(np.asarray(E, dtype=np.float64), nan=0.0, posinf=0.0, neginf=0.0)
    x = np.maximum(x, 0.0)
    logE = np.log1p(x)
    lo = float(np.percentile(logE, lo_pct))
    hi = float(np.percentile(logE, hi_pct))
    if hi <= lo:
        hi = lo + 1e-9
    return np.clip((logE - lo) / (hi - lo), 0, 1).astype(np.float32)


def db_range(x):
    mn, mx = float(np.nanmin(x)), float(np.nanmax(x))
    return 20 * np.log10(mx / max(mn, 1e-9))


def make_compare(img_a, img_b, label_a='Debevec', label_b='Linear'):
    a, b = img_a.copy(), img_b.copy()
    if a.ndim == 2:
        a = cv2.cvtColor(a, cv2.COLOR_GRAY2BGR)
        b = cv2.cvtColor(b, cv2.COLOR_GRAY2BGR)
    h, w = a.shape[:2]
    gap = 6
    body = np.hstack([a, np.full((h, gap, 3), 255, np.uint8), b])
    lab = np.full((34, w * 2 + gap, 3), 255, np.uint8)
    cv2.putText(lab, label_a, (12, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
    cv2.putText(lab, label_b, (w + gap + 12, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
    return np.vstack([lab, body])


def merge(imgs12, imgs8, times):
    """返回 (hdr, ldr_debevec, E, ldr_linear)。"""
    hdr, _ = merge_debevec(imgs8, times)
    E = merge_linear(imgs12, times)
    return hdr, log_compress(hdr), E, log_compress(E)


def filter_bracket(imgs12, imgs8, times, means):
    """剔除过度欠曝/过曝的档(污染 Debevec 校准)。返回过滤后的三元组。"""
    keep = [i for i, m in enumerate(means)
            if SETTINGS.hdr_skip_lo <= m <= SETTINGS.hdr_skip_hi]
    if 2 <= len(keep) < len(means):
        return ([imgs12[i] for i in keep], [imgs8[i] for i in keep],
                [times[i] for i in keep], len(means) - len(keep))
    return imgs12, imgs8, times, 0


# ---------------- 命令行 ----------------
def _capture(channel, ser, shutters, scale):
    dw, dh = int(W * scale), int(H * scale)
    imgs12, imgs8, times, means = [], [], [], []
    for i, us in enumerate(shutters):
        if ser:
            ser.set_shutter(us)
        grab_frame(channel, 25000)                 # 丢弃首帧(快门切换需一帧生效)
        frame = grab_frame(channel, 25000)
        mean = float(frame.mean())
        means.append(mean)
        f = cv2.resize(frame, (dw, dh), interpolation=cv2.INTER_AREA) if scale != 1.0 else frame
        imgs12.append(f)
        imgs8.append((f >> 4).astype(np.uint8))
        times.append(us / 1e6)
        print('  [%d/%d] %-8s (%dus) 均值 %.1f' % (
            i + 1, len(shutters), format_shutter(us), us, mean))
    imgs12, imgs8, times, dropped = filter_bracket(imgs12, imgs8, times, means)
    if dropped:
        print('  已剔除 %d 个极端曝光档' % dropped)
    return imgs12, imgs8, times


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--shutters', type=int, nargs='+', default=SETTINGS.hdr_shutters)
    ap.add_argument('--scale', type=float, default=SETTINGS.hdr_scale)
    ap.add_argument('--outdir', default=OUTDIR)
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    print('曝光序列:', [format_shutter(u) for u in args.shutters])
    ser = CameraSerial().open()
    MC.OpenDriver()
    channel = MC.Create('CHANNEL')
    try:
        configure_channel(channel)
        imgs12, imgs8, times = _capture(channel, ser, args.shutters, args.scale)
    finally:
        MC.Delete(channel)
        MC.CloseDriver()
        ser.close()

    print('合成中...')
    hdr, ldr_d, E, ldr_l = merge(imgs12, imgs8, times)
    ts = time.strftime('%Y%m%d-%H%M%S')
    cv2.imwrite(os.path.join(args.outdir, 'hdr_%s.hdr' % ts), hdr)
    cv2.imwrite(os.path.join(args.outdir, 'hdr_%s_tonemapped.png' % ts), (ldr_d * 255).astype(np.uint8))
    cmp = make_compare((ldr_d * 255).astype(np.uint8), (ldr_l * 255).astype(np.uint8))
    cv2.imwrite(os.path.join(args.outdir, 'hdr_%s_compare.png' % ts), cmp)
    print('Debevec DR %.1f dB | Linear DR %.1f dB' % (db_range(hdr), db_range(E)))
    print('已保存到', args.outdir)


if __name__ == '__main__':
    main()
