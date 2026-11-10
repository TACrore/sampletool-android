# -*- coding: utf-8 -*-
"""Android 端数据层：样品登记（电子表格）+ 工序进度 + 库存（Base）+ 版本检查"""
import datetime
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://open.feishu.cn"
SPREADSHEET = "Tj8as05MfhRWjRtsUDYc1xmdnrf"
SHEET_SAMPLE = "0qVBlJ"       # 样品记录
SHEET_PROGRESS = "4m1iVi"     # 工序进度（A=图号，B=JSON）
BASE_APP = "UtX4b0Y2qadqzEsMXbAcaGfwnKg"
BASE_TABLE = "tbli62aFhhiu866v"
STEPS = 20
DATA_DIR = ""


def _data_dir():
    global DATA_DIR
    if DATA_DIR:
        return DATA_DIR
    cands = []
    try:
        cands.append(app_private)  # noqa: F821  p4a 注入
    except NameError:
        pass
    cands.append(os.environ.get("ANDROID_PRIVATE") or "")
    cands.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"))
    for c in cands:
        if not c:
            continue
        try:
            os.makedirs(c, exist_ok=True)
            with open(os.path.join(c, ".w"), "w"):
                pass
            DATA_DIR = c
            return c
        except Exception:
            continue
    DATA_DIR = os.path.dirname(os.path.abspath(__file__))
    return DATA_DIR


def log_crash(tag, text):
    try:
        with open(os.path.join(_data_dir(), "crash.log"), "a", encoding="utf-8") as f:
            f.write("\n== %s %s\n%s\n" % (tag, time.strftime("%m-%d %H:%M:%S"), text))
    except Exception:
        pass


def _token_path():
    return os.path.join(_data_dir(), "token.json")


def _load_token():
    try:
        with open(_token_path(), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_token(t):
    try:
        with open(_token_path(), "w", encoding="utf-8") as f:
            json.dump(t, f, ensure_ascii=False)
    except Exception:
        pass


def _http(method, path, payload=None, token=None, timeout=45):
    url = API + path
    data = None
    hdr = {"Content-Type": "application/json; charset=utf-8"}
    if token:
        hdr["Authorization"] = "Bearer " + token
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=hdr, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")
        try:
            return json.loads(body)
        except Exception:
            return {"code": e.code, "msg": body[:200]}


def user_token():
    t = _load_token()
    tok = t.get("user_access_token") or ""
    if tok and time.time() < float(t.get("expire_at", 0)) - 120:
        return tok
    rt = t.get("refresh_token") or ""
    if not rt:
        raise RuntimeError("未登录")
    import auth
    c = auth.load_app_conf()
    r = _http("POST", "/open-apis/authen/v2/oauth/token", {
        "grant_type": "refresh_token", "client_id": c.get("app_id", ""),
        "client_secret": c.get("app_secret", ""), "refresh_token": rt})
    d = r.get("data") or r
    if not d.get("access_token"):
        raise RuntimeError("刷新失败：" + str(r.get("msg"))[:80])
    t.update({"user_access_token": d["access_token"],
              "refresh_token": d.get("refresh_token", rt),
              "expire_at": time.time() + int(d.get("expires_in", 7200))})
    _save_token(t)
    return t["user_access_token"]


def _api(method, path, payload=None):
    r = _http(method, path, payload, user_token())
    if r.get("code") not in (0, None):
        raise RuntimeError(str(r.get("msg") or r.get("code"))[:120])
    return r


def whoami():
    r = _http("GET", "/open-apis/authen/v1/user_info", None, user_token())
    return r.get("data") or {}


def _serial_to_date(v):
    try:
        n = float(v)
    except Exception:
        return str(v or "")
    if n <= 0:
        return ""
    base = datetime.datetime(1899, 12, 30)
    return (base + datetime.timedelta(days=n)).strftime("%Y-%m-%d")


def _s(v):
    if v is None:
        return ""
    if isinstance(v, list) and v and isinstance(v[0], dict):
        return "/".join(str(x.get("text") or "") for x in v)
    return str(v).strip()


def load_samples(rows=15000):
    """样品登记列表（最新在前）。"""
    r = _api("GET", "/open-apis/sheets/v2/spreadsheets/%s/values/%s!A1:L%d"
             % (SPREADSHEET, SHEET_SAMPLE, rows))
    vals = ((r.get("data") or {}).get("valueRange") or {}).get("values") or []
    out = []
    for i, row in enumerate(vals, start=1):
        row = list(row) + [""] * (12 - len(row))
        if not any(_s(v) for v in row):
            continue
        fig = _s(row[3])
        if not fig:
            continue
        out.append({"row": i, "date": _serial_to_date(row[0]), "spec": _s(row[2]),
                    "fig": fig, "cust": _s(row[4]), "qty": _s(row[7]),
                    "due": _serial_to_date(row[8]), "urgent": _s(row[9]) == "急",
                    "special": _s(row[10]), "owner": _s(row[11]), "note": _s(row[12])})
    out.reverse()
    return out


def search_samples(items, kw):
    kw = (kw or "").strip().upper()
    if not kw:
        return items
    return [it for it in items if kw in ("%s %s %s %s" % (
        it["fig"], it["cust"], it["spec"], it["owner"])).upper()]


_PROG = {"map": {}, "loaded": 0.0}


def progress_map(refresh=False):
    """工序进度：图号 → {row, st}"""
    if _PROG["map"] and not refresh and time.time() - _PROG["loaded"] < 300:
        return _PROG["map"]
    r = _api("GET", "/open-apis/sheets/v2/spreadsheets/%s/values/%s!A1:B13000"
             % (SPREADSHEET, SHEET_PROGRESS))
    vals = ((r.get("data") or {}).get("valueRange") or {}).get("values") or []
    m = {}
    for i, row in enumerate(vals, start=1):
        row = list(row) + ["", ""]
        fig = _s(row[0])
        if not fig:
            continue
        m[fig] = {"row": i, "raw": _s(row[1])}
    _PROG["map"] = m
    _PROG["loaded"] = time.time()
    return m


def progress_get(fig):
    it = progress_map().get(fig) or {}
    st = {"done": [False] * STEPS, "names": [""] * STEPS, "plan": [""] * STEPS,
          "actual": [""] * STEPS, "status": "", "reason": ""}
    raw = it.get("raw") or ""
    if raw:
        try:
            d = json.loads(raw)
            for k in ("d", "n", "p", "a"):
                ln = {"d": "done", "n": "names", "p": "plan", "a": "actual"}[k]
                v = d.get(k) or ""
                st[ln] = [v[j] == "1" if k == "d" else v[j] for j in range(min(STEPS, len(v)))]
                st[ln] += [False if k == "d" else ""] * (STEPS - len(st[ln]))
            st["status"] = d.get("s") or ""
            st["reason"] = d.get("r") or ""
        except Exception:
            pass
    return st


def _pack(st):
    return json.dumps({"d": "".join("1" if x else "0" for x in st["done"]),
                       "n": "".join(str(x or "")[:6].ljust(6)[:6] for x in st["names"]),
                       "p": "".join(str(x or "")[:10].ljust(10)[:10] for x in st["plan"]),
                       "a": "".join(str(x or "")[:10].ljust(10)[:10] for x in st["actual"]),
                       "s": st.get("status") or "", "r": (st.get("reason") or "")[:40]},
                      ensure_ascii=False, separators=(",", ":"))


def progress_save(fig, st):
    m = progress_map()
    raw = _pack(st)
    row = (m.get(fig) or {}).get("row")
    base = "/open-apis/sheets/v2/spreadsheets/%s/values" % SPREADSHEET
    if row:
        _api("PUT", base, {"valueRange": {"range": "%s!B%d:B%d" % (SHEET_PROGRESS, row, row),
                                          "values": [[raw]]}})
        m[fig] = {"row": row, "raw": raw}
    else:
        n = len(m) + 2
        _api("PUT", base, {"valueRange": {"range": "%s!A%d:B%d" % (SHEET_PROGRESS, n, n),
                                          "values": [[fig, raw]]}})
        m[fig] = {"row": n, "raw": raw}
    _PROG["loaded"] = time.time()


def toggle_step(fig, i):
    st = progress_get(fig)
    st["done"][i] = not st["done"][i]
    today = datetime.date.today().strftime("%Y-%m-%d")
    if st["done"][i]:
        if not st["actual"][i]:
            st["actual"][i] = today
        if not st["plan"][i]:
            st["plan"][i] = (datetime.date.today() + datetime.timedelta(days=7)).strftime("%Y-%m-%d")
    else:
        st["actual"][i] = ""
    progress_save(fig, st)
    return st


def stock_search(kw, limit=200):
    kw = (kw or "").strip()
    body = {"filter": {"conjunction": "and",
                       "conditions": ([{"field_name": "图番", "operator": "contains",
                                        "value": [kw]}] if kw else [])}}
    r = _api("POST", "/open-apis/bitable/v1/apps/%s/tables/%s/records/search?page_size=%d"
             "&automatic_fields=false" % (BASE_APP, BASE_TABLE, limit), body)
    out = []
    for it in ((r.get("data") or {}).get("items") or []):
        f = it.get("fields") or {}
        out.append({"fig": _s(f.get("图番")), "spec": _s(f.get("规格")),
                    "maker": _s(f.get("厂家")), "shelf": _s(f.get("货架号")),
                    "qty": _s(f.get("数量")), "stock": _s(f.get("现库存总数")),
                    "io": _s(f.get("出库/入库")), "date": _s(f.get("出入库日期"))})
    return out


def _last_row():
    r = _api("GET", "/open-apis/sheets/v2/spreadsheets/%s/values/%s!A1:A16000"
             % (SPREADSHEET, SHEET_SAMPLE))
    vals = ((r.get("data") or {}).get("valueRange") or {}).get("values") or []
    last = 0
    for i, row in enumerate(vals, start=1):
        if row and _s(row[0]):
            last = i
    return max(last, 1)


def _date_serial(s):
    d = None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            d = datetime.datetime.strptime((s or "").strip(), fmt)
            break
        except Exception:
            continue
    if not d:
        d = datetime.datetime.now()
    return (d - datetime.datetime(1899, 12, 30)).days


def new_sample(d):
    row = _last_row() + 1
    vals = [[_date_serial(d.get("date")), "", d.get("spec", ""), d.get("fig", ""),
             d.get("cust", ""), "", "", d.get("qty", ""),
             _date_serial(d.get("due")) if d.get("due") else "",
             "", d.get("special", ""), d.get("owner", "")]]
    _api("PUT", "/open-apis/sheets/v2/spreadsheets/%s/values" % SPREADSHEET,
         {"valueRange": {"range": "%s!A%d:L%d" % (SHEET_SAMPLE, row, row), "values": vals}})
    return row


def sheet_id_by_title(title):
    r = _api("GET", "/open-apis/sheets/v2/spreadsheets/%s/metainfo" % SPREADSHEET)
    for s in ((r.get("data") or {}).get("sheets") or []):
        if s.get("title") == title:
            return s.get("sheetId")
    return ""


def latest_version():
    sid = sheet_id_by_title("更新记录")
    if not sid:
        return ""
    r = _api("GET", "/open-apis/sheets/v2/spreadsheets/%s/values/%s!A2:F20" % (SPREADSHEET, sid))
    vals = ((r.get("data") or {}).get("valueRange") or {}).get("values") or []
    best = ""
    for row in vals:
        v = _s((row or [""])[0])
        if not v:
            continue
        try:
            key = tuple(int(x) for x in v.lstrip("vV").split("."))
        except Exception:
            continue
        if not best or key > tuple(int(x) for x in best.split(".")):
            best = v
    return best
