# -*- coding: utf-8 -*-
"""串口控制命令行。

    python vc71_control.py --temp                  # 读温度
    python vc71_control.py --shutter 10000         # 设快门(微秒)
    python vc71_control.py --gain 31               # 设增益
    python vc71_control.py --offset 20             # 设补偿
    python vc71_control.py --roi 2496 2000         # 设 ROI 宽高
    python vc71_control.py --cmd gag               # 发任意命令
    python vc71_control.py --interactive           # 交互式终端

注意: 运行前须退出 MultiCamStudio / Vieworks 客户端(独占串口)。
"""
import argparse

from vc71_camera import CameraSerial, SETTINGS, format_shutter


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--temp', action='store_true', help='读相机温度')
    ap.add_argument('--shutter', type=int, help='设快门(微秒)')
    ap.add_argument('--gain', type=int, help='设增益(0-63)')
    ap.add_argument('--offset', type=int, help='设补偿(0-63)')
    ap.add_argument('--roi', type=int, nargs=2, metavar=('W', 'H'), help='设 ROI 宽高')
    ap.add_argument('--cmd', help='发送任意命令, 如 gag')
    ap.add_argument('--interactive', action='store_true', help='交互式终端')
    args = ap.parse_args()

    try:
        ser = CameraSerial().open()
    except Exception as e:
        print('打开串口失败(可能被 MultiCamStudio 占用): %s' % e)
        return
    try:
        if args.interactive:
            print('输入命令回车发送(如 gct / set 10000 / sag 31), exit 退出')
            while True:
                try:
                    c = input('> ').strip()
                except (EOFError, KeyboardInterrupt):
                    break
                if c.lower() in ('exit', 'quit'):
                    break
                if c:
                    print(ser.send(c))
        elif args.temp:
            print('温度: %s °C' % ser.get_temp())
        elif args.shutter is not None:
            print('快门 %s (%dus): %s' % (format_shutter(args.shutter),
                                          args.shutter, ser.set_shutter(args.shutter)))
        elif args.gain is not None:
            print('增益 %d: %s' % (args.gain, ser.set_gain(args.gain)))
        elif args.offset is not None:
            print('补偿 %d: %s' % (args.offset, ser.set_offset(args.offset)))
        elif args.roi:
            w, h = args.roi
            print('ROI %dx%d: %s' % (w, h, ser.set_roi(w, h)))
        elif args.cmd:
            print('%s -> %s' % (args.cmd, ser.send(args.cmd)))
        else:
            print('温度: %s °C' % ser.get_temp())
    finally:
        ser.close()


if __name__ == '__main__':
    main()
