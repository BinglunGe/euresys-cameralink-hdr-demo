# -*- coding: utf-8 -*-
"""HDR / TIFF 输出验证 (无硬件依赖).

    python tests/test_hdr.py       # 独立运行
    pytest tests/test_hdr.py       # 若装了 pytest
"""
import inspect
import os
import sys
import tempfile

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))
import vc71_camera as C
import vc71_hdr as H

SAT = C.SETTINGS.sat


def _bps(im):
    v = im.tag_v2.get(258)
    return v[0] if isinstance(v, (tuple, list)) else v


def test_hdr_scale_is_full_size():
    assert C.SETTINGS.hdr_scale == 1.0, C.SETTINGS.hdr_scale


def test_write_tiff16_is_16bit_adobe_deflate():
    p = os.path.join(tempfile.gettempdir(), 'test_hdr_tiff.tiff')
    H.write_tiff16(p, np.linspace(0, 1, 200 * 300).reshape(200, 300).astype(np.float32))
    try:
        im = Image.open(p)
        assert _bps(im) == 16, _bps(im)
        assert im.tag_v2.get(259) == 8, 'not Adobe Deflate: %s' % im.tag_v2.get(259)
        a = np.array(im)
        assert a.dtype == np.uint16 and a.shape == (200, 300)
        assert a.min() == 0 and a.max() == 65535
    finally:
        os.remove(p)


def test_write_tiff16_clips_out_of_range():
    p = os.path.join(tempfile.gettempdir(), 'test_hdr_clip.tiff')
    H.write_tiff16(p, np.array([[-1.0, 0.5, 2.0]], np.float32))
    try:
        a = np.array(Image.open(p))
        assert a.min() == 0 and a.max() == 65535
    finally:
        os.remove(p)


def test_make_compare_downscales_full_size():
    big = np.zeros((7096, 10000), np.uint8)
    assert H.make_compare(big, big).shape[1] <= 2410


def test_make_compare_does_not_upscale_small():
    sm = np.zeros((600, 800), np.uint8)
    assert H.make_compare(sm, sm).shape[1] == 800 * 2 + 6


def test_merge_preserves_size():
    base = np.linspace(1, SAT, 200 * 150).reshape(150, 200)
    ts = [1e-3, 1e-2, 1e-1]
    i12 = [np.clip(base * t * 1000, 0, SAT).astype(np.uint16) for t in ts]
    i8 = [(x >> 4).astype(np.uint8) for x in i12]
    hdr, ld, E, le = H.merge(i12, i8, ts)
    assert hdr.shape[:2] == (150, 200) and E.shape == (150, 200)


def test_log_compress_cleans_nan_inf():
    lc = H.log_compress(np.array([[np.nan, 1.0], [0.5, np.inf]]))
    assert np.all(np.isfinite(lc)) and lc.min() >= 0 and lc.max() <= 1


def test_cli_and_gui_wire_write_tiff16():
    assert inspect.getsource(H).count('write_tiff16') >= 2
    import vc71_gui as G
    assert 'write_tiff16' in inspect.getsource(G.CameraThread._do_hdr)


def test_ev_bracket_step_and_range():
    seq = C.ev_bracket(100, 2000000, 2)              # 2 EV/档 = 4x
    assert seq[0] == 100 and len(seq) == 8 and seq[-1] == 1638400, seq
    assert len(C.ev_bracket(100, 2000000, 1)) == 15   # 1 EV/档
    assert C.SETTINGS.hdr_step_ev == 2.0
    assert C.SETTINGS.hdr_shutters[0] == 100


def test_acq_timeout_setting():
    import inspect
    assert C.SETTINGS.acq_timeout_ms == 10000, C.SETTINGS.acq_timeout_ms
    # 采集超时的字符串标识符是 'Timeout' (非参数名 AcqTimeout_ms)
    assert "'Timeout'" in inspect.getsource(C.configure_channel)


def test_to_negative():
    import numpy as np
    a8 = np.array([[0, 128, 255]], dtype=np.uint8)
    assert (C.to_negative(a8) == np.array([[255, 127, 0]], dtype=np.uint8)).all()
    a12 = np.array([[0, 2048, 4095]], dtype=np.uint16)
    assert (C.to_negative(a12) == np.array([[4095, 2047, 0]], dtype=np.uint16)).all()
    assert (C.to_negative(C.to_negative(a12)) == a12).all()   # 反相两次还原
    assert isinstance(C.SETTINGS.negative, bool)


def test_focus_peaking_marks_edges_only():
    import vc71_gui as G
    img = np.zeros((60, 80), dtype=np.uint8)
    img[:, 40:] = 200                                  # 竖直边界
    out = G.focus_peaking(img, coverage_pct=2.0)
    assert out.shape == (60, 80, 3) and out.dtype == np.uint8
    red = out[:, :, 2] == 255
    assert 0 < red.sum() < img.size * 0.2, '红色应少量且集中(%d)' % red.sum()
    cols = np.where(red.any(axis=0))[0]
    assert 34 <= cols.min() and cols.max() <= 46, '红色应只在边界附近: %s' % cols
    assert not out[red][:, 0].any() and not out[red][:, 1].any(), '峰值应纯红(亮背景上才可见)'
    # 灵敏度数值越大越宽松, 标红不会更少
    assert (G.focus_peaking(img, 10.0)[:, :, 2] == 255).sum() >= red.sum()


def test_focus_peaking_flat_image_stays_clean():
    import vc71_gui as G
    flat = np.full((40, 40), 128, dtype=np.uint8)      # 全平: 没有边
    assert (G.focus_peaking(flat, 3.0)[:, :, 2] == 255).sum() == 0


def test_focus_peaking_keeps_12bit_brightness():
    import vc71_gui as G
    img = np.full((20, 20), 4000, dtype=np.uint16)     # 12bit 亮场
    out = G.focus_peaking(img, 3.0)
    assert out[:, :, 0].max() > 200, '12bit 底图被压黑(应 >>4 而非 >>8): %d' % out[:, :, 0].max()


def test_magnify_quadrants_are_1to1_corners():
    import vc71_gui as G
    img = np.arange(100 * 200, dtype=np.uint8).reshape(100, 200)   # uint8 原样透过
    out = G.magnify_quadrants(img, 100, 60)                        # 每块 50x30
    ph, pw = 30, 50
    assert out.shape == (60, 100) and out.dtype == np.uint8
    # 四块 = 原图四角, 逐像素一致(1:1 无缩放)
    assert (out[:ph, :pw] == img[:ph, :pw]).all()
    assert (out[:ph, pw:] == img[:ph, -pw:]).all()
    assert (out[ph:, :pw] == img[-ph:, :pw]).all()
    assert (out[ph:, pw:] == img[-ph:, -pw:]).all()


def test_magnify_peaking_is_per_pane():
    """峰值必须逐块做: 四块内容不同造成的接缝不能被标红。"""
    import vc71_gui as G
    img = np.zeros((40, 60), dtype=np.uint8)
    img[:20, -30:] = 100      # 四块各自平坦, 但值不同 -> 拼起来有明显接缝
    img[-20:, :30] = 200
    img[-20:, -30:] = 50
    out = G.magnify_quadrants(img, 60, 40, lambda q: G.focus_peaking(q, 3.0))
    assert out.shape == (40, 60, 3) and out.dtype == np.uint8
    assert (out[:, :, 2] == 255).sum() == 0, '每块都平坦, 接缝不该被标红'


def test_draw_cross_marks_midlines():
    import vc71_gui as G
    img = np.zeros((10, 20), dtype=np.uint8)
    G.draw_cross(img)
    assert (img[4, :] == 255).all() and (img[:, 9] == 255).all()
    assert img[0, 0] == 0


def test_fit_never_upscales():
    import vc71_gui as G
    assert G.fit(np.zeros((20, 30), dtype=np.uint8), 100, 100).shape == (20, 30)
    assert G.fit(np.zeros((2000, 4000), dtype=np.uint16), 100, 100).shape == (50, 100)


def test_magnify_settings():
    assert isinstance(C.SETTINGS.magnify, bool)


def test_peaking_settings():
    import vc71_gui as G
    assert isinstance(C.SETTINGS.peaking, bool)
    assert 1 <= C.SETTINGS.peaking_coverage <= 10
    assert callable(G.focus_peaking)


if __name__ == '__main__':
    fns = [v for k, v in sorted(vars().items()) if k.startswith('test_') and callable(v)]
    fails = 0
    for fn in fns:
        try:
            fn()
            print('PASS  %s' % fn.__name__)
        except AssertionError as e:
            fails += 1
            print('FAIL  %s: %s' % (fn.__name__, e))
    print('\n%d/%d passed' % (len(fns) - fails, len(fns)))
    raise SystemExit(1 if fails else 0)
