# -*- coding: utf-8 -*-
"""抓单帧 -> 16-bit PNG + 8-bit 预览。"""
import os
import time
import argparse

import numpy as np
import cv2

from MultiCam import MC
from vc71_camera import (SETTINGS, OUTDIR, configure_channel, grab_frame,
                         CameraSerial, format_shutter, to_negative)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--shutter', type=int, default=10000, help='快门(微秒)')
    ap.add_argument('--outdir', default=OUTDIR)
    ap.add_argument('--negative', action='store_true',
                    help='负片模式: 软件反相(满量程-v), 不走硬件 LUT')
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    ser = CameraSerial().open()
    try:
        ser.set_shutter(args.shutter)
    except Exception as e:
        print('串口不可用(%s), 用当前快门' % e)

    MC.OpenDriver()
    ch = MC.Create('CHANNEL')
    try:
        configure_channel(ch)
        grab_frame(ch, 25000)      # 丢弃(快门切换需一帧生效)
        frame = grab_frame(ch, 25000)
    finally:
        MC.Delete(ch)
        MC.CloseDriver()
        ser.close()

    if args.negative:
        frame = to_negative(frame)     # 12-bit 域反相: 4095-v

    tag = 'neg_' if args.negative else ''
    ts = time.strftime('%Y%m%d-%H%M%S')
    p16 = os.path.join(args.outdir, 'snap_%s%s_16bit.png' % (tag, ts))
    p8 = os.path.join(args.outdir, 'snap_%s%s_preview8.png' % (tag, ts))
    cv2.imwrite(p16, frame)
    cv2.imwrite(p8, (frame >> 4).astype(np.uint8))
    print('快门 %s%s, 尺寸 %dx%d, 均值 %.1f' % (
        format_shutter(args.shutter), ' (负片)' if args.negative else '',
        frame.shape[1], frame.shape[0], frame.mean()))
    print('已保存:', p16)
    print('已保存:', p8)


if __name__ == '__main__':
    main()
