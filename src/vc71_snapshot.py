# -*- coding: utf-8 -*-
"""抓单帧 -> 16-bit PNG + 8-bit 预览。"""
import os
import time
import argparse

import numpy as np
import cv2

from MultiCam import MC
from vc71_camera import (SETTINGS, configure_channel, grab_frame,
                         CameraSerial, format_shutter)

OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'output')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--shutter', type=int, default=10000, help='快门(微秒)')
    ap.add_argument('--outdir', default=OUTDIR)
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

    ts = time.strftime('%Y%m%d-%H%M%S')
    p16 = os.path.join(args.outdir, 'snap_%s_16bit.png' % ts)
    p8 = os.path.join(args.outdir, 'snap_%s_preview8.png' % ts)
    cv2.imwrite(p16, frame)
    cv2.imwrite(p8, (frame >> 4).astype(np.uint8))
    print('快门 %s, 尺寸 %dx%d, 均值 %.1f' % (
        format_shutter(args.shutter), frame.shape[1], frame.shape[0], frame.mean()))
    print('已保存:', p16)
    print('已保存:', p8)


if __name__ == '__main__':
    main()
