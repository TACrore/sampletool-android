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
        "client_id": c.get("app_id", ""),
        "redirect_uri": c.get("redirect_uri", ""),
        "response_type": "code",
        "scope": " ".join([
            "sheets:spreadsheet",
            "bitable:app",
            "offline_access",
        ]),
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
