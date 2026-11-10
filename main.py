# -*- coding: utf-8 -*-
"""样品查询管理工具 Android 版（Kivy）：登记查询 / 工序点绿 / 库存查询 / 新建"""
import datetime
import os
import threading
import webbrowser

import auth
import data
import fontutil
from kivy.app import App
from kivy.base import ExceptionHandler, ExceptionManager
from kivy.clock import Clock, mainthread
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import Screen, ScreenManager, SlideTransition
from kivy.uix.textinput import TextInput

APP_VERSION = "1.3.3"
FONT = fontutil.font_path()


def mk_label(text="", size=dp(14), bold=False, color=(0.12, 0.16, 0.22, 1), **kw):
    kw.setdefault("halign", "left")
    kw.setdefault("valign", "middle")
    lab = Label(text=text, font_size=size, color=color, bold=bold, **kw)
    if FONT:
        lab.font_name = FONT
    lab.bind(size=lambda w, *_: setattr(w, "text_size", (w.width, None)))
    return lab


def mk_button(text, on_press, color=(0.18, 0.44, 0.90, 1), height=dp(44), size=dp(14)):
    b = Button(text=text, size_hint_y=None, height=height, background_color=color,
               font_size=size, on_release=lambda *_: on_press())
    if FONT:
        b.font_name = FONT
    return b


def mk_input(hint="", text="", height=dp(40), multiline=False):
    t = TextInput(text=text, hint_text=hint, multiline=multiline, size_hint_y=None,
                  height=height, font_size=dp(14), padding=[dp(8), dp(8)])
    if FONT:
        t.font_name = FONT
    return t


def toast(msg, title="提示"):
    Popup(title=title, content=mk_label(msg, size=dp(14)), size_hint=(0.85, 0.35)).open()


class _KeepAlive(ExceptionHandler):
    def handle_exception(self, inst):
        import traceback as _tb
        data.log_crash("uncaught", _tb.format_exc())
        return ExceptionManager.PASS


ExceptionManager.add_handler(_KeepAlive())


def bg(work, done):
    """后台跑 work()，回主线程调 done(result) / done(None, err)"""
    def run():
        try:
            res = work()
            Clock.schedule_once(lambda *_: done(res, None), 0)
        except BaseException as e:  # noqa: BLE001
            import traceback as _tb
            data.log_crash("bg", _tb.format_exc())
            Clock.schedule_once(lambda *_: done(None, str(e)[:160]), 0)
    threading.Thread(target=run, daemon=True).start()


class LoginScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(10))
        root.add_widget(mk_label("样品查询管理工具", size=dp(24), bold=True,
                                 color=(0.16, 0.40, 0.85, 1)))
        root.add_widget(mk_label("首次使用：点「打开授权页」→ 飞书点同意 → 复制跳转后地址栏的整段网址 → 粘贴回来"))
        self.url = mk_input("授权地址（自动生成）")
        self.url.readonly = True
        root.add_widget(self.url)
        root.add_widget(mk_button("打开授权页", self.open_url))
        self.code = mk_input("粘贴回调网址或 code")
        root.add_widget(self.code)
        root.add_widget(mk_button("登录", self.do_login, color=(0.20, 0.62, 0.32, 1)))
        self.tip = mk_label("")
        root.add_widget(self.tip)
        root.add_widget(BoxLayout())
        self.add_widget(root)
        self.url.text = auth.auth_url()

    def open_url(self):
        try:
            webbrowser.open(auth.auth_url())
        except Exception:
            pass
        self.tip.text = "已在浏览器打开；如未弹出，长按地址框复制后手动打开"

    def do_login(self):
        self.tip.text = "登录中…"

        def done(_res, err):
            if err:
                self.tip.text = "失败：" + err
                return
            self.manager.current = "home"

        bg(lambda: auth.exchange_code(self.code.text, data), done)


class HomeScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))
        self.who = mk_label("", size=dp(18), bold=True)
        root.add_widget(self.who)
        root.add_widget(mk_label("版本 V" + APP_VERSION, size=dp(12),
                                 color=(0.45, 0.50, 0.58, 1)))
        root.add_widget(mk_button("样品登记", lambda: self.go("samples"), height=dp(56), size=dp(18)))
        root.add_widget(mk_button("库存查询", lambda: self.go("stock"), height=dp(56), size=dp(18)))
        root.add_widget(mk_button("检查更新", self.check_update, color=(0.35, 0.60, 0.90, 1)))
        root.add_widget(BoxLayout())
        root.add_widget(mk_button("退出登录", self.logout, color=(0.75, 0.30, 0.30, 1)))
        self.add_widget(root)

    def on_pre_enter(self, *_):
        t = data._load_token()
        self.who.text = "账号：" + (t.get("name") or "已登录")

    def go(self, name):
        self.manager.current = name

    def logout(self):
        data._save_token({})
        self.manager.current = "login"

    def check_update(self):
        def done(res, err):
            if err:
                toast("检查失败：" + err)
                return
            latest = res or ""
            try:
                newer = latest and tuple(int(x) for x in latest.split(".")) > \
                    tuple(int(x) for x in APP_VERSION.split("."))
            except Exception:
                newer = False
            toast("已是最新版本 V%s" % APP_VERSION if not newer
                  else "发现新版本 V%s\n请联系朱超获取安装包" % latest, "检查更新")

        bg(data.latest_version, done)


class SampleScreen(Screen):
    PAGE = 200

    def __init__(self, **kw):
        super().__init__(**kw)
        self.items = []
        self.shown = 0
        root = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))
        bar = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        bar.add_widget(mk_button("←", lambda: setattr(self.manager, "current", "home"),
                                 color=(0.55, 0.58, 0.64, 1), size=dp(18)))
        self.kw = mk_input("搜索 图号/客户/规格/担当")
        bar.add_widget(self.kw)
        bar.add_widget(mk_button("搜索", self.reload, size=dp(13)))
        root.add_widget(bar)
        bar2 = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(6))
        bar2.add_widget(mk_button("刷新", self.reload, color=(0.20, 0.62, 0.32, 1), size=dp(13)))
        bar2.add_widget(mk_button("新建登记", lambda: setattr(self.manager, "current", "new"),
                                  color=(0.90, 0.55, 0.15, 1), size=dp(13)))
        self.count = mk_label("", size=dp(12), color=(0.45, 0.50, 0.58, 1))
        bar2.add_widget(self.count)
        root.add_widget(bar2)
        self.scroll = ScrollView()
        self.list = GridLayout(cols=1, spacing=dp(4), size_hint_y=None)
        self.list.bind(minimum_height=self.list.setter("height"))
        self.scroll.add_widget(self.list)
        root.add_widget(self.scroll)
        self.add_widget(root)

    def on_pre_enter(self, *_):
        if not self.items:
            self.reload()

    def reload(self):
        self.count.text = "加载中…"

        def done(res, err):
            if err:
                self.count.text = "失败：" + err
                return
            self.items = res or []
            self.render()

        bg(lambda: data.load_samples(), done)
        return True

    def render(self):
        self.list.clear_widgets()
        kw = self.kw.text
        hits = data.search_samples(self.items, kw)
        self.shown = 0
        self.count.text = "%d 条" % len(hits)
        self._hits = hits
        self.load_more()

    def load_more(self):
        hits = getattr(self, "_hits", [])
        chunk = hits[self.shown:self.shown + self.PAGE]
        self.shown += len(chunk)
        for it in chunk:
            line = "%s  %s" % (it["fig"], it["spec"])
            sub = "%s 日 %s ｜ %s ｜ %s" % (it["date"] or "-", it["cust"] or "-",
                                          it["qty"] or "-", it["owner"] or "-")
            box = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(58),
                            padding=[dp(6), dp(2)])
            t1 = mk_label(line, size=dp(15), bold=True)
            t2 = mk_label(sub, size=dp(12), color=(0.45, 0.50, 0.58, 1))
            box.add_widget(t1)
            box.add_widget(t2)
            btn = Button(background_color=(0, 0, 0, 0), size_hint_y=None, height=dp(58))
            btn.bind(on_release=lambda *_, x=it: self.open_detail(x))
            box.add_widget(btn)
            self.list.add_widget(box)
        if self.shown < len(hits):
            self.list.add_widget(mk_button("加载更多（%d/%d）" % (self.shown, len(hits)),
                                           self.load_more, size=dp(13)))

    def open_detail(self, it):
        self.manager.get_screen("detail").show(it)
        self.manager.current = "detail"


class DetailScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.fig = ""
        root = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(6))
        bar = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(6))
        bar.add_widget(mk_button("←", lambda: setattr(self.manager, "current", "samples"),
                                 color=(0.55, 0.58, 0.64, 1), size=dp(18)))
        self.title = mk_label("", size=dp(16), bold=True)
        bar.add_widget(self.title)
        root.add_widget(bar)
        self.info = mk_label("", size=dp(12), color=(0.35, 0.40, 0.48, 1))
        root.add_widget(self.info)
        self.scroll = ScrollView()
        self.grid = GridLayout(cols=4, spacing=dp(4), size_hint_y=None)
        self.grid.bind(minimum_height=self.grid.setter("height"))
        self.scroll.add_widget(self.grid)
        root.add_widget(self.scroll)
        self.add_widget(root)

    def show(self, it):
        self.item = it
        self.title.text = it["fig"]
        self.info.text = "%s ｜ 客户 %s ｜ 数量 %s ｜ 担当 %s\n要求完成 %s ｜ %s" % (
            it["spec"], it["cust"], it["qty"], it["owner"], it["due"] or "-",
            it["special"] or "")
        self.load()

    def load(self):
        self.grid.clear_widgets()
        self.grid.add_widget(mk_label("读取工序进度…"))
        fig = self.item["fig"]

        def done(res, err):
            self.grid.clear_widgets()
            if err:
                self.grid.add_widget(mk_label("失败：" + err))
                return
            st = res
            for i in range(20):
                name = (st["names"][i] or "").strip() or ("工序%d" % (i + 1))
                done_ = bool(st["done"][i])
                txt = ("✔ %s" % name) if done_ else name
                b = Button(text=txt, size_hint_y=None, height=dp(52), font_size=dp(12),
                           background_color=(0.30, 0.75, 0.40, 1) if done_ else (0.88, 0.90, 0.93, 1),
                           color=(1, 1, 1, 1) if done_ else (0.2, 0.2, 0.2, 1))
                if FONT:
                    b.font_name = FONT
                b.bind(on_release=lambda *_, idx=i: self.toggle(idx))
                self.grid.add_widget(b)

        bg(lambda: data.progress_get(fig), done)

    def toggle(self, i):
        def work():
            return data.toggle_step(self.item["fig"], i)

        def done(res, err):
            if err:
                toast("保存失败：" + err)
                return
            self.load()

        bg(work, done)


class StockScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        root = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))
        bar = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        bar.add_widget(mk_button("←", lambda: setattr(self.manager, "current", "home"),
                                 color=(0.55, 0.58, 0.64, 1), size=dp(18)))
        self.kw = mk_input("图番（空=最近 100 条）")
        bar.add_widget(self.kw)
        bar.add_widget(mk_button("查询", self.search, size=dp(13)))
        root.add_widget(bar)
        self.scroll = ScrollView()
        self.list = GridLayout(cols=1, spacing=dp(4), size_hint_y=None)
        self.list.bind(minimum_height=self.list.setter("height"))
        self.scroll.add_widget(self.list)
        root.add_widget(self.scroll)
        self.add_widget(root)

    def search(self):
        self.list.clear_widgets()
        self.list.add_widget(mk_label("查询中…"))

        def done(res, err):
            self.list.clear_widgets()
            if err:
                self.list.add_widget(mk_label("失败：" + err))
                return
            if not res:
                self.list.add_widget(mk_label("没有记录"))
                return
            for it in res:
                box = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(56),
                                padding=[dp(6), dp(2)])
                box.add_widget(mk_label("%s  %s" % (it["fig"], it["spec"]), size=dp(14), bold=True))
                box.add_widget(mk_label("库存 %s ｜ 厂家 %s ｜ 货架 %s ｜ %s" % (
                    it["stock"], it["maker"], it["shelf"], it["io"]),
                    size=dp(12), color=(0.45, 0.50, 0.58, 1)))
                self.list.add_widget(box)

        bg(lambda: data.stock_search(self.kw.text), done)


class NewScreen(Screen):
    FIELDS = [("cust", "客户编号"), ("fig", "图号"), ("spec", "规格"), ("qty", "数量"),
              ("due", "要求完成日期 YYYY-MM-DD"), ("owner", "担当"),
              ("special", "特殊要求"), ("date", "接收日期 YYYY-MM-DD")]

    def __init__(self, **kw):
        super().__init__(**kw)
        self.inputs = {}
        root = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(6))
        bar = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(6))
        bar.add_widget(mk_button("←", lambda: setattr(self.manager, "current", "samples"),
                                 color=(0.55, 0.58, 0.64, 1), size=dp(18)))
        bar.add_widget(mk_label("新建登记", size=dp(16), bold=True))
        root.add_widget(bar)
        scroll = ScrollView()
        form = GridLayout(cols=1, spacing=dp(6), size_hint_y=None)
        form.bind(minimum_height=form.setter("height"))
        today = datetime.date.today().strftime("%Y-%m-%d")
        for key, label in self.FIELDS:
            form.add_widget(mk_label(label, size=dp(12), color=(0.35, 0.40, 0.48, 1)))
            t = mk_input("", today if key in ("due", "date") else "")
            self.inputs[key] = t
            form.add_widget(t)
        scroll.add_widget(form)
        root.add_widget(scroll)
        root.add_widget(mk_button("提交", self.submit, color=(0.20, 0.62, 0.32, 1)))
        self.add_widget(root)

    def submit(self):
        d = {k: v.text.strip() for k, v in self.inputs.items()}
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


from kivy.core.window import Window


class RootApp(App):
    def build(self):
        Window.clearcolor = (0.97, 0.98, 1, 1)
        self.title = "样品查询管理工具 V" + APP_VERSION
        sm = ScreenManager(transition=SlideTransition(duration=0.12))
        sm.add_widget(LoginScreen(name="login"))
        sm.add_widget(HomeScreen(name="home"))
        sm.add_widget(SampleScreen(name="samples"))
        sm.add_widget(DetailScreen(name="detail"))
        sm.add_widget(StockScreen(name="stock"))
        sm.add_widget(NewScreen(name="new"))
        sm.current = "home" if data._load_token().get("refresh_token") else "login"
        return sm


if __name__ == "__main__":
    RootApp().run()
