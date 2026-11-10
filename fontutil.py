# -*- coding: utf-8 -*-
"""Android 端：字体路径修复 + 可读配色 + 登录入口（占位）"""
import os

CANDIDATES = []


def _candidates():
    if CANDIDATES:
        return CANDIDATES
    here = os.path.dirname(os.path.abspath(__file__))
    roots = [
        os.environ.get("ANDROID_APP_PATH") or "",
        os.environ.get("ANDROID_PRIVATE") or "",
        here,
        os.path.join(here, "assets"),
        os.getcwd(),
    ]
    for r in roots:
        if r:
            for name in ("sy-cjk.ttf", os.path.join("assets", "sy-cjk.ttf")):
                CANDIDATES.append(os.path.join(r, name))
    return CANDIDATES


def font_path():
    for p in _candidates():
        if os.path.exists(p):
            return p
    return ""
