# -*- coding: utf-8 -*-
"""探测相机实际参数：连接器、Tap 配置、分辨率"""
import sys as _s, os as _o
_s.path.insert(0, _o.path.join(_o.path.dirname(_o.path.abspath(__file__)), '..', 'src'))
import sys
from MultiCam import MC

def probe():
    MC.OpenDriver()
    channel = MC.Create('CHANNEL')
    try:
        # 配置
        MC.SetParamInt(channel, 'DriverIndex', 0)
        MC.SetParamStr(channel, 'Connector', 'M')
        MC.SetParamStr(channel, 'CamFile', 'MyCameraLink_PxxSC')

        print("=== 通道配置后参数 ===")
        for p in ['DriverIndex', 'Connector', 'CamFile']:
            try:
                print("  %s = %s" % (p, MC.GetParamStr(channel, p)))
            except Exception as e:
                print("  %s 查询失败: %s" % (p, e))

        # 尝试激活通道
        try:
            MC.SetParamStr(channel, 'ChannelState', 'ACTIVE')
            print("\n  ChannelState = ACTIVE 成功")
        except Exception as e:
            print("\n  ChannelState ACTIVE 失败:", e)

        # 查询图像尺寸
        try:
            w = MC.GetParamInt(channel, 'ImageSizeX')
            h = MC.GetParamInt(channel, 'ImageSizeY')
            print("\n  ImageSize = %d x %d" % (w, h))
        except Exception as e:
            print("\n  ImageSize 查询失败:", e)

        # 查询 Tap 配置
        for p in ['TapConfiguration', 'TapGeometry', 'ColorFormat', 'ChannelsPerBoard']:
            try:
                print("  %s = %s" % (p, MC.GetParamStr(channel, p)))
            except Exception as e:
                print("  %s 查询失败: %s" % (p, e))

        # 查询板卡信息
        board = MC.BOARD + 0
        for p in ['BoardType', 'BoardIdentifier', 'DriverIndex']:
            try:
                print("  Board.%s = %s" % (p, MC.GetParamStr(board, p)))
            except Exception as e:
                print("  Board.%s 查询失败: %s" % (p, e))

        # 复位
        try:
            MC.SetParamStr(channel, 'ChannelState', 'IDLE')
        except Exception:
            pass
    finally:
        MC.Delete(channel)
        MC.CloseDriver()

if __name__ == '__main__':
    probe()
