import re, sys, urllib.request, html, time
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
def get(u, to=120):
    r = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"}), timeout=to)
    return r.status, r.read().decode("utf-8", "replace")
docs = sys.argv[1:]
first_art = None
for d in docs:
    u = f"https://www.consultant.ru/document/cons_doc_LAW_{d}/"
    t0 = time.time()
    try:
        st, t = get(u)
    except Exception as e:
        print(d, "ERR", repr(e), round(time.time()-t0)); continue
    title = re.search(r"<title>(.*?)</title>", t, re.S)
    ed = re.search(r"ред\.\s*от\s*(\d\d\.\d\d\.\d{4})", t)
    anchors = re.findall(r'<a[^>]+href="([^"]+)"[^>]*>\s*(Стать[яи]\s+[\d.]+[^<]{0,160})</a>', t)
    rep = [a[1] for a in anchors if re.search(r"(?i)утратил|исключен", a[1])]
    print(d, st, round(time.time()-t0), "s |", html.unescape(title.group(1)).strip()[:110] if title else None, "| ed", ed.group(1) if ed else None, "| arts", len(anchors), "| repealed", len(rep), rep[:3])
    if first_art is None and anchors:
        first_art = anchors[min(20, len(anchors)-1)]
    time.sleep(2)
if first_art:
    au = "https://www.consultant.ru" + first_art[0]
    try:
        st2, t2 = get(au)
        txt = re.sub(r"(?s)<script.*?</script>|<style.*?</style>", " ", t2)
        txt = re.sub(r"<[^>]+>", "\n", txt); txt = re.sub(r"\n\s*\n+", "\n", html.unescape(txt))
        j = txt.find(first_art[1][:14])
        print("ARTICLE", au, st2, len(t2)); print(txt[max(0,j-300):j+2500])
    except Exception as e:
        print("ARTICLE ERR", repr(e))
