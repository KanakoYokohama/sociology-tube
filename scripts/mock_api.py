"""動作確認用の偽YouTube API。本番では使いません。"""
import hashlib
import random
from datetime import datetime, timedelta, timezone

EPOCH = datetime(2026, 10, 1, tzinfo=timezone.utc)

JA_TITLES = ["【暴露】移民賛成派がヤバすぎる理由 #日本 #政治 #自民党", "私が友情結婚を選んだ理由｜夫婦のリアルな暮らし", "格差はどこから生まれる？", "非正規で働く30代のリアル",
             "地方が消える日", "SNSが孤独を深める理由", "ジェンダー平等は進んだのか",
             "外国人労働者と日本の未来", "教育格差の正体", "老後2000万円問題その後", "推し活の社会学"]
EN_TITLES = ["Feminist DESTROYED by Student!!", "Why I Chose a Platonic Marriage | Our Life Documentary", "The Death of the Middle Class", "Why Nobody Wants Kids Anymore",
             "Small Towns Are Dying", "Is Feminism Winning?", "The Truth About Immigration",
             "Burnout Culture Explained", "How Algorithms Shape Society", "The Retirement Crisis", "College Isn't Worth It"]


def h(s):
    return int(hashlib.md5(s.encode()).hexdigest(), 16)


class MockYouTube:
    def __init__(self, now):
        self.now = now
        self.units = 0

    def _video(self, n):
        vid = f"vid{n:05d}xx"[:11]
        r = random.Random(n)
        ja = n % 2 == 0
        titles = JA_TITLES if ja else EN_TITLES
        pub = EPOCH + timedelta(hours=n * 7)
        ch = r.randrange(12)
        if n % 7 == 0:
            ch = 99
        return vid, {
            "title": titles[n % 10] + ("" if n < 10 else f" #{n}"),
            "ja": ja, "pub": pub, "ch": f"UCmock{'ja' if ja else 'en'}{ch:02d}",
            "base": r.choice([2_000, 8_000, 30_000, 120_000, 500_000]),
            "short": r.random() < 0.2,
            "news": n % 7 == 0,
        }

    def _all(self):
        n = 0
        while True:
            vid, v = self._video(n)
            if v["pub"] > self.now:
                return
            yield n, vid, v
            n += 1

    def search(self, q, lang, after):
        self.units += 100
        a = datetime.fromisoformat(after.replace("Z", "+00:00"))
        hits = [(vid, v) for _, vid, v in self._all()
                if v["pub"] >= a and v["ja"] == (lang == "ja") and h(vid + q) % 5 == 0]
        r = random.Random(h(q + self.now.date().isoformat()))
        r.shuffle(hits)
        return [{"id": {"videoId": vid}} for vid, _ in hits[:8]]

    def videos(self, ids):
        self.units += -(-len(ids) // 50)
        lookup = {vid: v for _, vid, v in self._all()}
        out = []
        for vid in ids:
            v = lookup.get(vid)
            if not v:
                continue
            age = max((self.now - v["pub"]).total_seconds() / 86400, 0)
            views = int(v["base"] * (1 - 0.6 ** (age + 0.3)) * (1 + 0.02 * age))
            out.append({
                "id": vid,
                "snippet": {"title": v["title"], "description": "家族と結婚について取材しました" if v["ja"] else "An interview about family and marriage",
                            "channelId": v["ch"],
                            "channelTitle": v["ch"].replace("UCmock", "チャンネル"),
                            "publishedAt": v["pub"].strftime("%Y-%m-%dT%H:%M:%SZ")},
                "statistics": {"viewCount": str(views), "likeCount": str(views // 30),
                               "commentCount": str(views // 400)},
                "contentDetails": {"duration": "PT58S" if v["short"] else "PT14M20S"},
            })
        return out

    def channel_by_handle(self, handle):
        self.units += 1
        if handle in ("@nhk", "@BBCNews"):
            ja = handle == "@nhk"
            return {"id": f"UCmock{'ja' if ja else 'en'}99", "snippet": {"title": handle[1:]},
                    "contentDetails": {"relatedPlaylists": {"uploads": "UU" + handle}}}
        return None

    def uploads(self, playlist_id):
        self.units += 1
        ja = "nhk" in playlist_id
        out = []
        for _, vid, v in self._all():
            if v["news"] and v["ja"] == ja:
                out.append({"snippet": {"title": v["title"], "description": "結婚 家族 family marriage",
                                        "publishedAt": v["pub"].strftime("%Y-%m-%dT%H:%M:%SZ")},
                            "contentDetails": {"videoId": vid,
                                               "videoPublishedAt": v["pub"].strftime("%Y-%m-%dT%H:%M:%SZ")}})
        return out[-50:]

    def channels(self, ids):
        self.units += -(-len(ids) // 50)
        out = []
        for ch in ids:
            r = random.Random(h(ch))
            base = r.choice([5_000, 40_000, 150_000, 900_000])
            days = (self.now - EPOCH).days
            subs = int(base * (1 + r.uniform(0, 0.004) * days))
            out.append({"id": ch,
                        "snippet": {"title": ch.replace("UCmock", "チャンネル"), "customUrl": "@" + ch.lower(),
                                    "country": "JP" if "ja" in ch else "US", "thumbnails": {}},
                        "statistics": {"subscriberCount": str(subs), "viewCount": str(subs * 120),
                                       "videoCount": str(200 + days)}})
        return out
