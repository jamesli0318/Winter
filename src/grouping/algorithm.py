"""Rule-based algorithmic clustering for K-pop fan tweets.

Three phases:
1. classify_tweet  — assign EventCategory based on account_type + keywords
2. cluster_tweets  — greedy single-pass clustering by similarity
3. generate_event_name / generate_summary — build Chinese event metadata
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from src.grouping.models import Event, EventCategory
from src.twitter.models import AccountType, RawTweet

# ---------------------------------------------------------------------------
# Phase 1: Classification
# ---------------------------------------------------------------------------

# Keyword → category scoring dictionaries (covers KR / CN / JP / EN)
CATEGORY_KEYWORDS: dict[EventCategory, list[str]] = {
    EventCategory.SCHEDULE: [
        # Korean
        "공항", "출국", "입국", "녹화", "인기가요", "음악중심", "엠카운트다운",
        "뮤직뱅크", "음악방송", "쇼챔피언", "더쇼", "콘서트", "팬미팅",
        "리허설", "사전녹화", "본방사수", "출근", "퇴근",
        # English
        "airport", "musicbank", "music bank", "inkigayo", "mcountdown",
        "m countdown", "music core", "show champion", "the show",
        "concert", "fanmeeting", "fan meeting", "rehearsal", "prerecording",
        "pre-recording", "fansign", "fan sign",
        # Chinese
        "行程", "活動", "機場", "出發", "到達", "錄影", "音樂節目",
        "演唱會", "粉絲見面會", "簽售",
    ],
    EventCategory.MEDIA: [
        # Korean
        "화보", "매거진", "잡지", "광고", "CF", "영상",
        # English
        "magazine", "photoshoot", "photo shoot", "pictorial", "interview",
        "mv", "music video", "teaser", "behind", "making",
        "commercial", "brand", "ambassador", "endorsement", "campaign",
        # Chinese
        "雜誌", "畫報", "拍攝", "廣告", "代言", "影片", "預告",
        # Japanese
        "写真", "撮影",
    ],
    EventCategory.NEWS: [
        # Korean
        "차트", "판매", "스트리밍", "1위", "신기록",
        # English
        "chart", "sales", "streaming", "billboard", "spotify",
        "record", "milestone", "breaking", "announce", "announcement",
        "debut", "comeback", "release",
        # Chinese
        "排行", "數據", "銷量", "串流", "紀錄", "突破",
    ],
    EventCategory.SNS: [
        # Korean
        "인스타", "위버스", "버블",
        # English
        "instagram", "weverse", "bubble", "selfie", "selca",
        "update", "post",
        # Chinese
        "貼文", "動態", "自拍", "更新",
    ],
}

# Pre-compile patterns (case-insensitive) for each category
_CATEGORY_PATTERNS: dict[EventCategory, re.Pattern] = {
    cat: re.compile("|".join(re.escape(kw) for kw in kws), re.IGNORECASE)
    for cat, kws in CATEGORY_KEYWORDS.items()
}

# Default categories per account type when no keyword matches
_DEFAULT_CATEGORY: dict[AccountType, EventCategory] = {
    AccountType.OFFICIAL: EventCategory.SNS,
    AccountType.FANSITE: EventCategory.SCHEDULE,
    AccountType.TRANSLATOR: EventCategory.SNS,
    AccountType.NEWS: EventCategory.NEWS,
    AccountType.OTHER: EventCategory.NEWS,
}


def classify_tweet(tweet: RawTweet) -> EventCategory:
    """Assign an EventCategory based on account_type and keyword scoring."""
    # OFFICIAL always SNS
    if tweet.account_type == AccountType.OFFICIAL:
        return EventCategory.SNS

    text = tweet.text
    if tweet.quoted_text:
        text += " " + tweet.quoted_text

    scores: dict[EventCategory, int] = {}
    for cat, pattern in _CATEGORY_PATTERNS.items():
        matches = pattern.findall(text)
        if matches:
            scores[cat] = len(matches)

    if scores:
        return max(scores, key=scores.get)  # type: ignore[arg-type]

    return _DEFAULT_CATEGORY.get(tweet.account_type, EventCategory.NEWS)


# ---------------------------------------------------------------------------
# Phase 2: Clustering
# ---------------------------------------------------------------------------

# Generic hashtags to ignore during comparison
_GENERIC_TAGS = {
    "aespa", "에스파", "winter", "윈터", "김민정", "kimminjung",
    "sm", "smentertainment", "kpop", "smtown",
}

_HASHTAG_RE = re.compile(r"#(\w+)", re.UNICODE)
_URL_RE = re.compile(r"https?://\S+")
_MENTION_RE = re.compile(r"@\w+")

# Music show Korean name → Traditional Chinese mapping
SHOW_NAME_MAP: dict[str, str] = {
    "인기가요": "人氣歌謠",
    "음악중심": "音樂中心",
    "엠카운트다운": "M Countdown",
    "뮤직뱅크": "Music Bank",
    "쇼챔피언": "Show Champion",
    "더쇼": "The Show",
    "뮤직뱅크": "Music Bank",
    "콘서트": "演唱會",
    "팬미팅": "粉絲見面會",
}


@dataclass
class TweetFeatures:
    tweet: RawTweet
    category: EventCategory
    hashtags: set[str] = field(default_factory=set)
    keywords: set[str] = field(default_factory=set)
    media_urls: set[str] = field(default_factory=set)


def extract_features(tweet: RawTweet, category: EventCategory) -> TweetFeatures:
    """Extract clustering features from a tweet."""
    text = tweet.text
    if tweet.quoted_text:
        text += " " + tweet.quoted_text

    # Hashtags (lowered, minus generic)
    raw_tags = {t.lower() for t in _HASHTAG_RE.findall(text)}
    hashtags = raw_tags - _GENERIC_TAGS

    # Matched keywords from the tweet's category
    kw_set: set[str] = set()
    for cat, pattern in _CATEGORY_PATTERNS.items():
        for m in pattern.finditer(text):
            kw_set.add(m.group().lower())

    return TweetFeatures(
        tweet=tweet,
        category=category,
        hashtags=hashtags,
        keywords=kw_set,
        media_urls=set(tweet.media_urls),
    )


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


def _time_diff_hours(a: datetime, b: datetime) -> float:
    return abs((a - b).total_seconds()) / 3600


@dataclass
class _Cluster:
    features: list[TweetFeatures] = field(default_factory=list)
    category: EventCategory = EventCategory.NEWS
    all_hashtags: set[str] = field(default_factory=set)
    all_keywords: set[str] = field(default_factory=set)
    all_media: set[str] = field(default_factory=set)
    earliest: datetime | None = None
    latest: datetime | None = None

    def add(self, feat: TweetFeatures) -> None:
        self.features.append(feat)
        self.category = feat.category
        self.all_hashtags |= feat.hashtags
        self.all_keywords |= feat.keywords
        self.all_media |= feat.media_urls
        t = feat.tweet.created_at
        if self.earliest is None or t < self.earliest:
            self.earliest = t
        if self.latest is None or t > self.latest:
            self.latest = t


def _cluster_similarity(feat: TweetFeatures, cluster: _Cluster) -> float:
    """Compute similarity between a tweet and a cluster."""
    # Different category → never merge
    if feat.category != cluster.category:
        return 0.0

    # Time gap check against cluster's time range
    t = feat.tweet.created_at
    gap_hours = min(
        _time_diff_hours(t, cluster.earliest),  # type: ignore[arg-type]
        _time_diff_hours(t, cluster.latest),  # type: ignore[arg-type]
    )
    if gap_hours > 6:
        return 0.0

    score = 0.0

    # Time proximity (linear decay, max +0.2)
    score += 0.2 * max(0.0, 1.0 - gap_hours / 6.0)

    # Hashtag overlap (strongest signal, max +0.4)
    score += 0.4 * _jaccard(feat.hashtags, cluster.all_hashtags)

    # Keyword overlap (max +0.25)
    score += 0.25 * _jaccard(feat.keywords, cluster.all_keywords)

    # Shared media URL (max +0.3)
    if feat.media_urls & cluster.all_media:
        score += 0.3

    # Quote chain: if this tweet quotes (or is quoted by) a tweet in cluster
    if feat.tweet.is_quote and feat.tweet.quoted_text:
        for cf in cluster.features:
            if feat.tweet.quoted_text in cf.tweet.text or cf.tweet.text in feat.tweet.quoted_text:
                score += 0.5
                break

    return score


_MERGE_THRESHOLD = 0.3


def cluster_tweets(
    tweets: list[RawTweet],
    categories: dict[str, EventCategory],
) -> list[_Cluster]:
    """Greedy single-pass clustering sorted by created_at."""
    sorted_tweets = sorted(tweets, key=lambda t: t.created_at)
    clusters: list[_Cluster] = []

    for tweet in sorted_tweets:
        cat = categories[tweet.tweet_id]
        feat = extract_features(tweet, cat)

        # Special rule: OFFICIAL non-quote tweets each get their own cluster
        if tweet.account_type == AccountType.OFFICIAL and not tweet.is_quote:
            c = _Cluster()
            c.add(feat)
            clusters.append(c)
            continue

        # Find best matching cluster
        best_score = 0.0
        best_cluster: _Cluster | None = None
        for c in clusters:
            s = _cluster_similarity(feat, c)
            if s > best_score:
                best_score = s
                best_cluster = c

        if best_score >= _MERGE_THRESHOLD and best_cluster is not None:
            best_cluster.add(feat)
        else:
            c = _Cluster()
            c.add(feat)
            clusters.append(c)

    return clusters


# ---------------------------------------------------------------------------
# Phase 3: Naming & Summary
# ---------------------------------------------------------------------------

# Category suffixes for event naming
_CATEGORY_SUFFIX: dict[EventCategory, str] = {
    EventCategory.SCHEDULE: "出演",
    EventCategory.MEDIA: "更新",
    EventCategory.SNS: "更新",
    EventCategory.NEWS: "新聞",
}


def generate_event_name(cluster: _Cluster) -> str:
    """Generate a Traditional Chinese event name from cluster hashtags."""
    # Collect meaningful hashtags (already stripped of generic ones)
    tags = cluster.all_hashtags

    # Check for Korean music show names → map to Chinese
    for kr_name, cn_name in SHOW_NAME_MAP.items():
        if kr_name in tags or kr_name.lower() in tags:
            suffix = _CATEGORY_SUFFIX.get(cluster.category, "更新")
            return f"{cn_name}{suffix}"
        # Also check in keywords
        for kw in cluster.all_keywords:
            if kr_name in kw or kr_name.lower() == kw:
                suffix = _CATEGORY_SUFFIX.get(cluster.category, "更新")
                return f"{cn_name}{suffix}"

    # Use the most common non-generic hashtag
    if tags:
        # Pick the tag shared by the most tweets
        tag_counts: dict[str, int] = {}
        for feat in cluster.features:
            for t in feat.hashtags:
                tag_counts[t] = tag_counts.get(t, 0) + 1
        if tag_counts:
            best_tag = max(tag_counts, key=tag_counts.get)  # type: ignore[arg-type]
            suffix = _CATEGORY_SUFFIX.get(cluster.category, "更新")
            return f"{best_tag} {suffix}"

    # No hashtags: use first 15 chars of highest-engagement tweet
    if cluster.features:
        best_tweet = max(
            cluster.features,
            key=lambda f: f.tweet.like_count + f.tweet.retweet_count,
        )
        text = _clean_text(best_tweet.tweet.text)
        if text:
            truncated = text[:15].strip()
            if len(text) > 15:
                truncated += "..."
            return truncated

    # Final fallback
    cat_name = cluster.category.value
    return f"{cat_name} 更新"


def generate_summary(cluster: _Cluster) -> str:
    """Generate a short Traditional Chinese summary."""
    # Pick representative tweet: prefer TRANSLATOR > OFFICIAL > highest engagement
    features = cluster.features
    representative: TweetFeatures | None = None

    for priority_type in (AccountType.TRANSLATOR, AccountType.OFFICIAL):
        for f in features:
            if f.tweet.account_type == priority_type:
                representative = f
                break
        if representative:
            break

    if not representative:
        representative = max(
            features,
            key=lambda f: f.tweet.like_count + f.tweet.retweet_count,
        )

    text = _clean_text(representative.tweet.text)
    n = len(features)

    if len(text) > 80:
        text = text[:80].strip() + "..."

    if n > 1:
        text += f"（{n}則推文報導）"

    return text


def _clean_text(text: str) -> str:
    """Remove @mentions, URLs, and excess hashtags from text."""
    text = _MENTION_RE.sub("", text)
    text = _URL_RE.sub("", text)
    # Remove hashtags but keep the word if it's informative
    text = re.sub(r"#(\w+)", r"\1", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_algorithm(tweets: list[RawTweet]) -> list[Event]:
    """Execute the full 3-phase pipeline: classify → cluster → name/summarize."""
    if not tweets:
        return []

    # Phase 1: classify each tweet
    categories: dict[str, EventCategory] = {}
    for t in tweets:
        categories[t.tweet_id] = classify_tweet(t)

    # Phase 2: cluster
    clusters = cluster_tweets(tweets, categories)

    # Phase 3: build Event objects
    url_map = {t.tweet_id: t.url for t in tweets}
    events: list[Event] = []

    for cluster in clusters:
        name = generate_event_name(cluster)
        summary = generate_summary(cluster)
        tweet_ids = [f.tweet.tweet_id for f in cluster.features]
        tweet_urls = [url_map[tid] for tid in tweet_ids if tid in url_map]

        events.append(Event(
            name=name,
            category=cluster.category,
            summary=summary,
            tweet_ids=tweet_ids,
            tweet_urls=tweet_urls,
            earliest_time=cluster.earliest,
        ))

    return events
