"""収集の設定（2026-11-23 改訂）。分野・検索語・追跡期間はここを書き換えれば変わります。"""

# 何日前までに投稿された動画を「新しく探す」対象にするか
SEARCH_WINDOW_DAYS = 7
# 見つけた動画を何日間、毎日追跡するか
TRACK_DAYS = 30
# 1回の検索で取る件数（最大50）
RESULTS_PER_SEARCH = 50  # ショートを除外するぶん多めに取る（費用は同じ）

# 8分野。id は英字、name は画面に出る名前。
# queries: 検索語（日本語・英語）。keywords: タイトルや説明文での判定に使う語。
CATEGORIES = [
    {
        "id": "inequality",
        "name": "格差・貧困",
        "queries": {
            "ja": ["格差社会", "貧困 日本 社会"],
            "en": ["inequality sociology", "poverty society explained"],
        },
        "keywords": ["格差", "貧困", "階層", "階級", "生活保護", "低所得", "富裕層", "中流",
                     "inequality", "poverty", "social class", "wealth gap", "the poor", "homeless"],
    },
    {
        "id": "gender",
        "name": "ジェンダー",
        "queries": {
            "ja": ["ジェンダー 社会", "フェミニズム"],
            "en": ["gender sociology", "feminism society"],
        },
        "keywords": ["ジェンダー", "フェミニ", "男女", "女性差別", "男性学", "LGBT", "性別",
                     "gender", "feminis", "patriarchy", "masculinity", "women's", "sexism", "lgbt"],
    },
    {
        "id": "family",
        "name": "家族・結婚",
        "queries": {
            "ja": ["結婚 社会学", "少子化 家族"],
            "en": ["marriage sociology", "family decline birth rate"],
        },
        "keywords": ["結婚", "婚活", "離婚", "家族", "少子化", "出生率", "子育て", "未婚", "夫婦",
                     "marriage", "married", "divorce", "family", "birth rate", "fertility", "dating"],
    },
    {
        "id": "work",
        "name": "労働・働き方",
        "queries": {
            "ja": ["働き方 社会問題", "非正規雇用"],
            "en": ["work culture sociology", "work life society"],
        },
        "keywords": ["労働", "働き方", "非正規", "雇用", "賃金", "給料", "残業", "転職", "仕事",
                     "work", "labor", "labour", "job", "wage", "employment", "burnout", "career"],
    },
    {
        "id": "youth",
        "name": "教育・若者",
        "queries": {
            "ja": ["若者 社会 問題", "教育格差"],
            "en": ["gen z sociology", "education system problem"],
        },
        "keywords": ["若者", "Z世代", "教育", "学校", "受験", "大学", "学歴", "いじめ", "不登校",
                     "gen z", "youth", "young people", "education", "school", "college", "student"],
    },
    {
        "id": "aging",
        "name": "高齢化・地域",
        "queries": {
            "ja": ["高齢化 地方", "地方 過疎"],
            "en": ["aging society", "rural decline community"],
        },
        "keywords": ["高齢", "老後", "介護", "年金", "地方", "過疎", "地域", "田舎", "限界集落",
                     "aging", "ageing", "elderly", "retirement", "pension", "rural", "small town", "community"],
    },
    {
        "id": "migration",
        "name": "移民・多文化",
        "queries": {
            "ja": ["移民 日本", "外国人 共生"],
            "en": ["immigration sociology", "multicultural society"],
        },
        "keywords": ["移民", "外国人", "難民", "多文化", "共生", "在日", "国籍", "排外",
                     "immigra", "migrant", "refugee", "multicultural", "racism", "ethnic"],
    },
    {
        "id": "media",
        "name": "ネット文化・メディア",
        "queries": {
            "ja": ["SNS 社会 影響", "ネット文化 解説"],
            "en": ["internet culture explained", "social media society"],
        },
        "keywords": ["SNS", "ネット文化", "ネット社会", "炎上", "TikTok", "インフルエンサー", "メディア", "推し", "陰謀論",
                     "internet culture", "social media", "influencer", "tiktok", "algorithm", "loneliness"],
    },
]

# どの分野にも当てはめず「社会学全般」として探す検索語
GENERAL_QUERIES = {
    "ja": ["社会学", "ドキュメンタリー 社会", "特集 社会問題", "ドキュメンタリー 家族", "密着 暮らし", "ドキュメンタリー 孤独"],
    "en": ["sociology", "documentary society", "video essay society", "documentary family life",
           "documentary loneliness", "short documentary community"],
}

# 言語ごとの検索地域
REGION = {"ja": "JP", "en": "US"}

OTHER_CATEGORY = {"id": "other", "name": "その他・社会学全般"}

# どの分野にも当たらない動画は、これらの語がなければ「関係なし」として除外する
SOCIOLOGY_WORDS = ["社会学", "社会問題", "社会", "人間関係", "孤独", "共同体", "差別",
                   "sociolog", "society", "loneliness", "human connection"]


# ---------------------------------------------------------------- 除外

# この秒数以下の動画はショートとみなして除外（YouTubeのショートは最長3分）
MIN_DURATION_SEC = 181

# 煽り判定。タイトル・チャンネル名に含まれる語に点数をつけ、合計が
# SENSATIONAL_THRESHOLD 以上なら除外する。報道機関チャンネルは判定しない。
SENSATIONAL_THRESHOLD = 2
SENSATIONAL_WORDS = {
    # 1語で除外（2点）
    2: ["暴露", "論破", "ド正論", "痛烈", "嘲笑", "発狂", "ブチギレ", "ブチ切れ", "完全終了", "ざまぁ",
        "公開処刑", "撃沈", "売国", "反日", "媚中", "在日特権", "許せない", "絶句", "フルボッコ", "痛快",
        "一刀両断", "黙らせ", "ボコボコ", "大炎上", "ヤバすぎ", "やばすぎ", "悲報", "朗報",
        "DESTROYS", "DESTROYED", "OWNED", "HUMBLED", "TRIGGERED", "MELTDOWN", "MELTS DOWN",
        "SHUTS DOWN", "GOES OFF", "EPIC", "SHOCKING", "LIBS", "WOKE",
        "delusional", "brainwashed", "heated debate", "fact check", "humiliat", "red pill", "redpill",
        "gets schooled", "meltdown", "2ch", "2ちゃん", "ガルちゃん", "レスバ", "スカッと",
        "都市伝説", "予言", "REACTS", "Parasite", "Beyond Sad"],
    # 2語そろうと除外（1点）
    1: ["衝撃", "ヤバい", "やばい", "ヤバ", "炎上", "激怒", "呆れ", "爆笑", "末路", "闇", "斬る", "本音",
        "怒り", "正論", "称賛", "批判殺到", "ｗ", "www", "残酷", "絶望", "地獄", "ガチ", "マジで", "罠",
        "口コミ", "限界突破",
        "EXPOSED", "INSANE", "CRAZY", "BROKE", "RANT", "SLAMS", "CLAPBACK"],
}
# チャンネル名にこれが入っていたら除外（切り抜き・まとめ系）
SENSATIONAL_CHANNEL_WORDS = ["切り抜き", "切り抜", "国会中継", "ネットの話題", "まとめ", "スカッと", "Clips", "clips",
                             "ガルちゃん", "2ch", "口コミ", "物申"]


# ---------------------------------------------------------------- 報道機関

# 各国の報道機関・ドキュメンタリーチャンネル。新着動画（最大50本）から、8分野のどれかに
# 当てはまるか、ドキュメンタリー・密着の語を含む3分超の動画を「報道特集」として拾う。@ハンドル名で指定。
NEWS_CHANNELS = {
    "ja": ["@nhk", "@NHKWORLDJAPAN", "@tbsnewsdig", "@ntv_news", "@ANNnewsCH",
           "@FNNnewsCH", "@asahicom", "@mainichi", "@KyodoNews", "@toyokeizai"],
    "en": ["@BBCNews", "@BBCWorldService", "@DWDocumentary", "@dwnews", "@aljazeeraenglish",
           "@PBSNewsHour", "@frontline", "@Vox", "@guardiannews", "@nytimes",
           "@washingtonpost", "@CNAInsider", "@Channel4News", "@60minutes", "@CBCNews",
           "@abcnewsindepth", "@VICENews", "@NPR", "@AJPlus", "@RealStories", "@NHKWORLDDocumentary"],
}


# ---------------------------------------------------------------- 語り口

# 語り口の分類（1本が複数に入ることもある）。どれにも当たらなければ「その他」。
STYLES = [
    {"id": "first_person", "name": "一人称・体験談",
     "words": ["私", "あたし", "僕", "わたし", "体験", "実体験", "経験談", "した話", "私の", "人生", "生き方", "エッセイ", "語る",
               "my ", "i'm", "i've", "why i ", "how i ", "i was", "personal", "my story", "my life", "essay"]},
    {"id": "case", "name": "当事者・密着",
     "words": ["インタビュー", "当事者", "密着", "ドキュメンタリー", "暮らし", "取材", "実態", "素顔", "日常", "に聞く",
               "documentary", "interview", "living with", "life of", "day in the life", "we live", "lives of", "my life as"]},
    {"id": "explainer", "name": "解説・講義",
     "words": ["解説", "講義", "社会学者", "教授", "専門家", "研究", "データで", "わかりやすく", "なぜ起きる",
               "explained", "explainer", "lecture", "professor", "sociologist", "research", "analysis", "the science of"]},
]
NEWS_STYLE = {"id": "news", "name": "報道特集"}
OTHER_STYLE = {"id": "other", "name": "その他"}

# 問いかけ型のタイトル
QUESTION_WORDS = ["なぜ", "どうして", "とは", "？", "?", "のか", "べきか",
                  "why ", "what ", "how ", "is it", "should ", "can we", "do we"]


# ---------------------------------------------------------------- 本に近い動画

# 本に近い動画＝テーマは問わず、「一人称・体験談」か「当事者・密着」の語り口を持つ動画。
# 判定に使う語は上の STYLES と QUESTION_WORDS を共用。


# ---------------------------------------------------------------- 政治・経済を少し減らす

# タイトルにこれらの語が POLITICS_THRESHOLD 個以上あれば除外（報道機関も対象）。
# 「少しだけ離れる」ための弱めの設定。強めたいときは THRESHOLD を1に。
POLITICS_THRESHOLD = 2
POLITICS_WORDS = [
    # 政治
    "自民党", "立憲", "維新", "公明", "共産党", "国民民主", "参政党", "れいわ", "社民党", "首相", "総理", "石破",
    "高市", "岸田", "国会", "選挙", "衆院", "参院", "政権", "内閣", "議員", "政治家", "野党", "与党", "政府",
    "Trump", "Biden", "Harris", "Vance", "Congress", "Senate", "Republican", "Democrat", "GOP", "election",
    "parliament", "MAGA", "White House", "prime minister", "president", "大統領", "首脳", "外交",
    "minister", "民主党", "共和党", "votes", "Pentagon", "Kremlin", "NATO", "military", "軍事", "防衛",
    # 経済・お金
    "投資", "株価", "NISA", "資産運用", "資産形成", "節約", "円安", "物価高", "日経平均", "為替", "金利",
    "年収アップ", "副業", "不動産", "経済", "税金", "増税", "減税",
    "stock", "invest", "crypto", "bitcoin", "interest rate", "inflation", "recession", "the Fed", "GDP",
    "tariff", "economy", "taxes",
]
