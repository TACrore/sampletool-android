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
HEADER_WORDS = ('图号', '图号规格', '规格', '客户编号', '接收日期', '需求数量', '客户担当者', '数量', '要求完成', '实际完成', '登记日期')
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


_CA_CTX = {"v": None}


def _ssl_ctx(verify=True):
    import ssl
    if not verify:
        return ssl._create_unverified_context()
    if _CA_CTX["v"] is not None:
        return _CA_CTX["v"]
    cafile = None
    try:
        import certifi
        cafile = certifi.where()
    except Exception:
        cafile = None
    try:
        ctx = ssl.create_default_context(cafile=cafile) if cafile else ssl.create_default_context()
    except Exception:
        ctx = ssl.create_default_context()
    _CA_CTX["v"] = ctx
    return ctx


def _open(req, timeout, verify=True):
    """带 CA 证书链的请求；证书校验失败再降级一次（企业网 TLS 拦截场景）。"""
    import ssl
    try:
        opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=_ssl_ctx(verify)))
        return opener.open(req, timeout=timeout)
    except urllib.error.HTTPError:
        raise
    except urllib.error.URLError as e:
        reason = str(getattr(e, "reason", e))
        if verify and ("CERTIFICATE" in reason.upper() or "SSL" in reason.upper()):
            log_crash("tls", "verify failed, retry unverified: " + reason[:200])
            opener = urllib.request.build_opener(
                urllib.request.HTTPSHandler(context=_ssl_ctx(False)))
            return opener.open(req, timeout=timeout)
        raise


def _http(method, path, payload=None, token=None, timeout=45):
    data = None
    hdr = {"Content-Type": "application/json; charset=utf-8"}
    if token:
        hdr["Authorization"] = "Bearer " + token
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(API + path, data=data, headers=hdr, method=method)
    try:
        with _open(req, timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")
        try:
            return json.loads(body)
        except Exception:
            return {"code": e.code, "msg": body[:200]}
    except urllib.error.URLError as e:
        raise RuntimeError("网络错误：" + str(getattr(e, "reason", e))[:160])


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


def _values(sheet_id, start, end, last_col="L"):
    r = _api("GET", "/open-apis/sheets/v2/spreadsheets/%s/values/%s!A%d:%s%d"
             % (SPREADSHEET, sheet_id, start, last_col, end))
    return ((r.get("data") or {}).get("valueRange") or {}).get("values") or []


def load_samples(rows=20000, step=2000):
    """样品登记列表（最新在前）。分段读，避免单次超行数上限。"""
    out = []
    start = 1
    while start <= rows:
        end = min(start + step - 1, rows)
        vals = _values(SHEET_SAMPLE, start, end, "AH")
        if not vals:
            break
        for i, row in enumerate(vals, start=start):
            row = list(row) + [""] * (34 - len(row))
            if not any(_s(v) for v in row):
                continue
            fig = _s(row[3])
            if not fig:
                continue
            if fig in HEADER_WORDS or _s(row[0]) in HEADER_WORDS or _s(row[2]) in HEADER_WORDS:
                continue
            out.append({"row": i, "date": _serial_to_date(row[0]), "spec": _s(row[2]),
                        "fig": fig, "cust": _s(row[4]), "qty": _s(row[7]),
                        "due": _serial_to_date(row[8]), "urgent": _s(row[9]) == "急",
                        "special": _s(row[10]), "owner": _s(row[11]), "note": _s(row[12]),
                        "names": [_s(row[14 + j]) for j in range(20)]})
        if len(vals) < step:
            break
        start = end + 1
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
    """工序进度：图号 → {row, st}（分段读）"""
    if _PROG["map"] and not refresh and time.time() - _PROG["loaded"] < 300:
        return _PROG["map"]
    m = {}
    start = 1
    step = 2000
    total = 14000
    while start <= total:
        end = min(start + step - 1, total)
        vals = _values(SHEET_PROGRESS, start, end, "B")
        if not vals:
            break
        for i, row in enumerate(vals, start=start):
            row = list(row) + ["", ""]
            fig = _s(row[0])
            if not fig:
                continue
            m[fig] = {"row": i, "raw": _s(row[1])}
        if len(vals) < step:
            break
        start = end + 1
    _PROG["map"] = m
    _PROG["loaded"] = time.time()
    return m


def progress_get(fig, names=None):
    it = progress_map().get(fig) or {}
    st = {"done": [False] * STEPS, "names": (list(names) if names else [""] * STEPS),
          "plan": [""] * STEPS, "actual": [""] * STEPS, "status": "", "reason": ""}
    while len(st["names"]) < STEPS:
        st["names"].append("")
    st["names"] = st["names"][:STEPS]
    raw = it.get("raw") or ""
    if raw:
        try:
            d = json.loads(raw)
            ds = str(d.get("d") or "")
            st["done"] = [ds[i] == "1" if i < len(ds) else False for i in range(STEPS)]
            for k, target in (("p", "plan"), ("a", "actual"), ("n", "names")):
                v = d.get(k)
                if isinstance(v, dict):
                    for i, val in v.items():
                        try:
                            j = int(i)
                        except Exception:
                            continue
                        if 0 <= j < STEPS and val:
                            st[target][j] = str(val)
                elif isinstance(v, str) and v:
                    # 旧版手机写的定长字符串（兼容修复）
                    step = 10 if k in ("p", "a") else 6
                    for j in range(min(STEPS, len(v) // step)):
                        seg = v[j * step:(j + 1) * step].strip()
                        if seg:
                            st[target][j] = seg
            st["status"] = d.get("s") or ""
            st["reason"] = d.get("r") or ""
        except Exception:
            pass
    return st


def _pack(st):
    d = {}
    d["d"] = "".join("1" if x else "0" for x in st["done"])
    for src, k in (("plan", "p"), ("actual", "a"), ("names", "n")):
        m = {str(i): str(v) for i, v in enumerate(st.get(src) or []) if v}
        if m:
            d[k] = m
    if st.get("status"):
        d["s"] = st["status"]
    if st.get("reason"):
        d["r"] = (st["reason"] or "")[:40]
    return json.dumps(d, ensure_ascii=False, separators=(",", ":"))




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


def toggle_step(fig, i, names=None):
    st = progress_get(fig, names)
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


def repair_progress_rows():
    """把旧版手机写的 p/a 字符串格式改回桌面端字典格式；返回修复行数。"""
    fixed = 0
    start = 1
    step = 2000
    total = 14000
    base = "/open-apis/sheets/v2/spreadsheets/%s/values" % SPREADSHEET
    while start <= total:
        end = min(start + step - 1, total)
        vals = _values(SHEET_PROGRESS, start, end, "B")
        if not vals:
            break
        batch = []
        for i, row in enumerate(vals, start=start):
            raw = _s((list(row) + [""])[0])
            if not raw.startswith("{"):
                continue
            try:
                d = json.loads(raw)
            except Exception:
                continue
            bad = False
            for k, width in (("p", 10), ("a", 10), ("n", 6)):
                v = d.get(k)
                if isinstance(v, str):
                    m = {}
                    for j in range(min(STEPS, len(v) // width)):
                        seg = v[j * width:(j + 1) * width].strip()
                        if seg:
                            m[str(j)] = seg
                    if m:
                        d[k] = m
                    else:
                        d.pop(k, None)
                    bad = True
            if bad:
                batch.append([i, d])
        for row_no, d in batch:
            raw = json.dumps(d, ensure_ascii=False, separators=(",", ":"))
            _api("PUT", base, {"valueRange": {
                "range": "%s!B%d:B%d" % (SHEET_PROGRESS, row_no, row_no),
                "values": [[raw]]}})
            fixed += 1
        if len(vals) < step:
            break
        start = end + 1
    if fixed:
        _PROG["map"] = {}
        _PROG["loaded"] = 0.0
    return fixed


SAMPLE_COLS = {"cust": "E", "fig": "D", "spec": "C", "qty": "H", "due": "I",
               "owner": "L", "special": "K", "note": "M", "date": "A", "actual": "N"}


def col_letter(idx):
    s = ""
    idx += 1
    while idx:
        idx, r = divmod(idx - 1, 26)
        s = chr(65 + r) + s
    return s


def _put_cell(sheet_id, row, col, value):
    _api("PUT", "/open-apis/sheets/v2/spreadsheets/%s/values" % SPREADSHEET,
         {"valueRange": {"range": "%s!%s%d:%s%d" % (sheet_id, col, row, col, row),
                         "values": [[value]]}})


FIELD_CN = {"cust": "客户编号", "fig": "图号", "spec": "规格", "qty": "数量",
            "due": "要求完成", "owner": "担当", "special": "特殊要求",
            "note": "备注", "date": "接收日期", "actual": "实际完成"}


def update_sample(row, changes, fig=""):
    """changes: {字段: 值}；due/date 自动转成序列号。写回并记一条变更。"""
    detail = []
    for key, val in changes.items():
        col = SAMPLE_COLS.get(key)
        if not col:
            continue
        v = val
        if key in ("due", "date", "actual"):
            v = _date_serial(val) if val else ""
        if key == "qty":
            try:
                v = int(float(val)) if str(val).strip() else ""
            except Exception:
                v = val
        _put_cell(SHEET_SAMPLE, row, col, v)
        detail.append("%s：%s" % (FIELD_CN.get(key, key), val))
    if detail:
        append_change("", row, fig or changes.get("fig", ""), "修改", "；".join(detail))
    return True


def set_step_name(row, idx, name):
    _put_cell(SHEET_SAMPLE, row, col_letter(14 + idx), name or "")
    return True


def append_change(who, row_no, fig, kind, detail):
    sid = sheet_id_by_title("变更记录")
    if not sid:
        return False
    try:
        r = _api("GET", "/open-apis/sheets/v2/spreadsheets/%s/values/%s!A1:A5000"
                 % (SPREADSHEET, sid))
        vals = ((r.get("data") or {}).get("valueRange") or {}).get("values") or []
        last = 1
        for i, v in enumerate(vals, start=1):
            if v and str(v[0] or "").strip():
                last = i
        when = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        if not who:
            who = _load_token().get("name") or "手机端"
        _api("PUT", "/open-apis/sheets/v2/spreadsheets/%s/values" % SPREADSHEET,
             {"valueRange": {"range": "%s!A%d:F%d" % (sid, last + 1, last + 1),
                             "values": [[when, who, str(row_no), str(fig),
                                         str(kind), str(detail)[:400]]]}})
        return True
    except Exception:
        return False


def save_step(fig, row, names, idx, name, plan, actual, done):
    """保存一道工序：名字写回样品记录，状态写回工序进度。"""
    if name is not None and row:
        try:
            set_step_name(row, idx, name)
        except Exception:
            pass
    st = progress_get(fig, names)
    if name is not None:
        st["names"][idx] = name
    st["plan"][idx] = plan or ""
    st["actual"][idx] = actual or ""
    st["done"][idx] = bool(done)
    progress_save(fig, st)
    return st


def complete_all(fig, names, row=None):
    st = progress_get(fig, names)
    today = datetime.date.today().strftime("%Y-%m-%d")
    for i in range(STEPS):
        if (st["names"][i] or "").strip():
            st["done"][i] = True
            if not st["actual"][i]:
                st["actual"][i] = today
            if not st["plan"][i]:
                st["plan"][i] = (datetime.date.today() +
                                 datetime.timedelta(days=7)).strftime("%Y-%m-%d")
    progress_save(fig, st)
    return st


def set_sample_status(fig, row, status, reason=""):
    """status: '' / 'pause' / 'abort'"""
    st = progress_get(fig)
    st["status"] = status
    st["reason"] = reason
    progress_save(fig, st)
    if status:
        label = {"pause": "生产暂停", "abort": "生产中止"}.get(status, status)
        append_change("", row or 0, fig, label, reason)
    return st


def latest_release(platform="android"):
    """读「更新记录」里该平台最新一版；返回 {version, file_token, sha256} 或 None。"""
    sid = sheet_id_by_title("更新记录")
    if not sid:
        return None
    r = _api("GET", "/open-apis/sheets/v2/spreadsheets/%s/values/%s!A2:I100"
             % (SPREADSHEET, sid))
    vals = ((r.get("data") or {}).get("valueRange") or {}).get("values") or []
    best = None
    for row in vals:
        row = list(row) + [""] * (9 - len(row))
        ver = _s(row[0])
        plat = _s(row[6]) or "win"
        if not ver or plat != platform:
            continue
        item = {"version": ver, "sha256": _s(row[1]), "file_token": _s(row[8]),
                "type": _s(row[7]) or "sheet"}
        if best is None or ver_tuple(ver) > ver_tuple(best["version"]):
            best = item
    return best


def ver_tuple(v):
    out = []
    for part in str(v or "").replace("-", ".").split("."):
        num = ""
        for ch in part:
            if ch.isdigit():
                num += ch
            else:
                break
        out.append(int(num or 0))
    return tuple(out + [0] * (3 - len(out)))[:3]


def download_release(file_token, dst):
    tok = user_token()
    url = API + "/open-apis/drive/v1/files/%s/download" % file_token
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + tok})
    with urllib.request.urlopen(req, timeout=900) as r, open(dst, "wb") as f:
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            f.write(b)
    return dst
