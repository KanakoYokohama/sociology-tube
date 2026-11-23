"""社会学系YouTube動画の毎日の記録と集計。

使い方:
  YOUTUBE_API_KEY=xxxx python scripts/collect.py        # 本番（YouTube Data API）
  python scripts/collect.py --mock --date 2026-11-23   # 動作確認用の偽データ

外部ライブラリは使わず、Python標準ライブラリだけで動きます。
"""
import argparse
import csv
import json
import os
import re
import statistics
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"            # 生データ（履歴）
SITE_DATA = ROOT / "docs" / "data"  # 画面が読むデータ
JST = timezone(timedelta(hours=9))
API = "https://www.googleapis.com/youtube/v3/"

CAT_NAMES = {c["id"]: c["name"] for c in config.CATEGORIES}
CAT_NAMES[config.OTHER_CATEGORY["id"]] = config.OTHER_CATEGORY["name"]


# ---------------------------------------------------------------- API

class YouTube:
    def __init__(self, key):
        self.key = key
        self.units = 0

    def get(self, endpoint, cost, allow_fail=False, **params):
        params["key"] = self.key
        url = API + endpoint + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                self.units += cost
                return json.load(r)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:500]
            self.units += cost
            if allow_fail and e.code in (400, 404):
                print(f"  スキップ: {endpoint} {params.get('forHandle') or params.get('playlistId')} ({e.code})")
                return {}
            raise SystemExit(f"YouTube APIエラー {e.code} ({endpoint}): {body}")

    def search(self, q, lang, published_after):
        return self.get(
            "search", 100, part="snippet", type="video", q=q,
            order="viewCount", maxResults=config.RESULTS_PER_SEARCH,
            publishedAfter=published_after, relevanceLanguage=lang,
            regionCode=config.REGION[lang],
        ).get("items", [])

    def videos(self, ids):
        out = []
        for i in range(0, len(ids), 50):
            out += self.get("videos", 1, part="snippet,statistics,contentDetails",
                            id=",".join(ids[i:i + 50])).get("items", [])
        return out

    def channel_by_handle(self, handle):
        items = self.get("channels", 1, allow_fail=True, part="snippet,contentDetails",
                         forHandle=handle).get("items", [])
        return items[0] if items else None

    def uploads(self, playlist_id):
        return self.get("playlistItems", 1, allow_fail=True, part="snippet,contentDetails",
                        playlistId=playlist_id, maxResults=50).get("items", [])

    def channels(self, ids):
        out = []
        for i in range(0, len(ids), 50):
            out += self.get("channels", 1, part="snippet,statistics",
                            id=",".join(ids[i:i + 50])).get("items", [])
        return out


# ---------------------------------------------------------------- 判定

KANA = re.compile("[぀-ヿ]")
HAN = re.compile("[一-鿿]")
# キリル・ハングル・デーヴァナーガリー・タイ・アラビア・ベンガル〜タミル
OTHER_SCRIPTS = re.compile("[Ѐ-ӿ가-힯ऀ-ॿ฀-๿؀-ۿঀ-௿]")
LATIN = re.compile("[A-Za-z]")


def detect_lang(snippet):
    """日本語ならja、英語ならen、それ以外（中国語・韓国語・ロシア語など）はother。"""
    title = snippet.get("title", "") or ""
    desc = (snippet.get("description", "") or "")[:300]
    audio = (snippet.get("defaultAudioLanguage") or snippet.get("defaultLanguage") or "").lower()
    if audio.startswith("ja"):
        return "ja"
    if KANA.search(title):
        return "ja"
    if OTHER_SCRIPTS.search(title) or HAN.search(title):
        return "other"  # 漢字だけでかなが見当たらない＝中国語とみなす
    if audio and not audio.startswith("en"):
        return "other"
    if OTHER_SCRIPTS.search(desc):
        return "other"
    return "en" if len(LATIN.findall(title)) >= 5 else "other"


def keyword_categories(text):
    text_l = (text or "").lower()
    found = []
    for c in config.CATEGORIES:
        for kw in c["keywords"]:
            k = kw.lower()
            if k.isascii():
                hit = re.search(r"(?<![a-z])" + re.escape(k), text_l)
            else:
                hit = k in text_l
            if hit:
                found.append(c["id"])
                break
    return found


def _count_words(text, words):
    hits = []
    for w in words:
        if w.isascii() and w.isupper():
            if re.search(r"(?<![A-Za-z])" + re.escape(w) + r"(?![A-Za-z])", text):
                hits.append(w)
        elif w.lower() in text.lower():
            hits.append(w)
    return hits


def sensational_score(title, channel):
    """煽り度の点数と、当たった理由。"""
    score, why = 0, []
    for pts, words in config.SENSATIONAL_WORDS.items():
        for w in _count_words(title, words):
            score += pts
            why.append(w)
    for w in config.SENSATIONAL_CHANNEL_WORDS:
        if w in channel:
            score += 2
            why.append("ch:" + w)
    caps = [w for w in re.findall(r"[A-Za-z']+", title) if len(w) >= 3 and w.isupper()]
    if len(caps) >= 3:
        score += 1
        why.append("大文字")
    if title.count("!") + title.count("！") >= 2:
        score += 1
        why.append("！！")
    tags = re.findall(r"#\S+", title)
    if len(tags) >= 3:
        score += 1
        why.append("#多数")
    if any(p in title for p in ["#自民党", "#立憲", "#参政党", "#維新", "#国民民主", "#石破", "#高市", "#MAGA", "#Trump"]):
        score += 1
        why.append("#政党")
    return score, why


def text_hits(text, words):
    t = (text or "").lower()
    out = []
    for w in words:
        k = w.lower()
        if k.isascii() and k.strip().isalpha():
            if re.search(r"(?<![a-z])" + re.escape(k.strip()) + r"(?![a-z])", t):
                out.append(w.strip())
        elif k in t:
            out.append(w.strip())
    return out


def styles_of(v):
    text = v.get("title", "") + "\n" + v.get("description", "")
    out = []
    if v.get("news"):
        out.append(config.NEWS_STYLE["id"])
    for st in config.STYLES:
        if text_hits(text, st["words"]):
            out.append(st["id"])
    return out or [config.OTHER_STYLE["id"]]


def book_match(v):
    """本の書き方（一人称の語り＋当事者の事例＋社会への問い）に近いか。テーマは問わない。
    「一人称・体験談」か「当事者・密着」に当たれば近いとし、当たった要素を返す。"""
    text = v.get("title", "") + "\n" + v.get("description", "")
    st = {s["id"]: text_hits(text, s["words"]) for s in config.STYLES}
    if not (st["first_person"] or st["case"]):
        return None
    question = bool(text_hits(v.get("title", ""), config.QUESTION_WORDS))
    score = 2 * bool(st["first_person"]) + 2 * bool(st["case"]) + bool(st["explainer"]) + question
    return {"firstPerson": st["first_person"][:3], "case": st["case"][:3],
            "explainer": bool(st["explainer"]), "question": question, "score": score}


def parse_duration(iso):
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


# ---------------------------------------------------------------- 保存

def load_json(path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def save_json(path, obj, pretty=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1 if pretty else None,
                               separators=None if pretty else (",", ":")), encoding="utf-8")


def upsert_daily(path, fields, today, rows):
    """同じ日付の行は置き換え、それ以外は残す（1日に何度実行しても重複しない）。"""
    old = []
    if path.exists():
        with path.open(encoding="utf-8") as f:
            old = [r for r in csv.DictReader(f) if r["date"] != today]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(old)
        w.writerows(rows)
    return old + rows


# ---------------------------------------------------------------- 収集

DOC_WORDS = ["ドキュメンタリー", "ドキュメント", "密着", "documentary", "docuseries", "in-depth", "special report"]


def resolve_news_channels(yt):
    """報道機関の@ハンドルをチャンネルIDとアップロード一覧に変換（結果は保存して再利用）。"""
    cache = load_json(DATA / "news_channels.json", {})
    for lang, handles in config.NEWS_CHANNELS.items():
        for hd in handles:
            if hd in cache:
                continue
            it = yt.channel_by_handle(hd)
            if it:
                cache[hd] = {"id": it["id"], "title": it["snippet"].get("title", ""), "lang": lang,
                             "uploads": it["contentDetails"]["relatedPlaylists"]["uploads"]}
            else:
                cache[hd] = {"id": None, "lang": lang, "notFound": True}
    save_json(DATA / "news_channels.json", cache, pretty=True)
    return cache


def collect(yt, today_d, now):
    videos = load_json(DATA / "videos.json", {})
    channels = load_json(DATA / "channels.json", {})
    after_dt = now - timedelta(days=config.SEARCH_WINDOW_DAYS)
    after = after_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    today = today_d.isoformat()

    # 1) 分野ごとに検索して新しい動画を見つける
    found = {}  # video_id -> set(categories)
    jobs = []
    for c in config.CATEGORIES:
        for lang, qs in c["queries"].items():
            for q in qs:
                jobs.append((c["id"], lang, q))
    for lang, qs in config.GENERAL_QUERIES.items():
        for q in qs:
            jobs.append((None, lang, q))
    for cat, lang, q in jobs:
        for it in yt.search(q, lang, after):
            vid = it["id"].get("videoId")
            if vid:
                found.setdefault(vid, set())
                if cat:
                    found[vid].add(cat)

    # 2) 報道機関の新着から、8分野に当てはまる動画を拾う
    news = resolve_news_channels(yt)
    news_ids = {n["id"] for n in news.values() if n.get("id")}
    for n in news.values():
        if not n.get("uploads"):
            continue
        for it in yt.uploads(n["uploads"]):
            sn = it["snippet"]
            pub = it.get("contentDetails", {}).get("videoPublishedAt") or sn.get("publishedAt", "")
            if not pub or datetime.fromisoformat(pub.replace("Z", "+00:00")) < after_dt:
                continue
            text = sn.get("title", "") + "\n" + (sn.get("description") or "")[:600]
            cats = keyword_categories(text)
            doc = text_hits(text, DOC_WORDS)
            if cats or doc:
                vid = it["contentDetails"]["videoId"]
                found.setdefault(vid, set()).update(cats)

    for vid, cats in found.items():
        v = videos.setdefault(vid, {"firstSeen": today, "searchCats": []})
        if "searchCats" not in v:  # 旧形式からの移行
            v["searchCats"] = [c for c in v.get("categories", []) if c != config.OTHER_CATEGORY["id"]]
        v["searchCats"] = sorted(set(v["searchCats"]) | cats)

    # 3) 追跡中の動画（投稿からTRACK_DAYS日以内）の数字を取る
    cutoff = now - timedelta(days=config.TRACK_DAYS)
    active = [vid for vid, v in videos.items()
              if not v.get("excluded") and
              ("publishedAt" not in v or datetime.fromisoformat(v["publishedAt"].replace("Z", "+00:00")) >= cutoff)]
    vrows = []
    for it in yt.videos(active):
        sn, st = it["snippet"], it.get("statistics", {})
        v = videos[it["id"]]
        v.setdefault("searchCats", [c for c in v.get("categories", []) if c != config.OTHER_CATEGORY["id"]])
        title, desc = sn.get("title", ""), (sn.get("description", "") or "")[:600]
        duration = parse_duration(it.get("contentDetails", {}).get("duration"))
        is_news = sn["channelId"] in news_ids
        v.update({"title": title, "description": desc[:500], "channelId": sn["channelId"],
                  "channelTitle": sn.get("channelTitle", ""), "publishedAt": sn["publishedAt"],
                  "duration": duration, "news": is_news})
        # 除外の判定
        lang = detect_lang(sn)
        if lang == "other":
            v["excluded"] = "language"
        elif duration < config.MIN_DURATION_SEC or "#shorts" in (title + desc).lower():
            v["excluded"] = "short"
        elif not is_news:
            score, why = sensational_score(title, sn.get("channelTitle", ""))
            if score >= config.SENSATIONAL_THRESHOLD:
                v["excluded"] = "sensational"
                v["sensational"] = why
        if not v.get("excluded"):
            pol = text_hits(title, config.POLITICS_WORDS)
            if len(pol) >= config.POLITICS_THRESHOLD:
                v["excluded"] = "politics"
                v["politics"] = pol
        if v.get("excluded"):
            continue
        cats = set(v["searchCats"]) | set(keyword_categories(title + "\n" + desc))
        v["lang"] = lang
        v["categories"] = sorted(cats) or [config.OTHER_CATEGORY["id"]]
        vrows.append({"date": today, "video_id": it["id"],
                      "views": st.get("viewCount", 0), "likes": st.get("likeCount", 0),
                      "comments": st.get("commentCount", 0)})

    # 4) そのチャンネルの登録者数などを取る
    ch_ids = sorted({videos[r["video_id"]]["channelId"] for r in vrows})
    crows = []
    for it in yt.channels(ch_ids):
        sn, st = it["snippet"], it.get("statistics", {})
        channels[it["id"]] = {
            "title": sn.get("title", ""),
            "handle": sn.get("customUrl", ""),
            "country": sn.get("country", ""),
            "thumb": sn.get("thumbnails", {}).get("default", {}).get("url", ""),
            "hiddenSubs": bool(st.get("hiddenSubscriberCount")),
            "news": it["id"] in news_ids,
        }
        crows.append({"date": today, "channel_id": it["id"],
                      "subs": st.get("subscriberCount", 0), "views": st.get("viewCount", 0),
                      "videos": st.get("videoCount", 0)})

    save_json(DATA / "videos.json", videos, pretty=True)
    save_json(DATA / "channels.json", channels, pretty=True)
    vhist = upsert_daily(DATA / "video_daily.csv", ["date", "video_id", "views", "likes", "comments"], today, vrows)
    chist = upsert_daily(DATA / "channel_daily.csv", ["date", "channel_id", "subs", "views", "videos"], today, crows)
    return videos, channels, vhist, chist, news


# ---------------------------------------------------------------- 集計

def series(rows, key_field, value_field):
    out = {}
    for r in rows:
        out.setdefault(r[key_field], {})[r["date"]] = int(float(r[value_field] or 0))
    return out


def value_on_or_before(s, day):
    """day以前で最も近い日の値。なければNone。"""
    best = None
    for d in sorted(s):
        if d <= day:
            best = s[d]
    return best


def median(xs):
    return statistics.median(xs) if xs else None


def summarize(videos, channels, vhist, chist, today_d, now, news=None):
    today = today_d.isoformat()
    d1 = (today_d - timedelta(days=1)).isoformat()
    d7 = (today_d - timedelta(days=7)).isoformat()
    d30 = (today_d - timedelta(days=30)).isoformat()
    vviews = series(vhist, "video_id", "views")
    vlikes = series(vhist, "video_id", "likes")
    vcomments = series(vhist, "video_id", "comments")
    csubs = series(chist, "channel_id", "subs")
    cviews = series(chist, "channel_id", "views")

    # 動画ごとの指標
    vlist = []
    for vid, s in vviews.items():
        if today not in s or vid not in videos or "title" not in videos[vid] or videos[vid].get("excluded"):
            continue
        v = videos[vid]
        pub = datetime.fromisoformat(v["publishedAt"].replace("Z", "+00:00"))
        age_days = max((now - pub).total_seconds() / 86400, 0.25)
        views = s[today]
        prev = value_on_or_before(s, d1)
        gain24 = views - prev if prev is not None else None
        ch = v["channelId"]
        subs = value_on_or_before(csubs.get(ch, {}), today) or 0
        vlist.append({
            "id": vid,
            "title": v["title"],
            "channelId": ch,
            "channel": v.get("channelTitle", ""),
            "publishedAt": v["publishedAt"],
            "lang": v.get("lang", "en"),
            "duration": v.get("duration", 0),
            "short": 0 < v.get("duration", 0) <= 180,
            "categories": v["categories"],
            "views": views,
            "likes": vlikes.get(vid, {}).get(today, 0),
            "comments": vcomments.get(vid, {}).get(today, 0),
            "gain24h": gain24,
            "viewsPerDay": round(views / age_days),
            "ageDays": round(age_days, 1),
            "subs": subs,
            "viewsPerSub": round(views / subs, 2) if subs else None,
            "trend": [s.get((today_d - timedelta(days=i)).isoformat()) for i in range(13, -1, -1)],
            "news": bool(v.get("news")),
            "styles": styles_of(v),
            "question": bool(text_hits(v["title"], config.QUESTION_WORDS)),
            "book": book_match(v),
        })

    # 「今日伸びた」順：前日比があればそれ。初めて見つけた動画は、
    # 投稿1日以内なら総再生数（＝ほぼ24時間の伸び）、それ以外は1日あたり再生数で代用
    def growth_key(x):
        if x["gain24h"] is not None:
            return x["gain24h"]
        return x["views"] if x["ageDays"] <= 1 else x["viewsPerDay"]

    top = sorted(vlist, key=growth_key, reverse=True)

    # チャンネルごとの指標
    clist = []
    for ch, s in csubs.items():
        if today not in s or ch not in channels:
            continue
        subs = s[today]
        s7 = value_on_or_before(s, d7)
        s30 = value_on_or_before(s, d30)
        first_day = min(s)
        vs = cviews.get(ch, {})
        v7 = value_on_or_before(vs, d7)
        tracked = [x for x in vlist if x["channelId"] == ch]
        clist.append({
            "id": ch,
            "title": channels[ch]["title"],
            "handle": channels[ch].get("handle", ""),
            "thumb": channels[ch].get("thumb", ""),
            "hiddenSubs": channels[ch].get("hiddenSubs", False),
            "lang": tracked[0]["lang"] if tracked else "",
            "subs": subs,
            "subsGain7d": subs - s7 if s7 is not None else None,
            "subsGain30d": subs - s30 if s30 is not None else None,
            "subsGrowth7dPct": round((subs - s7) / s7 * 100, 2) if s7 else None,
            "viewsGain7d": vs.get(today, 0) - v7 if v7 is not None else None,
            "since": first_day,
            "trackedVideos": len(tracked),
            "categories": sorted({c for x in tracked for c in x["categories"]}),
            "bestVideo": max(tracked, key=growth_key)["id"] if tracked else None,
            "trend": [s.get((today_d - timedelta(days=i)).isoformat()) for i in range(29, -1, -1)],
        })
    clist.sort(key=lambda c: (c["subsGain7d"] if c["subsGain7d"] is not None else -1, c["subs"]), reverse=True)

    # 分野ごとの伸びやすさ
    cat_ids = [c["id"] for c in config.CATEGORIES] + [config.OTHER_CATEGORY["id"]]
    cats = []
    top_ids = {x["id"] for x in top[:20]}
    for cid in cat_ids:
        xs = [x for x in vlist if cid in x["categories"]]
        long_xs = [x for x in xs if not x["short"]]
        gains = [x["gain24h"] for x in xs if x["gain24h"] is not None]
        ratios = [x["viewsPerSub"] for x in xs if x["viewsPerSub"] is not None]
        # 分野全体の1日あたり増加数（過去14日）
        daily = []
        for i in range(13, -1, -1):
            d = (today_d - timedelta(days=i)).isoformat()
            dp = (today_d - timedelta(days=i + 1)).isoformat()
            tot, n = 0, 0
            for x in xs:
                s = vviews[x["id"]]
                if d in s and dp in s:
                    tot += s[d] - s[dp]
                    n += 1
            daily.append(tot if n else None)
        cats.append({
            "id": cid,
            "name": CAT_NAMES[cid],
            "videos": len(xs),
            "channels": len({x["channelId"] for x in xs}),
            "jaShare": round(sum(1 for x in xs if x["lang"] == "ja") / len(xs), 2) if xs else None,
            "medianViewsPerDay": median([x["viewsPerDay"] for x in xs]),
            "medianViewsPerDayLong": median([x["viewsPerDay"] for x in long_xs]),
            "medianGain24h": median(gains),
            "totalGain24h": sum(gains) if gains else None,
            "medianViewsPerSub": median(ratios),
            "inTop20": len([x for x in xs if x["id"] in top_ids]),
            "daily": daily,
        })
    cats.sort(key=lambda c: c["medianViewsPerDay"] or -1, reverse=True)

    # 語り口ごとの伸びやすさ
    def stats(xs):
        gains = [x["gain24h"] for x in xs if x["gain24h"] is not None]
        ratios = [x["viewsPerSub"] for x in xs if x["viewsPerSub"] is not None]
        return {"videos": len(xs), "medianViewsPerDay": median([x["viewsPerDay"] for x in xs]),
                "medianGain24h": median(gains), "medianViewsPerSub": median(ratios),
                "inTop20": len([x for x in xs if x["id"] in top_ids])}

    style_defs = [config.NEWS_STYLE] + config.STYLES + [config.OTHER_STYLE]
    styles = [{"id": d["id"], "name": d["name"], **stats([x for x in vlist if d["id"] in x["styles"]])}
              for d in style_defs]
    styles.sort(key=lambda c: c["medianViewsPerDay"] or -1, reverse=True)
    question = [{"id": "q", "name": "問いかけ型タイトル", **stats([x for x in vlist if x["question"]])},
                {"id": "nq", "name": "それ以外", **stats([x for x in vlist if not x["question"]])}]

    # 本に近い動画
    book_list = sorted([x for x in vlist if x["book"]], key=growth_key, reverse=True)
    book = {
        "videos": book_list[:30],
        "compare": [
            {"id": "match", "name": "本に近い語り口", **stats(book_list)},
            {"id": "rest", "name": "それ以外の語り口", **stats([x for x in vlist if not x["book"]])},
        ],
        "signals": [
            {"id": "fp", "name": "一人称・体験談あり", **stats([x for x in book_list if x["book"]["firstPerson"]])},
            {"id": "case", "name": "当事者・密着あり", **stats([x for x in book_list if x["book"]["case"]])},
            {"id": "both", "name": "両方あり", **stats([x for x in book_list if x["book"]["firstPerson"] and x["book"]["case"]])},
            {"id": "q", "name": "問いかけ型タイトル", **stats([x for x in book_list if x["book"]["question"]])},
            {"id": "ex", "name": "解説・考察も含む", **stats([x for x in book_list if x["book"]["explainer"]])},
        ],
    }

    # 除外した動画の数（追跡期間内に投稿されたもの）
    cutoff = now - timedelta(days=config.TRACK_DAYS)
    excluded = {}
    for v in videos.values():
        if v.get("excluded") and "publishedAt" in v and \
                datetime.fromisoformat(v["publishedAt"].replace("Z", "+00:00")) >= cutoff:
            excluded[v["excluded"]] = excluded.get(v["excluded"], 0) + 1

    news = news or {}
    days_recorded = len({r["date"] for r in vhist})
    return {
        "updatedAt": now.astimezone(JST).isoformat(timespec="minutes"),
        "date": today,
        "daysRecorded": days_recorded,
        "trackDays": config.TRACK_DAYS,
        "categoryNames": CAT_NAMES,
        "top": top[:50],
        "channels": clist[:100],
        "categories": cats,
        "counts": {"videos": len(vlist), "channels": len(clist)},
        "styles": styles,
        "question": question,
        "book": book,
        "excluded": excluded,
        "newsChannels": {"found": sorted(n.get("title", h) for h, n in news.items() if n.get("id")),
                         "notFound": sorted(h for h, n in news.items() if not n.get("id"))},
    }


# ---------------------------------------------------------------- 実行

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true", help="偽データで動作確認")
    ap.add_argument("--date", help="記録日（YYYY-MM-DD、JST）。省略時は今日")
    args = ap.parse_args()

    if args.date:
        today_d = date.fromisoformat(args.date)
        now = datetime(today_d.year, today_d.month, today_d.day, 12, 0, tzinfo=timezone.utc)
    else:
        now = datetime.now(timezone.utc)
        today_d = now.astimezone(JST).date()

    if args.mock:
        from mock_api import MockYouTube
        yt = MockYouTube(now)
    else:
        key = os.environ.get("YOUTUBE_API_KEY")
        if not key:
            raise SystemExit("YOUTUBE_API_KEY が設定されていません")
        yt = YouTube(key)

    videos, channels, vhist, chist, news = collect(yt, today_d, now)
    summary = summarize(videos, channels, vhist, chist, today_d, now, news)
    summary["quotaUnits"] = yt.units
    save_json(SITE_DATA / "summary.json", summary)
    print(f"{today_d}: 動画 {summary['counts']['videos']} 本 / チャンネル {summary['counts']['channels']} 件 / "
          f"API使用量 {yt.units} ユニット（上限 10000/日）")


if __name__ == "__main__":
    main()
