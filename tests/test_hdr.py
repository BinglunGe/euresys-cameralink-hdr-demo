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
