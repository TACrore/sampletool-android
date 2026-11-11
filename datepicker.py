# -*- coding: utf-8 -*-
"""日期选择器（浅色弹层，与主界面风格一致）"""
import calendar
import datetime

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout

import dialog

BLUE = dialog.BLUE
GREY = dialog.GREY
INK = dialog.INK
MUTED = dialog.MUTED


class DatePicker(dialog.Sheet):
    def __init__(self, current="", on_pick=None, **kw):
        super().__init__("选择日期", height=0.74, **kw)
        self.on_pick = on_pick
        today = datetime.date.today()
        try:
            y, m, d = [int(x) for x in (current or "").split("-")[:3]]
        except Exception:
            y, m, d = today.year, today.month, today.day
        self.y, self.m = y, m

        head = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(6))
        head.add_widget(dialog.btn("‹", lambda: self._shift(-1), color=GREY,
                                   text_color=INK, size=20))
        self.title_lab = dialog.lab("", 15, INK, True, halign="center")
        head.add_widget(self.title_lab)
        head.add_widget(dialog.btn("›", lambda: self._shift(1), color=GREY,
                                   text_color=INK, size=20))
        self.body.add_widget(head)

        wk = GridLayout(cols=7, size_hint_y=None, height=dp(22))
        for n in ("一", "二", "三", "四", "五", "六", "日"):
            wk.add_widget(dialog.lab(n, 12, MUTED, halign="center"))
        self.body.add_widget(wk)

        self.grid = GridLayout(cols=7, spacing=dp(2))
        self.body.add_widget(self.grid)

        foot = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        foot.add_widget(dialog.btn("今天", self._today, color=dialog.GREEN))
        foot.add_widget(dialog.btn("清空", lambda: self._pick(""), color=GREY, text_color=INK))
        foot.add_widget(dialog.btn("取消", lambda: self.dismiss(), color=GREY, text_color=INK))
        self.body.add_widget(foot)
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
                self.grid.add_widget(dialog.lab(""))
                continue
            cur = datetime.date(self.y, self.m, day)
            is_today = (cur == today)
            b = dialog.btn(str(day), lambda dd=cur: self._pick(dd.strftime("%Y-%m-%d")),
                           color=BLUE if is_today else GREY,
                           text_color=(1, 1, 1, 1) if is_today else INK, height=34, size=13)
            self.grid.add_widget(b)
