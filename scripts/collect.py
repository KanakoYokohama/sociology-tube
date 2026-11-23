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

    def get(self, endpoint, cost, **params):
        params["key"] = self.key
        url = API + endpoint + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                self.units += cost
                return json.load(r)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:500]
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

    def channels(self, ids):
        out = []
        for i in range(0, len(ids), 50):
            out += self.get("channels", 1, part="snippet,statistics",
                            id=",".join(ids[i:i + 50])).get("items", [])
        return out


# ---------------------------------------------------------------- 判定

JA_CHARS = re.compile(r"[぀-ヿ一-鿿]")


def detect_lang(text):
    return "ja" if JA_CHARS.search(text or "") else "en"


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

def collect(yt, today_d, now):
    videos = load_json(DATA / "videos.json", {})
    channels = load_json(DATA / "channels.json", {})
    after = (now - timedelta(days=config.SEARCH_WINDOW_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
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

    for vid, cats in found.items():
        v = videos.setdefault(vid, {"firstSeen": today, "categories": []})
        v["categories"] = sorted(set(v["categories"]) | cats)

    # 2) 追跡中の動画（投稿からTRACK_DAYS日以内）の数字を取る
    cutoff = now - timedelta(days=config.TRACK_DAYS)
    active = [vid for vid, v in videos.items()
              if "publishedAt" not in v or datetime.fromisoformat(v["publishedAt"].replace("Z", "+00:00")) >= cutoff]
    vrows = []
    for it in yt.videos(active):
        sn, st = it["snippet"], it.get("statistics", {})
        v = videos[it["id"]]
        text = sn.get("title", "") + "\n" + sn.get("description", "")[:600]
        cats = set(v["categories"]) | set(keyword_categories(text))
        v.update({
            "title": sn.get("title", ""),
            "channelId": sn["channelId"],
            "channelTitle": sn.get("channelTitle", ""),
            "publishedAt": sn["publishedAt"],
            "lang": detect_lang(sn.get("title", "")),
            "duration": parse_duration(it.get("contentDetails", {}).get("duration")),
            "categories": sorted(cats) or [config.OTHER_CATEGORY["id"]],
        })
        if len(v["categories"]) > 1 and config.OTHER_CATEGORY["id"] in v["categories"]:
            v["categories"].remove(config.OTHER_CATEGORY["id"])
        vrows.append({"date": today, "video_id": it["id"],
                      "views": st.get("viewCount", 0), "likes": st.get("likeCount", 0),
                      "comments": st.get("commentCount", 0)})

    # 3) そのチャンネルの登録者数などを取る
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
        }
        crows.append({"date": today, "channel_id": it["id"],
                      "subs": st.get("subscriberCount", 0), "views": st.get("viewCount", 0),
                      "videos": st.get("videoCount", 0)})

    save_json(DATA / "videos.json", videos, pretty=True)
    save_json(DATA / "channels.json", channels, pretty=True)
    vhist = upsert_daily(DATA / "video_daily.csv", ["date", "video_id", "views", "likes", "comments"], today, vrows)
    chist = upsert_daily(DATA / "channel_daily.csv", ["date", "channel_id", "subs", "views", "videos"], today, crows)
    return videos, channels, vhist, chist


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


def summarize(videos, channels, vhist, chist, today_d, now):
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
        if today not in s or vid not in videos or "title" not in videos[vid]:
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

    videos, channels, vhist, chist = collect(yt, today_d, now)
    summary = summarize(videos, channels, vhist, chist, today_d, now)
    summary["quotaUnits"] = yt.units
    save_json(SITE_DATA / "summary.json", summary)
    print(f"{today_d}: 動画 {summary['counts']['videos']} 本 / チャンネル {summary['counts']['channels']} 件 / "
          f"API使用量 {yt.units} ユニット（上限 10000/日）")


if __name__ == "__main__":
    main()
