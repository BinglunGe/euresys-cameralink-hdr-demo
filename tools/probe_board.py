# -*- coding: utf-8 -*-
"""MultiCam 驱动与 Camera Link 相机探测脚本"""
import sys as _s, os as _o
_s.path.insert(0, _o.path.join(_o.path.dirname(_o.path.abspath(__file__)), '..', 'src'))
import sys
from MultiCam import MC

def probe():
    print("=== 1. 打开 MultiCam 驱动 ===")
    try:
        MC.OpenDriver()
        print("   OpenDriver 成功")
    except Exception as e:
        print("   OpenDriver 失败:", e)
        return

    try:
        print("\n=== 2. 枚举采集卡 (Board) ===")
        try:
            boardCount = MC.GetParamInt(MC.CONFIGURATION, 'BoardCount')
        except Exception as e:
            print("   无法获取 BoardCount:", e)
            boardCount = 0
        print("   BoardCount =", boardCount)

        for i in range(boardCount):
            board = MC.BOARD + i
            try:
                btype = MC.GetParamStr(board, 'BoardType')
            except Exception as e:
                btype = '?'
            try:
                bid = MC.GetParamStr(board, 'BoardIdentifier')
            except Exception as e:
                bid = '?'
            try:
                state = MC.GetParamStr(board, 'State')
            except Exception:
                state = '?'
            print("   Board[%d]: Type=%s, Identifier=%s, State=%s" % (i, btype, bid, state))
    finally:
        print("\n=== 3. 关闭驱动 ===")
        try:
            MC.CloseDriver()
            print("   CloseDriver 成功")
        except Exception as e:
            print("   CloseDriver 失败:", e)

if __name__ == '__main__':
    probe()
