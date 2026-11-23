"""収集の設定。分野・検索語・追跡期間はここを書き換えれば変わります。"""

# 何日前までに投稿された動画を「新しく探す」対象にするか
SEARCH_WINDOW_DAYS = 7
# 見つけた動画を何日間、毎日追跡するか
TRACK_DAYS = 30
# 1回の検索で取る件数（最大50）
RESULTS_PER_SEARCH = 25

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
            "en": ["work culture sociology", "labor workers economy"],
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
        "keywords": ["SNS", "ネット", "炎上", "YouTube", "TikTok", "インフルエンサー", "メディア", "推し", "陰謀論",
                     "internet culture", "social media", "influencer", "tiktok", "algorithm", "loneliness"],
    },
]

# どの分野にも当てはめず「社会学全般」として探す検索語
GENERAL_QUERIES = {
    "ja": ["社会学"],
    "en": ["sociology"],
}

# 言語ごとの検索地域
REGION = {"ja": "JP", "en": "US"}

OTHER_CATEGORY = {"id": "other", "name": "その他・社会学全般"}
