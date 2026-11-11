# -*- coding: utf-8 -*-
"""Kivy 简易日期选择器（月历弹窗）"""
import calendar
import datetime

from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup

import fontutil

FONT = fontutil.font_path()
BLUE = (0.184, 0.435, 0.922, 1)
GREY = (0.945, 0.953, 0.969, 1)
INK = (0.122, 0.165, 0.227, 1)
MUTED = (0.42, 0.463, 0.525, 1)


def _btn(text, cb, color=GREY, tc=INK, h=36, size=13):
    b = Button(text=text, size_hint_y=None, height=dp(h), background_normal="",
               background_color=color, color=tc, font_size=sp(size),
               on_release=lambda *_: cb())
    if FONT:
        b.font_name = FONT
    return b


def _lab(text, size=13, color=INK, bold=False, halign="center"):
    w = Label(text=text, font_size=sp(size), color=color, bold=bold, halign=halign,
              valign="middle", size_hint_y=None, height=dp(22))
    w.bind(size=lambda x, *_: setattr(x, "text_size", (x.width, None)))
    if FONT:
        w.font_name = FONT
    return w


class DatePicker(Popup):
    """current: 'YYYY-MM-DD' 或空；on_pick(text)"""

    def __init__(self, current="", on_pick=None, **kw):
        super().__init__(title="选择日期", size_hint=(0.92, 0.72), **kw)
        if FONT:
            self.title_font = FONT
        self.on_pick = on_pick
        today = datetime.date.today()
        try:
            y, m, d = [int(x) for x in (current or "").split("-")[:3]]
        except Exception:
            y, m, d = today.year, today.month, today.day
        self.y, self.m = y, m

        root = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))
        head = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(6))
        head.add_widget(_btn("‹", lambda: self._shift(-1), size=18))
        self.title_lab = _lab("", 15, INK, True)
        head.add_widget(self.title_lab)
        head.add_widget(_btn("›", lambda: self._shift(1), size=18))
        root.add_widget(head)

        wk = GridLayout(cols=7, size_hint_y=None, height=dp(24))
        for n in ("一", "二", "三", "四", "五", "六", "日"):
            wk.add_widget(_lab(n, 12, MUTED))
        root.add_widget(wk)

        self.grid = GridLayout(cols=7, spacing=dp(2))
        root.add_widget(self.grid)

        foot = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        foot.add_widget(_btn("今天", self._today, color=(0.216, 0.698, 0.302, 1),
                             tc=(1, 1, 1, 1), h=40, size=14))
        foot.add_widget(_btn("清空", lambda: self._pick(""), h=40, size=14))
        foot.add_widget(_btn("取消", lambda: self.dismiss(), h=40, size=14))
        root.add_widget(foot)
        self.content = root
        self._render()

    def _shift(self, delta):
        m = self.m + delta
        y = self.y
        while m < 1:
            m += 12
            y -= 1
        while m > 12:
            m -= 12
            y += 1
        self.y, self.m = y, m
        self._render()

    def _today(self):
        self._pick(datetime.date.today().strftime("%Y-%m-%d"))

    def _pick(self, text):
        if self.on_pick:
            self.on_pick(text)
        self.dismiss()

    def _render(self):
        self.title_lab.text = "%d 年 %d 月" % (self.y, self.m)
        self.grid.clear_widgets()
        cal = calendar.Calendar(firstweekday=0)
        today = datetime.date.today()
        for day in cal.itermonthdays(self.y, self.m):
            if day == 0:
                self.grid.add_widget(_lab(""))
                continue
            cur = datetime.date(self.y, self.m, day)
            color = GREY
            tc = INK
            if cur == today:
                color = BLUE
                tc = (1, 1, 1, 1)
            b = _btn(str(day), lambda d=cur: self._pick(d.strftime("%Y-%m-%d")),
                     color=color, tc=tc, h=34, size=13)
            self.grid.add_widget(b)
