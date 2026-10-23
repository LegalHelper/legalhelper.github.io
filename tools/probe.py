import re, sys, urllib.request, html
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
def get(u):
    r = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"}), timeout=30)
    return r.status, r.read().decode("utf-8", "replace")
docs = sys.argv[1:] or ["5142", "305", "37800", "10699", "39331"]
for d in docs:
    u = f"https://www.consultant.ru/document/cons_doc_LAW_{d}/"
    try:
        st, t = get(u)
    except Exception as e:
        print(d, "ERR", repr(e)); continue
    title = re.search(r"<title>(.*?)</title>", t, re.S)
    print("=====", d, st, len(t), "TITLE:", html.unescape(title.group(1)).strip()[:200] if title else None)
    for m in re.finditer(r"(?:ред\.|редакци\w*)[^<]{0,80}", t)[:0] if False else list(re.finditer(r"(?:ред\.|редакци\w*)[^<]{0,80}", t))[:6]:
        print("  ED:", html.unescape(m.group(0))[:120])
    anchors = re.findall(r'<a[^>]+href="([^"]+)"[^>]*>\s*(Статья\s+[\d.]+[^<]{0,120})</a>', t)
    print("  anchors:", len(anchors))
    for a in anchors[:5]: print("   ", a)
    rep = [a for a in anchors if re.search(r"(?i)утратил|исключен", a[1])]
    print("  repealed in anchors:", len(rep), rep[:5])
    raw = re.findall(r"Статья\s+[\d.]+\.[^<]{0,100}", t)
    print("  raw headings:", len(raw), raw[:3])
    i = t.find("Статья 395")
    if i > 0: print("  CTX395:", t[i-300:i+200].replace("\n", " "))
    if anchors:
        href = anchors[min(10, len(anchors)-1)][0]
        au = href if href.startswith("http") else "https://www.consultant.ru" + href
        st2, t2 = get(au)
        txt = re.sub(r"<[^>]+>", " ", t2); txt = re.sub(r"\s+", " ", html.unescape(txt))
        j = txt.find(anchors[min(10, len(anchors)-1)][1][:12])
        print("  ARTICLE", au, st2, len(t2), "| text:", txt[j:j+500] if j >= 0 else txt[:500])
