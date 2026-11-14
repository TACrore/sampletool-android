# -*- coding: utf-8 -*-
"""样品查询管理工具 Android 版（Kivy）— 界面按 Windows 版风格重做

风格：蓝色顶栏 / 白卡片 / 灰底；登记列表两行：图号+规格，日期+客户+数量+担当。
"""
import datetime
import os
import sys
import threading
import webbrowser

import auth
import data
import datepicker
import dialog
import fontutil
from kivy.app import App
from kivy.base import ExceptionHandler, ExceptionManager
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import Screen, ScreenManager, SlideTransition
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

APP_VERSION = "1.3.9"
try:
    _base = (os.path.dirname(sys.executable) if getattr(sys, "frozen", False)
             else os.path.dirname(os.path.abspath(__file__)))
    _vo = os.path.join(_base, "version_override.txt")
    if os.path.exists(_vo):
        APP_VERSION = open(_vo, encoding="utf-8").read().strip() or APP_VERSION
except Exception:
    pass
FONT = fontutil.font_path()

BLUE = (0.184, 0.435, 0.922, 1)
BLUE_D = (0.114, 0.290, 0.663, 1)
BG = (0.961, 0.969, 0.984, 1)
CARD = (1, 1, 1, 1)
INK = (0.122, 0.165, 0.227, 1)
MUTED = (0.420, 0.463, 0.525, 1)
GREEN = (0.216, 0.698, 0.302, 1)
RED = (0.788, 0.165, 0.165, 1)
GREY = (0.945, 0.953, 0.969, 1)


def font(w):
    if FONT:
        w.font_name = FONT
    return w


def lab(text="", size=14, color=INK, bold=False, height=None, halign="left"):
    h = height if height is not None else sp(size) * 1.6
    w = Label(text=text, font_size=sp(size), color=color, bold=bold, halign=halign,
              valign="middle", size_hint_y=None, height=h, shorten=True, shorten_from="right")
    w.bind(size=lambda x, *_: setattr(x, "text_size", (x.width, None)))
    return font(w)


def btn(text, cb, color=BLUE, height=44, size=14, text_color=(1, 1, 1, 1)):
    b = Button(text=text, size_hint_y=None, height=dp(height), background_normal="",
               background_color=color, font_size=sp(size), color=text_color,
               on_release=lambda *_: cb())
    return font(b)


def flat_btn(text, cb, color=GREY, text_color=INK, height=38, size=13):
    return btn(text, cb, color=color, height=height, size=size, text_color=text_color)


def card(padding=10, spacing=4, horizontal=False):
    """白色卡片容器（带浅色描边）"""
    class Card(BoxLayout):
        def __init__(self, **kw):
            super().__init__(**kw)
            with self.canvas.before:
                from kivy.graphics import Color, RoundedRectangle
                self._c = Color(rgba=CARD)
                self._r = RoundedRectangle(radius=[dp(6)])
            self.bind(pos=self._sync, size=self._sync)

        def _sync(self, *a):
            self._r.pos = self.pos
            self._r.size = self.size

    c = Card(orientation="horizontal" if horizontal else "vertical",
             size_hint_y=None, padding=[dp(padding)] * 2, spacing=dp(spacing))
    return c


def field(text="", size=13, color=INK, bold=False):
    return lab(text, size=size, color=color, bold=bold, height=sp(size) * 1.9)


def toast(msg, title="提示"):
    dialog.info(msg, title)


def bg(work, done):
    def run():
        try:
            res = work()
            Clock.schedule_once(lambda *_: done(res, None), 0)
        except BaseException as e:  # noqa: BLE001
            import traceback as _tb
            data.log_crash("bg", _tb.format_exc())
            Clock.schedule_once(lambda *_: done(None, str(e)[:200]), 0)
    threading.Thread(target=run, daemon=True).start()


class _KeepAlive(ExceptionHandler):
    def handle_exception(self, inst):
        import traceback as _tb
        data.log_crash("uncaught", _tb.format_exc())
        return ExceptionManager.PASS


ExceptionManager.add_handler(_KeepAlive())


class Header(BoxLayout):
    """蓝色顶栏：标题 + 账号"""

    def __init__(self, title, right="", **kw):
        super().__init__(size_hint_y=None, height=dp(56), padding=[dp(14), 0],
                         spacing=dp(8), **kw)
        from kivy.graphics import Color, Rectangle
        with self.canvas.before:
            self._c = Color(rgba=BLUE)
            self._r = Rectangle()
        self.bind(pos=self._sync, size=self._sync)
        self.add_widget(lab(title, 18, (1, 1, 1, 1), True))
        self.right_lab = lab(right, 12, (0.85, 0.90, 0.98, 1), halign="right")
        self.add_widget(self.right_lab)

    def _sync(self, *a):
        self._r.pos = self.pos
        self._r.size = self.size


class TabBar(BoxLayout):
    def __init__(self, tabs, on_pick, **kw):
        super().__init__(size_hint_y=None, height=dp(44), spacing=0, **kw)
        self.on_pick = on_pick
        self.buttons = {}
        self.active = ""
        for name in tabs:
            b = Button(text=name, font_size=sp(14), background_normal="",
                       background_color=CARD, color=MUTED, size_hint_y=None, height=dp(44),
                       on_release=lambda *_, n=name: self.on_pick(n))
            font(b)
            self.buttons[name] = b
            self.add_widget(b)
        self.set_active(tabs[0])

    def set_active(self, name):
        self.active = name
        for n, b in self.buttons.items():
            b.background_color = GREY if n == name else CARD
            b.color = BLUE_D if n == name else MUTED
            b.bold = (n == name)




def install_apk(path):
    """先走 FileProvider，失败则关掉 StrictMode 用 file:// 兜底。"""
    from jnius import autoclass, cast
    Intent = autoclass("android.content.Intent")
    File = autoclass("java.io.File")
    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    activity = PythonActivity.mActivity
    try:
        Uri = autoclass("android.net.Uri")
        FileProvider = autoclass("androidx.core.content.FileProvider")
        uri = FileProvider.getUriForFile(activity.getPackageName() + ".fileprovider",
                                         File(path))
        intent = Intent(Intent.ACTION_VIEW)
        intent.setDataAndType(cast("android.net.Uri", uri),
                              "application/vnd.android.package-archive")
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        activity.startActivity(intent)
        return True
    except Exception:
        pass
    try:
        StrictMode = autoclass("android.os.StrictMode")
        builder = StrictMode.VmPolicy.Builder()
        StrictMode.setVmPolicy(builder.build())
        Uri = autoclass("android.net.Uri")
        uri = Uri.fromFile(File(path))
        intent = Intent(Intent.ACTION_VIEW)
        intent.setDataAndType(uri, "application/vnd.android.package-archive")
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        activity.startActivity(intent)
        return True
    except Exception:
        return False


def make_splash(title):
    """品牌蓝开屏：加载期间盖住默认灰底"""
    from kivy.graphics import Color, Rectangle
    from kivy.uix.floatlayout import FloatLayout as _FL
    fl = _FL()
    with fl.canvas.before:
        Color(*BLUE)
        rect = Rectangle(pos=fl.pos, size=fl.size)
    fl.bind(pos=lambda *_: setattr(rect, "pos", fl.pos),
            size=lambda *_: setattr(rect, "size", fl.size))
    box = BoxLayout(orientation="vertical", padding=dp(28), spacing=dp(10))
    box.add_widget(Widget())
    box.add_widget(lab(title, 24, (1, 1, 1, 1), True))
    box.add_widget(lab("正在加载…", 14, (1, 1, 1, 0.85)))
    box.add_widget(Widget())
    fl.add_widget(box)
    return fl


class RootApp(App):
    def build(self):
        Window.clearcolor = BLUE          # 启动先品牌蓝，别露灰底
        self.title = "样品查询管理工具"
        sm = ScreenManager()              # 首屏不放动画
        sm.add_widget(LoginScreen(name="login"))
        sm.add_widget(HomeScreen(name="home"))
        sm.add_widget(SampleScreen(name="samples"))
        sm.add_widget(DetailScreen(name="detail"))
        sm.add_widget(EditScreen(name="edit"))
        sm.add_widget(StockScreen(name="stock"))
        sm.add_widget(NewScreen(name="new"))
        sm.current = "home" if data._load_token().get("refresh_token") else "login"
        sm.transition = SlideTransition(duration=0.12)
        root = BoxLayout()
        root.add_widget(sm)
        splash = make_splash("样品查询管理工具")
        root.add_widget(splash)
        Clock.schedule_once(lambda *_: setattr(Window, "clearcolor", BG), 0.4)
        Clock.schedule_once(lambda *_: (root.remove_widget(splash)
                                        if splash.parent else None), 1.2)
        return root


class LoginScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        root = BoxLayout(orientation="vertical")
        root.add_widget(Header("样品查询管理工具", "V" + APP_VERSION))
        body = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(10))
        card1 = card(padding=14, spacing=8)
        card1.add_widget(lab("飞书账号登录", 16, INK, True))
        card1.add_widget(lab("点下面「打开授权页」，在飞书里点同意。浏览器若提示 localhost 打不开属正常，"
                             "程序会自动收到授权码。", 12, MUTED))
        card1.height = dp(112)
        body.add_widget(card1)
        self.url = TextInput(text="", multiline=False, size_hint_y=None, height=dp(38),
                             font_size=sp(11), padding=[dp(8), dp(10)])
        font(self.url)
        self.url.text = auth.auth_url()
        self.url.readonly = True
        body.add_widget(self.url)
        body.add_widget(btn("打开授权页", self.open_url, height=46, size=15))
        self.code = TextInput(hint_text="或粘贴回调网址 / code", multiline=False,
                              size_hint_y=None, height=dp(40), font_size=sp(13),
                              padding=[dp(8), dp(10)])
        font(self.code)
        body.add_widget(self.code)
        body.add_widget(btn("登录", self.do_login, color=GREEN, height=46, size=15))
        self.tip = lab("", 12, MUTED)
        body.add_widget(self.tip)
        body.add_widget(Widget())
        root.add_widget(body)
        self.add_widget(root)

    def _auto_code(self, code):
        if not code:
            return
        self.code.text = code
        self.tip.text = "已自动收到授权码，正在登录..."
        self.do_login()

    def open_url(self):
        try:
            auth.start_callback(lambda c: Clock.schedule_once(lambda *_: self._auto_code(c), 0))
        except Exception:
            pass
        try:
            webbrowser.open(auth.auth_url())
        except Exception:
            pass
        self.tip.text = "已打开授权页；同意后自动登录（收不到就粘贴回调地址）"

    def do_login(self):
        self.tip.text = "登录中..."

        def done(_res, err):
            if err:
                self.tip.text = "失败：" + err
                return
            try:
                auth.stop_callback()
            except Exception:
                pass
            self.manager.current = "home"

        bg(lambda: auth.exchange_code(self.code.text, data), done)


class HomeScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        root = BoxLayout(orientation="vertical")
        self.header = Header("样品查询管理工具", "V" + APP_VERSION)
        root.add_widget(self.header)
        body = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(12))
        self.who_card = card(padding=14, spacing=4)
        self.who = lab("", 16, INK, True)
        self.who_sub = lab("", 12, MUTED)
        self.who_card.add_widget(self.who)
        self.who_card.add_widget(self.who_sub)
        self.who_card.height = dp(72)
        body.add_widget(self.who_card)
        body.add_widget(btn("样品登记", lambda: self.go("samples"), height=54, size=17))
        body.add_widget(btn("库存查询", lambda: self.go("stock"), height=54, size=17))
        body.add_widget(flat_btn("检查更新", self.check_update, height=42))
        body.add_widget(Widget())
        body.add_widget(btn("退出登录", self.logout, color=RED, height=44))
        root.add_widget(body)
        self.add_widget(root)

    def on_pre_enter(self, *_):
        t = data._load_token()
        self.who.text = "账号：" + (t.get("name") or "已登录")
        self.who_sub.text = "手机端 V%s ｜ 与电脑端数据实时同步" % APP_VERSION

    def go(self, name):
        self.manager.current = name

    def logout(self):
        data._save_token({})
        self.manager.current = "login"

    def check_update(self):
        def work():
            return data.latest_release("android")

        def done(res, err):
            if err:
                toast("检查失败：" + err)
                return
            if not res or not res.get("version"):
                toast("已是最新版本 V%s" % APP_VERSION, "检查更新")
                return
            latest = res["version"]
            if data.ver_tuple(latest) <= data.ver_tuple(APP_VERSION):
                toast("已是最新版本 V%s" % APP_VERSION, "检查更新")
                return
            dialog.confirm("发现新版本 V%s（当前 V%s）\n下载并安装？" % (latest, APP_VERSION),
                           lambda: self._start_update(latest, res), "检查更新", "下载安装")

        bg(work, done)

    def _start_update(self, latest, res):
        sh = dialog.Sheet("更新 V%s" % latest, height=0.5)
        info = dialog.lab("准备下载...", 13, dialog.INK)
        sh.body.add_widget(info)
        sh.body.add_widget(dialog.lab("", 4, dialog.MUTED, height=dp(6)))
        sh.body.add_widget(dialog.btn("关闭", lambda *_: sh.dismiss(), color=dialog.GREY,
                                      text_color=dialog.INK, height=42))
        sh.open()

        def set_text(txt, color=dialog.INK):
            def _u(*_):
                info.text = txt
                info.color = color
            Clock.schedule_once(_u, 0)

        def prog(nbytes):
            set_text("下载中... %.1f MB" % (nbytes / 1048576.0))

        def dl():
            out = os.path.join(data._data_dir(), "update-%s.apk" % latest)
            data.download_release(res["file_token"], out, on_progress=prog)
            return out

        def after_dl(path, e2):
            if e2:
                set_text("下载失败：" + e2, dialog.RED)
                _write_result(latest, "下载失败：" + e2)
                return
            mb = os.path.getsize(path) / 1048576.0
            set_text("下载完成 %.1f MB，校验中..." % mb)
            want = (res.get("sha256") or "").lower()
            try:
                import hashlib
                h = hashlib.sha256()
                with open(path, "rb") as f:
                    for chunk in iter(lambda: f.read(1 << 20), b""):
                        h.update(chunk)
                got = h.hexdigest()
            except Exception as e:
                set_text("校验异常：" + str(e)[:60], dialog.RED)
                return
            if want and got != want:
                set_text("SHA256 不一致，已中止（请重试）", dialog.RED)
                _write_result(latest, "SHA256 不一致")
                return
            set_text("SHA256 校验通过 %.1f MB\n正在打开安装器..." % mb)

            def inst():
                return install_apk(path)

            def after_inst(ok, e3):
                if ok:
                    set_text("已调起系统安装器\n装完版本会变成 V%s\n安装包：%s" % (latest, path))
                    _write_result(latest, "已调起安装器")
                else:
                    set_text("本机无法直接安装（Windows 属正常）\n安装包：%s" % path)
                    _write_result(latest, "已下载，需手动安装")

            bg(inst, after_inst)

        bg(dl, after_dl)

class SampleRow(BoxLayout):
    """一条登记记录（白卡片，两行信息）"""

    def __init__(self, it, on_pick, **kw):
        super().__init__(orientation="vertical", size_hint_y=None, height=dp(62),
                         padding=[dp(12), dp(6)], spacing=dp(2), **kw)
        from kivy.graphics import Color, Line, RoundedRectangle
        with self.canvas.before:
            self._bg = Color(rgba=CARD)
            self._rect = RoundedRectangle(radius=[dp(6)])
            self._line = Color(rgba=(0.88, 0.90, 0.94, 1))
        self.bind(pos=self._sync, size=self._sync)
        line1 = BoxLayout(size_hint_y=None, height=dp(24))
        line1.add_widget(lab(it["fig"], 15, INK, True))
        line1.add_widget(lab(it["spec"], 12, MUTED, halign="right"))
        line2 = BoxLayout(size_hint_y=None, height=dp(20))
        sub = " ｜ ".join(x for x in (it.get("date") or "", it.get("cust") or "",
                                      ("数量 " + it["qty"]) if it.get("qty") else "",
                                      it.get("owner") or "") if x)
        line2.add_widget(lab(sub, 12, MUTED))
        self.add_widget(line1)
        self.add_widget(line2)
        self.bind(on_touch_down=self._tap)
        self._on_pick = on_pick
        self._moved = False

    def _sync(self, *a):
        self._rect.pos = self.pos
        self._rect.size = self.size

    def _tap(self, w, touch):
        if self.collide_point(*touch.pos):
            self._on_pick()
            return True
        return False


class SampleScreen(Screen):
    PAGE = 200

    def __init__(self, **kw):
        super().__init__(**kw)
        self.items = []
        self.shown = 0
        self._hits = []
        root = BoxLayout(orientation="vertical")
        root.add_widget(Header("样品登记", ""))
        bar = BoxLayout(size_hint_y=None, height=dp(48), padding=[dp(8), dp(6)], spacing=dp(6))
        bar.add_widget(flat_btn("←", lambda: setattr(self.manager, "current", "home"),
                                height=36, size=16))
        self.kw = TextInput(hint_text="图号 / 客户 / 规格 / 担当", multiline=False,
                            size_hint_y=None, height=dp(36), font_size=sp(13),
                            padding=[dp(8), dp(9)])
        font(self.kw)
        self.kw.bind(on_text_validate=lambda *_: self.render())
        bar.add_widget(self.kw)
        bar.add_widget(flat_btn("搜索", self.render, color=BLUE, text_color=(1, 1, 1, 1), height=36))
        root.add_widget(bar)
        bar2 = BoxLayout(size_hint_y=None, height=dp(40), padding=[dp(8), 0], spacing=dp(6))
        bar2.add_widget(flat_btn("刷新", self.reload, color=GREEN, text_color=(1, 1, 1, 1), height=34))
        bar2.add_widget(flat_btn("新建登记", lambda: setattr(self.manager, "current", "new"),
                                 color=(0.90, 0.55, 0.15, 1), text_color=(1, 1, 1, 1), height=34))
        self.count = lab("", 12, MUTED, halign="right")
        bar2.add_widget(self.count)
        root.add_widget(bar2)
        self.scroll = ScrollView(bar_width=dp(3))
        self.list = GridLayout(cols=1, spacing=dp(6), size_hint_y=None, padding=[dp(8), dp(6)])
        self.list.bind(minimum_height=self.list.setter("height"))
        self.scroll.add_widget(self.list)
        root.add_widget(self.scroll)
        self.add_widget(root)

    def on_pre_enter(self, *_):
        if not self.items:
            self.reload()

    def reload(self):
        self.count.text = "加载中..."
        self.list.clear_widgets()
        self.list.add_widget(lab("正在读取飞书表格...", 13, MUTED))

        def done(res, err):
            if err:
                self.count.text = "失败"
                self.list.clear_widgets()
                self.list.add_widget(lab("读取失败：" + err, 13, RED))
                return
            self.items = res or []
            self.render()

        bg(lambda: data.load_samples(), done)
        return True

    def render(self):
        hits = data.search_samples(self.items, self.kw.text)
        hits.sort(key=lambda x: (x.get("date") or "", x.get("row") or 0), reverse=True)
        self._hits = hits
        self.shown = 0
        self.count.text = "%d 条" % len(hits)
        self.list.clear_widgets()
        if not hits:
            self.list.add_widget(lab("没有匹配记录", 13, MUTED))
            return
        self.load_more()

    def load_more(self):
        try:
            self.list.remove_widget(self._more_btn)
        except Exception:
            pass
        chunk = self._hits[self.shown:self.shown + self.PAGE]
        self.shown += len(chunk)
        for it in chunk:
            self.list.add_widget(SampleRow(it, lambda i=it: self.open_detail(i)))
        if self.shown < len(self._hits):
            self._more_btn = flat_btn("加载更多（%d/%d）" % (self.shown, len(self._hits)),
                                      self.load_more, height=40)
            self.list.add_widget(self._more_btn)

    def open_detail(self, it):
        self.manager.get_screen("detail").show(it)
        self.manager.current = "detail"


class DetailScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.item = None
        self._st = None
        root = BoxLayout(orientation="vertical")
        self.header = Header("", "")
        root.add_widget(self.header)
        bar = BoxLayout(size_hint_y=None, height=dp(46), padding=[dp(8), dp(6)], spacing=dp(6))
        bar.add_widget(flat_btn("←", lambda: setattr(self.manager, "current", "samples"),
                                height=34, size=16))
        self.title = lab("", 16, INK, True)
        bar.add_widget(self.title)
        bar.add_widget(flat_btn("编辑", self.open_edit, color=(0.90, 0.55, 0.15, 1),
                                text_color=(1, 1, 1, 1), height=34))
        bar.add_widget(flat_btn("全部完成", self.do_all_done, color=GREEN,
                                text_color=(1, 1, 1, 1), height=34))
        root.add_widget(bar)
        self.info_card = card(padding=12, spacing=3)
        self.info = lab("", 12, MUTED, height=dp(52))
        self.info_card.add_widget(self.info)
        self.info_card.height = dp(74)
        self.info_card.size_hint_y = None
        root.add_widget(self.info_card)
        self.step_hint = lab("点格子切换完成（绿=已完成，写回飞书）", 12, MUTED)
        root.add_widget(self.step_hint)
        self.scroll = ScrollView(bar_width=dp(3))
        self.grid = GridLayout(cols=4, spacing=dp(6), size_hint_y=None, padding=[dp(8), dp(6)])
        self.grid.bind(minimum_height=self.grid.setter("height"))
        self.scroll.add_widget(self.grid)
        root.add_widget(self.scroll)
        self.add_widget(root)

    def show(self, it):
        self.item = it
        self.header.right_lab.text = it["fig"]
        self.title.text = it["fig"]
        self.info.text = "%s\n客户 %s ｜ 数量 %s ｜ 担当 %s ｜ 要求完成 %s%s" % (
            it["spec"], it["cust"] or "-", it["qty"] or "-", it["owner"] or "-",
            it["due"] or "-", ("\n" + it["special"]) if it.get("special") else "")
        self.load()

    def load(self):
        self.grid.clear_widgets()
        self.grid.add_widget(lab("读取工序进度...", 13, MUTED))
        fig = self.item["fig"]

        def done(res, err):
            self.grid.clear_widgets()
            if err:
                self.grid.add_widget(lab("失败：" + err, 13, RED))
                return
            self._st = res
            for i in range(20):
                name = (res["names"][i] or "").strip() or ("工序%d" % (i + 1))
                on = bool(res["done"][i])
                b = Button(text=("√ " + name) if on else name, size_hint_y=None,
                           height=dp(56), font_size=sp(12), background_normal="",
                           background_color=GREEN if on else GREY,
                           color=(1, 1, 1, 1) if on else INK)
                font(b)
                b.bind(on_release=lambda *_, idx=i: self.edit_step(idx))
                self.grid.add_widget(b)

        bg(lambda: data.progress_get(fig, self.item.get("names")), done)

    def open_edit(self):
        self.manager.get_screen("edit").show(self.item)
        self.manager.current = "edit"

    def do_all_done(self):
        def yes():
            def work():
                return data.complete_all(self.item["fig"], self.item.get("names"),
                                         self.item.get("row"))

            def done(res, err):
                if err:
                    toast("失败：" + err)
                    return
                self.load()

            bg(work, done)

        dialog.confirm("把这一行的所有工序都标记为已完成？", yes, "全部完成")


    def edit_step(self, i):
        st = self._st
        if not st:
            return
        self._step_pop = StepEdit(self.item, st, i, lambda: self.load())
        self._step_pop.open()

    def toggle(self, i):
        def work():
            return data.toggle_step(self.item["fig"], i, self.item.get("names"))

        def done(res, err):
            if err:
                toast("保存失败：" + err)
                return
            self.load()

        bg(work, done)


class StepEdit(dialog.Sheet):
    """单道工序编辑：名称 / 理论 / 实际 / 完成（浅色弹层）"""

    def __init__(self, item, st, idx, on_saved):
        super().__init__("工序 %d" % (idx + 1), height=0.64)
        self.item, self.st, self.idx, self.on_saved = item, st, idx, on_saved

        self.body.add_widget(lab("工序名称", 12, MUTED, height=dp(20)))
        self.name = TextInput(text=(st["names"][idx] or ""), multiline=False,
                              size_hint_y=None, height=dp(38), font_size=sp(14),
                              padding=[dp(8), dp(10)])
        font(self.name)
        self.body.add_widget(self.name)

        self.plan = Button(text="理论完成：" + (st["plan"][idx] or "未设置"), size_hint_y=None,
                           height=dp(40), background_normal="", background_color=GREY,
                           color=INK, font_size=sp(13))
        font(self.plan)
        self.plan.bind(on_release=lambda *_: self.pick("plan"))
        self.body.add_widget(self.plan)

        self.actual = Button(text="实际完成：" + (st["actual"][idx] or "未设置"),
                             size_hint_y=None, height=dp(40), background_normal="",
                             background_color=GREY, color=INK, font_size=sp(13))
        font(self.actual)
        self.actual.bind(on_release=lambda *_: self.pick("actual"))
        self.body.add_widget(self.actual)

        self.done_btn = Button(text="当前：已完成（点此取消）" if st["done"][idx]
                               else "当前：未完成（点此点绿）",
                               size_hint_y=None, height=dp(46), background_normal="",
                               background_color=GREEN if st["done"][idx] else GREY,
                               color=(1, 1, 1, 1) if st["done"][idx] else INK,
                               font_size=sp(14))
        font(self.done_btn)
        self.done_btn.bind(on_release=lambda *_: self.toggle_done())
        self.body.add_widget(self.done_btn)

        foot = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        foot.add_widget(dialog.btn("取消", lambda *_: self.dismiss(), color=GREY, text_color=INK))
        foot.add_widget(dialog.btn("保存", self.save, color=dialog.BLUE))
        self.body.add_widget(foot)

    def pick(self, which):
        cur = self.st[which][self.idx]

        def on_pick(val):
            self.st[which][self.idx] = val
            b = self.plan if which == "plan" else self.actual
            b.text = ("理论完成：" if which == "plan" else "实际完成：") + (val or "未设置")

        datepicker.DatePicker(current=cur, on_pick=on_pick).open()

    def toggle_done(self):
        on = not self.st["done"][self.idx]
        self.st["done"][self.idx] = on
        self.done_btn.text = "当前：已完成（点此取消）" if on else "当前：未完成（点此点绿）"
        self.done_btn.background_color = GREEN if on else GREY
        self.done_btn.color = (1, 1, 1, 1) if on else INK

    def save(self):
        def work():
            return data.save_step(self.item["fig"], self.item.get("row"),
                                  self.item.get("names"), self.idx,
                                  self.name.text.strip(), self.st["plan"][self.idx],
                                  self.st["actual"][self.idx], self.st["done"][self.idx])

        def done(res, err):
            if err:
                toast("保存失败：" + err)
                return
            self.dismiss()
            self.on_saved()

        bg(work, done)


class EditScreen(Screen):
    """修改登记信息"""

    FIELDS = [("fig", "图号"), ("spec", "规格"), ("cust", "客户编号"), ("qty", "数量"),
              ("owner", "担当"), ("special", "特殊要求"), ("note", "备注")]

    def __init__(self, **kw):
        super().__init__(**kw)
        self.item = None
        self.inputs = {}
        root = BoxLayout(orientation="vertical")
        root.add_widget(Header("编辑登记", ""))
        bar = BoxLayout(size_hint_y=None, height=dp(46), padding=[dp(8), dp(6)], spacing=dp(6))
        bar.add_widget(flat_btn("←", lambda: setattr(self.manager, "current", "detail"),
                                height=34, size=16))
        bar.add_widget(lab("改完点「保存」，会写回飞书并留变更记录", 12, MUTED))
        root.add_widget(bar)
        scroll = ScrollView(bar_width=dp(3))
        form = GridLayout(cols=1, spacing=dp(4), size_hint_y=None, padding=[dp(12), dp(6)])
        form.bind(minimum_height=form.setter("height"))
        for key, label in self.FIELDS:
            form.add_widget(lab(label, 12, MUTED, height=dp(20)))
            t = TextInput(multiline=(key == "note"), size_hint_y=None,
                          height=dp(38) if key != "note" else dp(64), font_size=sp(13),
                          padding=[dp(8), dp(10)])
            font(t)
            self.inputs[key] = t
            form.add_widget(t)
        for key, label in (("due", "要求完成日期"), ("date", "接收日期"), ("actual", "实际完成日期")):
            form.add_widget(lab(label, 12, MUTED, height=dp(20)))
            b = Button(text="未设置", size_hint_y=None, height=dp(38), background_normal="",
                       background_color=GREY, color=INK, font_size=sp(13))
            font(b)
            b.bind(on_release=lambda *_, k=key: self.pick(k))
            self.inputs[key] = b
            form.add_widget(b)
        scroll.add_widget(form)
        root.add_widget(scroll)
        foot = BoxLayout(size_hint_y=None, height=dp(58), padding=[dp(12), dp(8)])
        foot.add_widget(btn("保存", self.save, color=GREEN, height=44, size=15))
        root.add_widget(foot)
        self.add_widget(root)

    def show(self, it):
        self.item = it
        for key, widget in self.inputs.items():
            val = {"due": it.get("due"), "date": it.get("date"), "actual": it.get("actual")}
            if key in val:
                widget.text = ("%s：%s" % ("", val[key] or "未设置")).strip()
                widget.text = ("日期：" + (val[key] or "未设置"))
            else:
                widget.text = it.get(key, "") or ""

    def pick(self, key):
        cur = ""
        txt = self.inputs[key].text
        if "：" in txt:
            cur = txt.split("：", 1)[1]
        if cur in ("未设置", "日期"):
            cur = ""

        def on_pick(val):
            self.inputs[key].text = "日期：" + (val or "未设置")

        datepicker.DatePicker(current=cur, on_pick=on_pick).open()

    def save(self):
        changes = {}
        for key, widget in self.inputs.items():
            if key in ("due", "date", "actual"):
                val = widget.text.split("：", 1)[-1]
                val = "" if val in ("未设置", "日期") else val
                orig = {"due": self.item.get("due"), "date": self.item.get("date"),
                        "actual": self.item.get("actual")}[key]
                if (val or "") != (orig or ""):
                    changes[key] = val
            else:
                val = widget.text.strip()
                if val != (self.item.get(key, "") or ""):
                    changes[key] = val
        if not changes:
            toast("没有改动")
            return

        def work():
            return data.update_sample(self.item["row"], changes, self.item.get("fig", ""))

        def done(res, err):
            if err:
                toast("保存失败：" + err)
                return
            toast("已保存")
            self.manager.get_screen("samples").items = []
            self.manager.current = "samples"

        bg(work, done)


def _write_result(ver, text):
    try:
        import time as _t
        with open(os.path.join(data._data_dir(), "update_result.txt"), "a",
                  encoding="utf-8") as f:
            f.write("%s  V%s  %s\n" % (_t.strftime("%Y-%m-%d %H:%M"), ver, text))
    except Exception:
        pass


class StockScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        root = BoxLayout(orientation="vertical")
        root.add_widget(Header("库存查询", ""))
        bar = BoxLayout(size_hint_y=None, height=dp(48), padding=[dp(8), dp(6)], spacing=dp(6))
        bar.add_widget(flat_btn("←", lambda: setattr(self.manager, "current", "home"),
                                height=36, size=16))
        self.kw = TextInput(hint_text="图番（空=最近 100 条）", multiline=False,
                            size_hint_y=None, height=dp(36), font_size=sp(13),
                            padding=[dp(8), dp(9)])
        font(self.kw)
        self.kw.bind(on_text_validate=lambda *_: self.search())
        bar.add_widget(self.kw)
        bar.add_widget(flat_btn("查询", self.search, color=BLUE, text_color=(1, 1, 1, 1), height=36))
        root.add_widget(bar)
        self.scroll = ScrollView(bar_width=dp(3))
        self.list = GridLayout(cols=1, spacing=dp(6), size_hint_y=None, padding=[dp(8), dp(6)])
        self.list.bind(minimum_height=self.list.setter("height"))
        self.scroll.add_widget(self.list)
        root.add_widget(self.scroll)
        self.add_widget(root)

    def on_pre_enter(self, *_):
        if not self.list.children:
            self.search()

    def search(self):
        self.list.clear_widgets()
        self.list.add_widget(lab("查询中...", 13, MUTED))

        def done(res, err):
            self.list.clear_widgets()
            if err:
                self.list.add_widget(lab("失败：" + err, 13, RED))
                return
            if not res:
                self.list.add_widget(lab("没有记录", 13, MUTED))
                return
            for it in res:
                c = card(padding=10, spacing=2)
                c.height = dp(64)
                c.add_widget(lab("%s   %s" % (it["fig"], it["spec"]), 14, INK, True))
                c.add_widget(lab("库存 %s ｜ 厂家 %s ｜ 货架 %s ｜ %s" % (
                    it["stock"] or "-", it["maker"] or "-", it["shelf"] or "-",
                    it["io"] or "-"), 12, MUTED))
                self.list.add_widget(c)

        bg(lambda: data.stock_search(self.kw.text), done)


class NewScreen(Screen):
    FIELDS = [("cust", "客户编号"), ("fig", "图号"), ("spec", "规格"), ("qty", "数量"),
              ("due", "要求完成日期"), ("owner", "担当"),
              ("special", "特殊要求"), ("date", "接收日期")]

    def __init__(self, **kw):
        super().__init__(**kw)
        self.inputs = {}
        root = BoxLayout(orientation="vertical")
        root.add_widget(Header("新建登记", ""))
        bar = BoxLayout(size_hint_y=None, height=dp(46), padding=[dp(8), dp(6)], spacing=dp(6))
        bar.add_widget(flat_btn("←", lambda: setattr(self.manager, "current", "samples"),
                                height=34, size=16))
        bar.add_widget(lab("填写后提交，写入飞书表格末行", 12, MUTED))
        root.add_widget(bar)
        scroll = ScrollView(bar_width=dp(3))
        form = GridLayout(cols=1, spacing=dp(4), size_hint_y=None, padding=[dp(12), dp(6)])
        form.bind(minimum_height=form.setter("height"))
        today = datetime.date.today().strftime("%Y-%m-%d")
        self.dates = {"due": today, "date": today}
        for key, label in self.FIELDS:
            form.add_widget(lab(label, 12, MUTED, height=dp(20)))
            if key in ("due", "date"):
                b = Button(text="日期：" + today, size_hint_y=None, height=dp(38),
                           background_normal="", background_color=GREY, color=INK,
                           font_size=sp(13))
                font(b)
                b.bind(on_release=lambda *_, k=key: self.pick(k))
                form.add_widget(b)
                self.inputs[key] = b
                continue
            t = TextInput(multiline=False, size_hint_y=None, height=dp(38),
                          font_size=sp(13), padding=[dp(8), dp(10)])
            font(t)
            self.inputs[key] = t
            form.add_widget(t)
        scroll.add_widget(form)
        root.add_widget(scroll)
        foot = BoxLayout(size_hint_y=None, height=dp(58), padding=[dp(12), dp(8)])
        foot.add_widget(btn("提交", self.submit, color=GREEN, height=44, size=15))
        root.add_widget(foot)
        self.add_widget(root)

    def pick(self, key):
        cur = self.dates.get(key) or ""

        def on_pick(val):
            self.dates[key] = val
            self.inputs[key].text = "日期：" + (val or "未设置")

        datepicker.DatePicker(current=cur, on_pick=on_pick).open()

    def submit(self):
        d = {}
        for k, v in self.inputs.items():
            if k in ("due", "date"):
                d[k] = self.dates.get(k) or ""
            else:
                d[k] = v.text.strip()
        if not d.get("fig"):
            toast("图号必填")
            return

        def done(res, err):
            if err:
                toast("提交失败：" + err)
                return
            toast("已写入第 %s 行" % res)
            self.manager.get_screen("samples").items = []
            self.manager.current = "samples"

        bg(lambda: data.new_sample(d), done)


if __name__ == "__main__":
    RootApp().run()
