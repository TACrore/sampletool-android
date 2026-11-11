# -*- coding: utf-8 -*-
"""统一的浅色弹层（替代默认深色 Popup），与主界面同一套配色。"""
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView

import fontutil

FONT = fontutil.font_path()
BLUE = (0.184, 0.435, 0.922, 1)
BLUE_D = (0.114, 0.290, 0.663, 1)
CARD = (1, 1, 1, 1)
INK = (0.122, 0.165, 0.227, 1)
MUTED = (0.42, 0.463, 0.525, 1)
GREY = (0.945, 0.953, 0.969, 1)
GREEN = (0.216, 0.698, 0.302, 1)
RED = (0.788, 0.165, 0.165, 1)


def _font(w):
    if FONT:
        w.font_name = FONT
    return w


def lab(text="", size=14, color=INK, bold=False, halign="left", height=None):
    h = height if height is not None else sp(size) * 1.7
    w = Label(text=text, font_size=sp(size), color=color, bold=bold, halign=halign,
              valign="middle", size_hint_y=None, height=h)
    w.bind(size=lambda x, *_: setattr(x, "text_size", (x.width, None)))
    return _font(w)


def btn(text, cb, color=BLUE, height=44, size=14, text_color=(1, 1, 1, 1)):
    b = Button(text=text, size_hint_y=None, height=dp(height), background_normal="",
               background_color=color, font_size=sp(size), color=text_color,
               on_release=lambda *_: cb())
    return _font(b)


class Sheet(ModalView):
    """白色卡片 + 蓝色标题条的弹层。"""

    def __init__(self, title, width=0.92, height=0.6, **kw):
        super().__init__(size_hint=(width, height), background_color=(0, 0, 0, 0.45), **kw)
        self.card = BoxLayout(orientation="vertical", padding=0, spacing=0)
        with self.card.canvas.before:
            self._bc = Color(rgba=CARD)
            self._rect = RoundedRectangle(radius=[dp(10)])
        self.card.bind(pos=self._sync, size=self._sync)

        head = BoxLayout(size_hint_y=None, height=dp(46), padding=[dp(14), 0])
        with head.canvas.before:
            self._hc = Color(rgba=BLUE)
            self._hrect = RoundedRectangle(radius=[dp(10)])
        head.bind(pos=self._hsync, size=self._hsync)
        head.add_widget(lab(title, 16, (1, 1, 1, 1), True))
        self.card.add_widget(head)

        self.body = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
        self.card.add_widget(self.body)
        self.add_widget(self.card)

    def _sync(self, *a):
        self._rect.pos = self.card.pos
        self._rect.size = self.card.size

    def _hsync(self, *a):
        self._hrect.pos = (self.card.x, self.card.top - dp(46))
        self._hrect.size = (self.card.width, dp(46))


def info(text, title="提示", on_close=None):
    sh = Sheet(title, height=0.36)

    def close(*_):
        sh.dismiss()
        if on_close:
            on_close()

    sh.body.add_widget(lab(text, 14))
    foot = BoxLayout(size_hint_y=None, height=dp(46))
    foot.add_widget(btn("知道了", close, color=BLUE))
    sh.body.add_widget(foot)
    sh.open()
    return sh


def confirm(text, on_yes, title="确认", yes_text="确定"):
    sh = Sheet(title, height=0.4)

    def yes(*_):
        sh.dismiss()
        on_yes()

    sh.body.add_widget(lab(text, 14))
    foot = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
    foot.add_widget(btn("取消", lambda *_: sh.dismiss(), color=GREY, text_color=INK))
    foot.add_widget(btn(yes_text, yes, color=GREEN))
    sh.body.add_widget(foot)
    sh.open()
    return sh
