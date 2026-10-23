# -*- coding: utf-8 -*-
"""
Ключевая ставка Банка России — свежая, без обновления программы.

При запуске (в фоне) и потом раз в 6 часов программа узнаёт ставку:
1) с сайта Банка России — веб-сервис DailyInfo (KeyRate), а если он не ответил — таблица cbr.ru/hd_base/KeyRate;
2) если сайт ЦБ недоступен — с сайта LegalHelper (key_rates.json; его каждый день обновляет GitHub по данным ЦБ).

Полученное проверяется: ставки 1–60 %, даты с 2013 г., и прошлые ставки должны совпасть со встроенной таблицей —
иначе ответ отбрасывается (лучше старые данные, чем неверные). Новые ставки добавляются в таблицу калькуляторов
(legal_data.KEY_RATES) и сохраняются в key_rates.json в папке данных — работают и без интернета.
"""
import datetime as dt
import json
import os
import re
import threading
import urllib.request

import legal_data as D

SOAP_URL = "https://www.cbr.ru/DailyInfoWebServ/DailyInfo.asmx"
HTML_URL = ("https://www.cbr.ru/hd_base/KeyRate/?UniDbQuery.Posted=True&UniDbQuery.From={frm}"
            "&UniDbQuery.To={to}")
MIRROR_URL = "https://raw.githubusercontent.com/LegalHelper/legalhelper.github.io/main/key_rates.json"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
FILE = "key_rates.json"
BUILTIN = list(D.KEY_RATES)          # встроенная таблица (как вышла с программой)


def _get(url, data=None, headers=None, timeout=20):
    h = {"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"}
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    for enc in ("utf-8", "cp1251"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


# ----------------------------------------------------------------------------- разбор ответов
def parse_soap(xml):
    """<KR><DT>2024-10-28T00:00:00+03:00</DT><Rate>21.00</Rate></KR> … → [(дата ISO, ставка)] (по дням)."""
    out = []
    for m in re.finditer(r"<KR\b[^>]*>(.*?)</KR>", xml, re.S):
        body = m.group(1)
        d = re.search(r"<DT>\s*(\d{4}-\d{2}-\d{2})", body)
        r = re.search(r"<Rate>\s*([\d.,]+)\s*</Rate>", body)
        if d and r:
            out.append((d.group(1), float(r.group(1).replace(",", "."))))
    return out


def parse_html(page):
    """Таблица на cbr.ru: «28.10.2024 | 21,00» → [(дата ISO, ставка)]."""
    out = []
    for m in re.finditer(r"(\d{2})\.(\d{2})\.(\d{4})\s*</td>\s*<td[^>]*>\s*(\d{1,2},\d{1,2})\s*</td>", page):
        out.append((f"{m.group(3)}-{m.group(2)}-{m.group(1)}", float(m.group(4).replace(",", "."))))
    return out


def changes(daily):
    """Ставки по дням → только даты, с которых ставка менялась: [(дата начала, ставка)]."""
    out = []
    for d, r in sorted(set(daily)):
        if not out or abs(out[-1][1] - r) > 1e-9:
            out.append((d, r))
    return out


def _rate_on(table, d):
    v = None
    for s, r in table:
        if s <= d:
            v = r
        else:
            break
    return v


def validate(points, base=None):
    """Похоже ли на правду: разумные ставки и даты; где известна встроенная таблица — совпадение с ней."""
    base = base or BUILTIN
    if not points:
        return False
    for d, r in points:
        if not (1.0 <= r <= 60.0) or not ("2013-09-13" <= d <= (dt.date.today() + dt.timedelta(days=40)).isoformat()):
            return False
    # прошлое: на даты встроенной таблицы ставка должна совпасть (почти везде — встроенная таблица тоже
    # могла ошибиться в одной строке; тогда верим Банку России)
    first = points[0][0]
    checked = same = 0
    for s, r in base:
        if s < first:
            continue
        v = _rate_on(points, s)
        checked += 1
        same += 1 if v is not None and abs(v - r) < 1e-6 else 0
    if checked < 3:
        return first > base[-2][0]
    return same >= 0.8 * checked


def mismatches(points, base=None):
    """Где встроенная таблица расходится с полученной (для проверки самой программы)."""
    base = base or BUILTIN
    first = points[0][0] if points else "9999"
    return [(s, r, _rate_on(points, s)) for s, r in base if s >= first and _rate_on(points, s) != r]


def merge(base, fresh):
    """До начала свежих данных — встроенная таблица, дальше — свежие данные (Банк России главнее)."""
    if not fresh:
        return list(base)
    fresh = sorted(fresh)
    out = [tuple(p) for p in base if p[0] < fresh[0][0]]
    for d, r in fresh:
        if not out or abs(out[-1][1] - r) > 1e-9:
            out.append((d, r))
    return out


# ----------------------------------------------------------------------------- источники
def from_cbr_soap(since="2022-01-01"):
    to = (dt.date.today() + dt.timedelta(days=1)).isoformat()
    body = ('<?xml version="1.0" encoding="utf-8"?>'
            '<soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            'xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">'
            f'<soap12:Body><KeyRate xmlns="http://web.cbr.ru/"><fromDate>{since}T00:00:00</fromDate>'
            f'<ToDate>{to}T00:00:00</ToDate></KeyRate></soap12:Body></soap12:Envelope>')
    xml = _get(SOAP_URL, body.encode("utf-8"), {"Content-Type": "application/soap+xml; charset=utf-8"})
    return changes(parse_soap(xml))


def from_cbr_html(since="2022-01-01"):
    s = dt.date.fromisoformat(since).strftime("%d.%m.%Y")
    t = (dt.date.today() + dt.timedelta(days=1)).strftime("%d.%m.%Y")
    return changes(parse_html(_get(HTML_URL.format(frm=s, to=t))))


def from_mirror():
    data = json.loads(_get(MIRROR_URL))
    return [(d, float(r)) for d, r in data.get("rates", [])]


def fetch(log=None):
    """Свежие ставки: (таблица, источник) или (None, текст ошибки)."""
    errors = []
    for name, fn in (("сайт Банка России", from_cbr_soap), ("сайт Банка России", from_cbr_html),
                     ("сайт LegalHelper", from_mirror)):
        try:
            pts = fn()
        except Exception as e:
            errors.append(f"{fn.__name__}: {e!r}")
            continue
        if validate(pts):
            return merge(BUILTIN, pts), name
        errors.append(f"{fn.__name__}: ответ не прошёл проверку ({len(pts)} строк)")
    if log:
        log("; ".join(errors))
    return None, "; ".join(errors)


# ----------------------------------------------------------------------------- хранение и применение
def _path(data_dir):
    return os.path.join(data_dir, FILE)


def load_saved(data_dir):
    try:
        with open(_path(data_dir), encoding="utf-8") as f:
            data = json.load(f)
        pts = [(d, float(r)) for d, r in data.get("rates", [])]
        return pts if validate(pts) else None, data
    except Exception:
        return None, {}


def apply(table):
    """Подставить таблицу в калькуляторы (тот же список — все, кто его держит, видят новое)."""
    table = merge(BUILTIN, table)
    if [tuple(p) for p in table] != [tuple(p) for p in D.KEY_RATES]:
        D.KEY_RATES[:] = table
        return True
    return False


def save(data_dir, table, source):
    tmp = _path(data_dir) + ".part"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"rates": table, "source": source, "checked": dt.datetime.now().isoformat(timespec="seconds")},
                  f, ensure_ascii=False, indent=1)
    os.replace(tmp, _path(data_dir))


def last_info(data_dir):
    """(дата проверки «23.10.2026», источник) — для подписи под калькуляторами."""
    _p, data = load_saved(data_dir)
    try:
        when = dt.datetime.fromisoformat(data.get("checked", "")).strftime("%d.%m.%Y %H:%M")
    except ValueError:
        when = ""
    return when, data.get("source", "")


def describe(point):
    d, r = point
    return f"с {dt.date.fromisoformat(d).strftime('%d.%m.%Y')} — {str(r).rstrip('0').rstrip('.').replace('.', ',')}%"


def start(main, data_dir, log_error=None, interval_h=6):
    """Подставить сохранённое, затем в фоне спросить ЦБ; новая ставка — плашка внизу окна."""
    from PySide6.QtCore import QObject, QTimer, Signal

    saved, _ = load_saved(data_dir)
    if saved:
        apply(saved)

    class _Bridge(QObject):
        done = Signal(object, str)

    br = _Bridge(main)
    state = {"busy": False}

    def work():
        try:
            table, src = fetch()
        except Exception as e:                # на всякий случай: фон никогда не роняет программу
            table, src = None, repr(e)
        br.done.emit(table, src)

    def run():
        if state["busy"]:
            return
        state["busy"] = True
        threading.Thread(target=work, daemon=True, name="LH-keyrate").start()

    def finished(table, src):
        state["busy"] = False
        if not table:
            return                            # нет интернета или сайт не ответил — тихо, попробуем позже
        before = list(D.KEY_RATES)
        changed = apply(table)
        try:
            save(data_dir, list(D.KEY_RATES), src)
        except OSError:
            pass
        if changed:
            new = [p for p in D.KEY_RATES if p not in before]
            if new:
                text = "📈  Ключевая ставка ЦБ изменилась: " + "; ".join(describe(p) for p in new) + \
                       ". Калькуляторы уже считают по новой ставке."
                try:
                    main.msg(text, 15000)
                except Exception:
                    pass
        for cb in getattr(main, "_keyrate_listeners", []):
            try:
                cb()
            except Exception:
                pass

    br.done.connect(finished)
    QTimer.singleShot(5000, run)
    t = QTimer(main)
    t.setInterval(int(interval_h * 3600 * 1000))
    t.timeout.connect(run)
    t.start()
    main._keyrate = (br, t, run)
    return run
