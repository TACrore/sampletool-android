# -*- coding: utf-8 -*-
"""Android 登录：OAuth 授权码（复制回调 code 粘贴）+ token 持久化"""
import json
import os
import time
import urllib.parse

API = "https://open.feishu.cn"
HERE = os.path.dirname(os.path.abspath(__file__))


def load_app_conf():
    for name in ("feishu.json", os.path.join("assets", "feishu.json")):
        p = os.path.join(HERE, name)
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                return json.load(f)
    return {}


def auth_url():
    c = load_app_conf()
    q = urllib.parse.urlencode({
        "app_id": c.get("app_id", ""),
        "redirect_uri": c.get("redirect_uri", ""),
        "response_type": "code",
        "scope": "sheets:spreadsheet offline_access",
        "state": "sample",
    })
    return API + "/open-apis/authen/v1/authorize?" + q


def exchange_code(code, data):
    """用授权码换 user_access_token，并写入本地 token 文件。"""
    c = load_app_conf()
    code = (code or "").strip()
    if not code:
        raise RuntimeError("请先粘贴回调里的 code")
    if "code=" in code:
        code = urllib.parse.parse_qs(urllib.parse.urlparse(code).query).get("code", [code])[0]
    r = data._http("POST", "/open-apis/authen/v2/oauth/token", {
        "grant_type": "authorization_code",
        "client_id": c.get("app_id", ""),
        "client_secret": c.get("app_secret", ""),
        "code": code,
        "redirect_uri": c.get("redirect_uri", ""),
    })
    d = r.get("data") or r
    if not d.get("access_token"):
        raise RuntimeError(str(r.get("msg") or r.get("error_description") or r)[:160])
    tok = {
        "user_access_token": d["access_token"],
        "refresh_token": d.get("refresh_token", ""),
        "expire_at": time.time() + int(d.get("expires_in", 7200)),
        "name": "",
    }
    data._save_token(tok)
    try:
        info = data.whoami()
        tok["name"] = info.get("name", "")
        tok["open_id"] = info.get("open_id", "")
        data._save_token(tok)
    except Exception:
        pass
    return tok.get("name", "")


_CALLBACK = {"srv": None}


def start_callback(on_code, port=8765):
    """在本机 127.0.0.1:port 起回调监听；收到 code 自动回调 on_code(code)。
    手机/电脑上浏览器跳转 localhost 时，如果 App 在跑，可全自动完成，不用复制。"""
    import http.server
    import threading

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            code = (q.get("code") or [""])[0]
            body = ("<html><body style='font:16px sans-serif;padding:24px'>" +
                    ("授权成功，可关闭本页，回到程序。" if code else "授权失败或已取消。") +
                    "</body></html>").encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            if code:
                try:
                    on_code(code)
                except Exception:
                    pass

        def log_message(self, *a):
            pass

    try:
        srv = http.server.HTTPServer(("127.0.0.1", port), H)
        srv.timeout = 1
        _CALLBACK["srv"] = srv

        def loop():
            while _CALLBACK.get("srv") is srv:
                try:
                    srv.handle_request()
                except Exception:
                    break

        threading.Thread(target=loop, daemon=True).start()
        return True
    except Exception:
        return False


def stop_callback():
    srv = _CALLBACK.get("srv")
    _CALLBACK["srv"] = None
    try:
        srv and srv.server_close()
    except Exception:
        pass
