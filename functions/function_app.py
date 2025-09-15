import json
import os
from typing import Any, Dict, List, Optional, Tuple

import azure.functions as func
from pydantic import BaseModel, Field, ValidationError, conint, constr
import base64
import httpx
from urllib.parse import quote_plus
from datetime import datetime, timedelta
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
from azure.cosmos import CosmosClient, PartitionKey


# Pydantic Schemas (minimal; align with spec)

class SearchYouTubeReq(BaseModel):
    age: conint(ge=0, le=15)
    cefr: constr(strip_whitespace=True)
    characters: List[str] = Field(default_factory=list)
    max: conint(ge=1, le=50) = 10


class VideoItem(BaseModel):
    id: str
    title: str
    channel: str
    url: str
    durationSec: int
    hasCaptions: bool
    thumbnail: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class IndexVideoReq(BaseModel):
    videoUrl: str


class IndexVideoResp(BaseModel):
    transcriptId: str
    lang: str
    wordCounts: Dict[str, int]
    segments: List[Dict[str, Any]]


class RankVideoReq(BaseModel):
    transcriptId: str
    cefr: str


class RankVideoResp(BaseModel):
    score: float
    reasons: List[str]


class ExtractTopWordsReq(BaseModel):
    transcriptId: str
    count: conint(ge=1, le=10) = 5
    cefr: str


class WordEntry(BaseModel):
    word: str
    pos: str
    cefr: str
    definition: Optional[str] = None
    ipa: Optional[str] = None
    audioUrl: Optional[str] = None


class ExampleSentenceReq(BaseModel):
    word: str
    cefr: str
    context: Dict[str, str] = Field(default_factory=dict)


class ExampleSentenceResp(BaseModel):
    sentence: str


class UpdateProgressReq(BaseModel):
    childId: str
    videoId: str
    learnedWords: List[str]
    quizScore: Optional[int] = Field(default=None, ge=0, le=100)
    durationSec: conint(ge=0)


class UpdateProgressResp(BaseModel):
    ok: bool
    newLevel: Optional[str] = None
    streak: Optional[int] = None


class ComputeLevelReq(BaseModel):
    childId: str


class ComputeLevelResp(BaseModel):
    cefr: str
    confidence: float
    deltas: Dict[str, int] = Field(default_factory=dict)


class FindLocalAcademiesReq(BaseModel):
    address: str
    radiusMeters: conint(gt=0) = 3000
    tags: Optional[List[str]] = None
    topK: conint(gt=0, le=25) = 10


class AcademyItem(BaseModel):
    name: str
    phone: Optional[str] = None
    address: str
    mapUrl: Optional[str] = None
    distanceM: Optional[int] = None


class SearchAcademiesReq(BaseModel):
    region: str
    query: Optional[str] = None
    topK: conint(gt=0, le=25) = 5


@app.route(route="tools/search_academies_ai", methods=["POST"])
def search_academies_ai(req: func.HttpRequest) -> func.HttpResponse:
    try:
        payload = SearchAcademiesReq.model_validate_json(req.get_body())
    except ValidationError as ve:
        return _bad_request(ve.json())

    ep = os.getenv("AZURE_SEARCH_ENDPOINT")
    key = os.getenv("AZURE_SEARCH_API_KEY")
    index = os.getenv("AZURE_SEARCH_INDEX", "kidsenglish")
    if not (ep and key and index):
        return _ok([])

    headers = {"api-key": key}
    search_text = (payload.query or "english academy kids") + " " + (payload.region or "")
    params = {
        "api-version": os.getenv("AZURE_SEARCH_API_VERSION", "2023-11-01").strip(),
        "search": search_text,
        "$top": int(payload.topK),
        "queryType": "simple",
    }
    url = f"{ep}/indexes/{index}/docs"
    items: List[Dict[str, Any]] = []
    try:
        with httpx.Client(timeout=10) as client:
            r = client.get(url, params=params, headers=headers)
            r.raise_for_status()
            data = r.json() or {}
            for d in data.get("value", [])[: int(payload.topK)]:
                name = d.get("name") or d.get("title") or d.get("academy") or "Academy"
                addr = d.get("address") or d.get("addr") or payload.region
                phone = d.get("phone") or d.get("tel") or None
                lat = d.get("lat") or d.get("latitude")
                lon = d.get("lon") or d.get("longitude")
                map_url = None
                if lat is not None and lon is not None:
                    map_url = f"https://www.bing.com/maps?cp={lat}~{lon}"
                items.append(
                    AcademyItem(
                        name=name,
                        phone=phone,
                        address=addr,
                        mapUrl=map_url,
                        distanceM=None,
                    ).model_dump()
                )
    except Exception:
        items = []

    return _ok(items)


class PlayCheerReq(BaseModel):
    voice: constr(strip_whitespace=True) = "child"
    style: constr(strip_whitespace=True) = "cheerful"


class PlayCheerResp(BaseModel):
    audioUrl: str


class ParentReportReq(BaseModel):
    childId: str
    period: constr(strip_whitespace=True) = "7d"


class ParentReportResp(BaseModel):
    summaryText: str
    kpis: Dict[str, Any]
    chartData: Dict[str, Any]


class SayWordReq(BaseModel):
    word: str
    voice: Optional[str] = None  # e.g., en-US-AvaNeural
    style: Optional[str] = None


class SayWordResp(BaseModel):
    audioUrl: Optional[str] = None  # data URL
    audioB64: Optional[str] = None
    contentType: Optional[str] = None


class ExtractExpressionsReq(BaseModel):
    transcriptId: str
    count: conint(ge=1, le=5) = 3
    cefr: Optional[str] = None


class ExtractExpressionsResp(BaseModel):
    phrases: List[str]


class SaveProfileReq(BaseModel):
    childId: str
    name: str
    age: conint(ge=0, le=15)
    region: str
    study: str
    characters: List[str] = Field(default_factory=list)
    cefr: str
    interest: Optional[int] = Field(default=None, ge=1, le=5)


class SaveProfileResp(BaseModel):
    ok: bool
    storedId: Optional[str] = None


class LoadProfileReq(BaseModel):
    childId: str


class LoadProfileResp(BaseModel):
    ok: bool
    profile: Optional[Dict[str, Any]] = None


app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)



def _ok(data: Any, status_code: int = 200) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps(data, ensure_ascii=False),
        status_code=status_code,
        mimetype="application/json",
    )


def _bad_request(err: str) -> func.HttpResponse:
    return _ok({"error": err}, 400)


@app.route(route="tools/search_youtube_videos", methods=["POST"])
def search_youtube_videos(req: func.HttpRequest) -> func.HttpResponse:
    try:
        payload = SearchYouTubeReq.model_validate_json(req.get_body())
    except ValidationError as ve:
        return _bad_request(ve.json())

    yt_key = os.getenv("YOUTUBE_API_KEY")

    # Age-based recommendation rules (configurable via env AGE_RECO_RULES)
    def load_age_rules() -> Dict[str, Dict[str, Any]]:
        """Load age buckets from env JSON or return sane defaults.

        Structure example:
        {
          "3-5": {"durationMaxSec": 360, "keywords": [...], "channels": [...], "avoid": [...]},
          "6-8": {...},
        }
        """
        raw = os.getenv("AGE_RECO_RULES")
        if raw:
            try:
                data = json.loads(raw)
                if isinstance(data, dict):
                    return data
            except Exception:
                pass
        # Defaults tuned for age-appropriate content
        return {
            "0-3": {
                "durationMaxSec": 5 * 60,
                "keywords": [
                    "nursery rhymes",
                    "lullaby",
                    "hand play",
                    "sensory music",
                ],
                "channels": [
                    "Cocomelon",
                    "Super Simple Songs",
                    "Baby Einstein",
                    "Hey Duggee",
                    "Pocoyo",
                    "Shaun the Sheep",
                ],
                "avoid": ["prank", "horror", "challenge"],
            },
            "4-6": {
                "durationMaxSec": 6 * 60,
                "keywords": [
                    "simple dialogue",
                    "phonics",
                    "everyday english",
                    "kids story",
                ],
                "channels": [
                    "Peppa Pig",
                    "Bluey",
                    "Ben & Holly's Little Kingdom",
                    "Thomas & Friends",
                    "Octonauts",
                    "Alphablocks",
                    "Numberblocks",
                ],
                "avoid": ["prank", "horror", "challenge"],
            },
            "7-9": {
                "durationMaxSec": 12 * 60,
                "keywords": [
                    "kids science",
                    "story for kids",
                    "basic social studies",
                    "animals vocabulary",
                ],
                "channels": [
                    "Wild Kratts",
                    "The Magic School Bus",
                    "Odd Squad",
                    "Hilda",
                    "Carmen Sandiego",
                ],
                "avoid": ["prank", "horror"],
            },
            "10-12": {
                "durationMaxSec": 18 * 60,
                "keywords": [
                    "science for kids",
                    "history for kids",
                    "english comprehension",
                    "a2 english",
                ],
                "channels": [
                    "Crash Course Kids",
                    "TED-Ed",
                ],
                "avoid": ["prank", "horror"],
            },
            "13-15": {
                "durationMaxSec": 18 * 60,
                "keywords": [
                    "intermediate english for kids",
                    "short stories b1",
                    "news for kids",
                ],
                "channels": [
                    "BBC Newsround",
                ],
                "avoid": ["prank", "horror"],
            },
        }

    def pick_age_bucket(age: int, rules: Dict[str, Dict[str, Any]]) -> Tuple[str, Dict[str, Any]]:
        for k, v in rules.items():
            try:
                a, b = [int(x) for x in k.split("-")]
                if a <= age <= b:
                    return k, v
            except Exception:
                continue
        # Fallback to widest bucket
        return "6-8", rules.get("6-8", {})

    # Helper: map some common Korean character names to English to improve hits
    def norm_characters(chars: List[str]) -> List[str]:
        mapping = {
            "블루이": "Bluey",
            "뽀로로": "Pororo",
            "페파 피그": "Peppa Pig",
            "피카츄": "Pikachu",
            "포켓몬": "Pokemon",
            "핑크퐁": "Pinkfong",
        }
        out = []
        for c in (chars or []):
            out.append(c)
            if c in mapping:
                out.append(mapping[c])
        return list(dict.fromkeys([s for s in out if s]))

    def level_keywords(cefr: str) -> List[str]:
        table = {
            "PREA1": ["phonics", "alphabet", "kids song", "nursery rhymes", "abc", "colors", "animals"],
            "A1": ["basic", "easy english", "kids english", "simple sentences", "sight words"],
            "A2": ["everyday english", "simple story", "short story", "english for kids a2"],
            "B1": ["intermediate", "story for kids", "learn english b1"],
        }
        return table.get(cefr or "A1", table["A1"])

    def duration_ok(age: int, dur: int) -> bool:
        # Age-based duration guardrails from rules
        rules = load_age_rules()
        _, bucket = pick_age_bucket(age, rules)
        max_sec = int(bucket.get("durationMaxSec", 12 * 60))
        return dur <= max_sec

    def score_item(item: Dict[str, Any], chars: List[str], cefr: str, age: int) -> float:
        title = (item.get("title") or "").lower()
        channel = (item.get("channel") or "").lower()
        dur = int(item.get("durationSec") or 0)
        # Character match boost
        cm = 0.0
        for c in chars:
            c_low = c.lower()
            if c_low and (c_low in title or c_low in channel):
                cm = 1.0
                break
        # Level keyword match
        kw = level_keywords(cefr)
        lm = 0.0
        for k in kw:
            k_low = k.lower()
            if k_low in title:
                lm = 1.0
                break
        # Age-preferred channels/keywords
        rules = load_age_rules()
        _, bucket = pick_age_bucket(age, rules)
        pref_channels = [c.lower() for c in bucket.get("channels", [])]
        age_keys = [k.lower() for k in bucket.get("keywords", [])]
        avoid = [k.lower() for k in bucket.get("avoid", [])]
        ch_boost = 1.0 if any(pc in channel for pc in pref_channels if pc) else 0.0
        age_kw = 1.0 if any(ak and ak in title for ak in age_keys) else 0.0
        bad = 1.0 if any(av and av in title for av in avoid) else 0.0
        # Duration preference (within age band)
        ds = 1.0 if duration_ok(age, dur) else 0.2
        # Captions bonus
        cap = 1.0 if item.get("hasCaptions") else 0.0
        # Final score weights
        base = 0.35 * cm + 0.25 * lm + 0.15 * ds + 0.05 * cap
        base += 0.15 * ch_boost + 0.10 * age_kw
        # Penalize avoid keywords
        if bad:
            base -= 0.25
        return base

    def _duration_to_seconds(iso_dur: str) -> int:
        # Minimal ISO8601 duration parser for YouTube (e.g., PT4M5S)
        if not iso_dur or not iso_dur.startswith("P"):
            return 0
        import re
        m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso_dur)
        if not m:
            return 0
        h, m_, s = m.groups()
        h = int(h) if h else 0
        m_ = int(m_) if m_ else 0
        s = int(s) if s else 0
        return h * 3600 + m_ * 60 + s

    if yt_key:
        try:
            chars = norm_characters(payload.characters) or ["kids"]
            # Age bucket driven keywords
            rules = load_age_rules()
            _, bucket = pick_age_bucket(int(payload.age), rules)
            age_kw = bucket.get("keywords", [])
            # Build multiple queries to widen recall, later we re-rank
            base_qs = []
            # character + age keyword
            if age_kw:
                base_qs.append(" ".join([chars[0], age_kw[0], "english"]))
            # character + generic learn english
            base_qs.append(" ".join([chars[0], "kids video", "learn english"]))
            # cefr derived
            base_qs.append(" ".join(["kids english", *level_keywords(payload.cefr)[:1]]))
            # preferred channel specific query (bias to channel)
            pref_channels = (bucket.get("channels") or [])
            if pref_channels:
                base_qs.append(" ".join([pref_channels[0], "kids", "english"]))
            params = {
                "key": yt_key,
                "q": base_qs[0],
                "maxResults": 10,
                "type": "video",
                "safeSearch": "strict",
                "videoCaption": "closedCaption",
                "videoEmbeddable": "true",
                "relevanceLanguage": "en",
            }
            with httpx.Client(timeout=12) as client:
                all_ids: List[str] = []
                for qi, q in enumerate(base_qs):
                    p = dict(params)
                    p["q"] = q
                    sr = client.get("https://www.googleapis.com/youtube/v3/search", params=p)
                    if sr.status_code != 200:
                        continue
                    sdata = sr.json()
                    all_ids.extend([item["id"]["videoId"] for item in sdata.get("items", []) if item.get("id", {}).get("videoId")])
                ids = list(dict.fromkeys(all_ids))[:15]
                if not ids:
                    return _ok([])
                vr = client.get(
                    "https://www.googleapis.com/youtube/v3/videos",
                    params={
                        "key": yt_key,
                        "id": ",".join(ids),
                        "part": "snippet,contentDetails,status",
                    },
                )
                vr.raise_for_status()
                vdata = vr.json()
                raw: List[Dict[str, Any]] = []
                for it in vdata.get("items", []):
                    vid = it.get("id")
                    sn = it.get("snippet", {})
                    cd = it.get("contentDetails", {})
                    if not vid:
                        continue
                    title = sn.get("title", "")
                    channel = sn.get("channelTitle", "")
                    thumbs = (sn.get("thumbnails") or {}).get("high") or (sn.get("thumbnails") or {}).get("default") or {}
                    dur = _duration_to_seconds(cd.get("duration", ""))
                    has_cap = (cd.get("caption") == "true")
                    raw.append(
                        VideoItem(
                            id=vid,
                            title=title,
                            channel=channel,
                            url=f"https://www.youtube.com/watch?v={vid}",
                            durationSec=dur,
                            hasCaptions=has_cap,
                            thumbnail=thumbs.get("url"),
                            tags=list(set([payload.cefr] + payload.characters)),
                        ).model_dump()
                    )
                # Filter and rank according to age/CEFR/characters
                filtered = [r for r in raw if duration_ok(int(payload.age), int(r.get("durationSec") or 0))]
                chars_norm = norm_characters(payload.characters)
                ranked = sorted(filtered, key=lambda x: score_item(x, chars_norm, payload.cefr, int(payload.age)), reverse=True)
                return _ok(ranked[: int(payload.max)])
        except Exception:
            # fall through to stub
            pass

    # Fallback stub if no API key or error
    use_char = (payload.characters[:1] or ["Pikachu"])[0]
    age = int(payload.age)
    if age <= 5:
        title = f"{use_char} ABC phonics song"
        vid = "JY8cXbeAY3Y"
        dur = 180
    elif age <= 8:
        title = f"{use_char} simple story for A1"
        vid = "J---aiyznGQ"
        dur = 360
    else:
        title = f"{use_char} science for kids (A2)"
        vid = "3JZ_D3ELwOQ"
        dur = 540
    sample = [
        VideoItem(
            id=vid,
            title=title,
            channel="Kids Channel",
            url=f"https://www.youtube.com/watch?v={vid}",
            durationSec=dur,
            hasCaptions=True,
            thumbnail=f"https://img.youtube.com/vi/{vid}/hqdefault.jpg",
            tags=[payload.cefr, use_char],
        ).model_dump()
    ]
    return _ok(sample[: payload.max])


@app.route(route="tools/index_video", methods=["POST"])
def index_video(req: func.HttpRequest) -> func.HttpResponse:
    try:
        payload = IndexVideoReq.model_validate_json(req.get_body())
    except ValidationError as ve:
        return _bad_request(ve.json())

    # TODO: Fetch captions or run Video Indexer; push segments to Azure AI Search
    resp = IndexVideoResp(
        transcriptId="tx_" + str(abs(hash(payload.videoUrl)) % 10_000_000),
        lang="en",
        wordCounts={"forest": 3, "brave": 2, "climb": 4},
        segments=[{"t0": 0, "t1": 12, "text": "Hello friends"}],
    )
    return _ok(resp.model_dump())


@app.route(route="tools/rank_video_by_level", methods=["POST"])
def rank_video_by_level(req: func.HttpRequest) -> func.HttpResponse:
    try:
        payload = RankVideoReq.model_validate_json(req.get_body())
    except ValidationError as ve:
        return _bad_request(ve.json())

    # TODO: Estimate difficulty via CEFR lists + Zipf + classifier
    resp = RankVideoResp(score=0.72, reasons=[f"Matches {payload.cefr}", "Short sentences"])
    return _ok(resp.model_dump())


@app.route(route="tools/extract_top_words", methods=["POST"])
def extract_top_words(req: func.HttpRequest) -> func.HttpResponse:
    try:
        payload = ExtractTopWordsReq.model_validate_json(req.get_body())
    except ValidationError as ve:
        return _bad_request(ve.json())

    # TODO: Frequency × pedagogical value × novelty; exclude known words via WordMastery
    words = [
        WordEntry(word="forest", pos="noun", cefr="A1", definition="a large area of trees"),
        WordEntry(word="climb", pos="verb", cefr="A1", definition="go up something"),
        WordEntry(word="brave", pos="adj", cefr="A2", definition="showing no fear"),
    ]
    return _ok([w.model_dump() for w in words[: payload.count]])


@app.route(route="tools/extract_top_expressions", methods=["POST"])
def extract_top_expressions(req: func.HttpRequest) -> func.HttpResponse:
    try:
        payload = ExtractExpressionsReq.model_validate_json(req.get_body())
    except ValidationError as ve:
        return _bad_request(ve.json())

    aoai_ep = os.getenv("AZURE_OPENAI_ENDPOINT")
    aoai_key = os.getenv("AZURE_OPENAI_API_KEY")
    aoai_dep = os.getenv("AZURE_OPENAI_DEPLOYMENT")
    aoai_ver = os.getenv("AZURE_OPENAI_API_VERSION", "2024-06-01")

    phrases: List[str] = []
    if aoai_ep and aoai_key and aoai_dep:
        sys = (
            "You are a kids' English tutor. From a children's video transcript,"
            " extract short, high-frequency everyday expressions useful for kids."
            " Return ONLY a JSON array of distinct phrases, each 2–5 words,"
            " kid-appropriate, simple, reusable."
        )
        user = (
            f"transcriptId: {payload.transcriptId}\n"
            f"count: {int(payload.count)}\n"
            "If transcript not available, output common phrases for kids."
        )
        chat_url = f"{aoai_ep}/openai/deployments/{aoai_dep}/chat/completions?api-version={aoai_ver}"
        headers = {"api-key": aoai_key, "Content-Type": "application/json"}
        body = {"messages": [{"role": "system", "content": sys}, {"role": "user", "content": user}], "temperature": 0.2, "response_format": {"type": "json_object"}}
        try:
            with httpx.Client(timeout=15) as client:
                r = client.post(chat_url, headers=headers, json=body)
                r.raise_for_status()
                data = r.json()
                content = (data.get("choices", [{}])[0].get("message", {}).get("content") or "").strip()
                obj = json.loads(content) if content else {}
                arr = obj.get("phrases") or obj.get("items") or []
                phrases = [str(x).strip() for x in arr if str(x).strip()]
        except Exception:
            phrases = []

    if not phrases:
        phrases = ["Let's go!", "Good job!", "Come on!"][: int(payload.count)]
    return _ok(ExtractExpressionsResp(phrases=phrases).model_dump())


@app.route(route="tools/example_sentence", methods=["POST"])
def example_sentence(req: func.HttpRequest) -> func.HttpResponse:
    try:
        payload = ExampleSentenceReq.model_validate_json(req.get_body())
    except ValidationError as ve:
        return _bad_request(ve.json())

    # Try Azure OpenAI to generate a short kid-friendly sentence (<= 10 words)
    aoai_ep = os.getenv("AZURE_OPENAI_ENDPOINT")
    aoai_key = os.getenv("AZURE_OPENAI_API_KEY")
    aoai_dep = os.getenv("AZURE_OPENAI_DEPLOYMENT")
    aoai_ver = os.getenv("AZURE_OPENAI_API_VERSION", "2024-06-01")
    sentence_text: Optional[str] = None
    if aoai_ep and aoai_key and aoai_dep:
        chat_url = f"{aoai_ep}/openai/deployments/{aoai_dep}/chat/completions?api-version={aoai_ver}"
        headers = {"api-key": aoai_key, "Content-Type": "application/json"}
        sys = (
            "You are a kids' English tutor. Generate ONE short, positive,"
            " kid-friendly sentence in English using the given word."
            " Max 10 words. Avoid names or sensitive content."
        )
        ctx = payload.context or {}
        user = (
            f"word: {payload.word}\n"
            f"cefr: {payload.cefr}\n"
            f"videoTitle: {ctx.get('videoTitle','')} character: {ctx.get('character','')}\n"
            "Return only the sentence."
        )
        body = {"messages": [{"role": "system", "content": sys}, {"role": "user", "content": user}], "temperature": 0.2}
        try:
            with httpx.Client(timeout=15) as client:
                r = client.post(chat_url, headers=headers, json=body)
                r.raise_for_status()
                data = r.json()
                sentence_text = (data.get("choices", [{}])[0].get("message", {}).get("content") or "").strip()
        except Exception:
            sentence_text = None

    if not sentence_text:
        sentence_text = f"The {payload.word} is fun to say."

    sent = ExampleSentenceResp(sentence=sentence_text)
    return _ok(sent.model_dump())


@app.route(route="tools/update_progress", methods=["POST"])
def update_progress(req: func.HttpRequest) -> func.HttpResponse:
    try:
        payload = UpdateProgressReq.model_validate_json(req.get_body())
    except ValidationError as ve:
        return _bad_request(ve.json())

    # TODO: Write WatchLog + LearningSession + WordMastery; recompute CEFR and streak
    resp = UpdateProgressResp(ok=True, newLevel="A1", streak=3)
    return _ok(resp.model_dump())


@app.route(route="tools/compute_level", methods=["POST"])
def compute_level(req: func.HttpRequest) -> func.HttpResponse:
    try:
        payload = ComputeLevelReq.model_validate_json(req.get_body())
    except ValidationError as ve:
        return _bad_request(ve.json())

    # TODO: Implement Bayesian mastery across CEFR bins (IRT-like)
    resp = ComputeLevelResp(cefr="A1", confidence=0.78, deltas={"A1": +3, "A2": +1})
    return _ok(resp.model_dump())


@app.route(route="tools/find_local_academies", methods=["POST"])
def find_local_academies(req: func.HttpRequest) -> func.HttpResponse:
    try:
        payload = FindLocalAcademiesReq.model_validate_json(req.get_body())
    except ValidationError as ve:
        return _bad_request(ve.json())

    maps_key = os.getenv("AZURE_MAPS_KEY")
    if not maps_key:
        # Fallback stub when key is missing
        results = [
            AcademyItem(
                name="해피 잉글리시",
                phone="010-1234-5678",
                address=payload.address,
                mapUrl=None,
                distanceM=850,
            ).model_dump()
        ]
        return _ok(results[: payload.topK])

    base = "https://atlas.microsoft.com"
    headers = {"User-Agent": "kids-english-agent/0.1"}

    def geocode_address(address: str) -> Optional[Dict[str, float]]:
        url = (
            f"{base}/search/address/json?api-version=1.0&query={quote_plus(address)}&subscription-key={maps_key}"
        )
        with httpx.Client(timeout=10, headers=headers) as client:
            r = client.get(url)
            if r.status_code != 200:
                return None
            data = r.json()
            results = data.get("results", [])
            if not results:
                return None
            pos = results[0].get("position", {})
            lat = pos.get("lat")
            lon = pos.get("lon")
            return {"lat": lat, "lon": lon} if lat is not None and lon is not None else None

    def search_poi(lat: float, lon: float, q: str, radius: int, limit: int) -> List[Dict[str, Any]]:
        # Use fuzzy search to capture KR/EN variants
        url = (
            f"{base}/search/fuzzy/json?api-version=1.0&subscription-key={maps_key}"
            f"&query={quote_plus(q)}&lat={lat}&lon={lon}&radius={radius}&limit={limit}"
        )
        with httpx.Client(timeout=10, headers=headers) as client:
            r = client.get(url)
            if r.status_code != 200:
                return []
            return r.json().get("results", [])

    geo = geocode_address(payload.address)
    if not geo:
        return _ok([])

    # Try both Korean and English queries; merge results
    raw: List[Dict[str, Any]] = []
    for query in ("영어학원", "영어 유치원", "english academy", "english school kids"):
        raw.extend(search_poi(geo["lat"], geo["lon"], query, int(payload.radiusMeters), int(payload.topK)))

    # Deduplicate by id or address
    seen = set()
    items: List[Dict[str, Any]] = []
    for r in raw:
        poi = r.get("poi") or {}
        addr = r.get("address") or {}
        uid = poi.get("id") or addr.get("freeformAddress") or poi.get("name")
        if not uid or uid in seen:
            continue
        seen.add(uid)
        coords = r.get("position") or {}
        url_map = None
        if coords.get("lat") is not None and coords.get("lon") is not None:
            url_map = f"https://www.bing.com/maps?cp={coords['lat']}~{coords['lon']}"
        items.append(
            AcademyItem(
                name=poi.get("name") or "학원",
                phone=(poi.get("phone") or addr.get("localName") or None),
                address=addr.get("freeformAddress") or payload.address,
                mapUrl=url_map,
                distanceM=int(r.get("dist", 0)) if r.get("dist") is not None else None,
            ).model_dump()
        )

    return _ok(items[: payload.topK])


def _blob_client_from_env():
    conn = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if conn:
        try:
            return BlobServiceClient.from_connection_string(conn)
        except Exception:
            return None
    account = os.getenv("AZURE_STORAGE_ACCOUNT")
    key = os.getenv("AZURE_STORAGE_KEY") or os.getenv("AZURE_STORAGE_ACCOUNT_KEY")
    if account and key:
        try:
            return BlobServiceClient(account_url=f"https://{account}.blob.core.windows.net", credential=key)
        except Exception:
            return None
    return None


@app.route(route="tools/play_cheer", methods=["POST"])
def play_cheer(req: func.HttpRequest) -> func.HttpResponse:
    try:
        payload = PlayCheerReq.model_validate_json(req.get_body())
    except ValidationError as ve:
        return _bad_request(ve.json())

    region = os.getenv("AZURE_SPEECH_REGION")
    key = os.getenv("AZURE_SPEECH_KEY")
    text = "Great job! You did it!"
    voice = "en-US-AvaNeural" if payload.voice == "child" else "en-US-JennyNeural"
    ct = "audio-16khz-32kbitrate-mono-mp3"
    data_bytes = None
    if region and key:
        headers = {
            "Ocp-Apim-Subscription-Key": key,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": ct,
            "User-Agent": "kids-english-agent/0.1",
        }
        ssml = f"""
<speak version='1.0' xml:lang='en-US'>
  <voice name='{voice}'>
    <prosody rate='0%'> {text} </prosody>
  </voice>
</speak>
""".strip()
        try:
            with httpx.Client(timeout=15) as client:
                r = client.post(f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1", headers=headers, content=ssml.encode("utf-8"))
                r.raise_for_status()
                data_bytes = r.content
        except Exception:
            data_bytes = None

    if data_bytes:
        bsc = _blob_client_from_env()
        if bsc:
            try:
                container = os.getenv("CHEER_CONTAINER", "cheer")
                bsc.create_container(container)
            except Exception:
                pass
            try:
                container = os.getenv("CHEER_CONTAINER", "cheer")
                blob_name = f"cheer_{int(datetime.utcnow().timestamp())}.mp3"
                blob = bsc.get_blob_client(container=container, blob=blob_name)
                blob.upload_blob(data_bytes, overwrite=True, content_type="audio/mpeg")
                account = bsc.account_name
                key = os.getenv("AZURE_STORAGE_KEY") or os.getenv("AZURE_STORAGE_ACCOUNT_KEY")
                if account and key:
                    sas = generate_blob_sas(
                        account_name=account,
                        container_name=container,
                        blob_name=blob_name,
                        account_key=key,
                        permission=BlobSasPermissions(read=True),
                        expiry=datetime.utcnow() + timedelta(minutes=30),
                    )
                    url = f"https://{account}.blob.core.windows.net/{container}/{blob_name}?{sas}"
                    return _ok(PlayCheerResp(audioUrl=url).model_dump())
            except Exception:
                pass
        # Fallback data URL if storage missing
        b64 = base64.b64encode(data_bytes).decode("ascii")
        return _ok(PlayCheerResp(audioUrl=f"data:audio/mpeg;base64,{b64}").model_dump())

    return _ok(PlayCheerResp(audioUrl=None).model_dump())


def _cosmos_container():
    conn = os.getenv("COSMOS_CONN")
    if not conn:
        return None
    try:
        client = CosmosClient.from_connection_string(conn)
        db_name = os.getenv("COSMOS_DB", "kids")
        cont_name = os.getenv("COSMOS_PREFS_CONTAINER") or os.getenv("COSMOS_PROFILE_CONTAINER") or "Prefs"
        pk_path = os.getenv("COSMOS_PARTITION_KEY", "/id")
        db = client.create_database_if_not_exists(id=db_name)
        container = db.create_container_if_not_exists(
            id=cont_name,
            partition_key=PartitionKey(path=pk_path),
        )
        return container
    except Exception:
        return None


@app.route(route="tools/save_prefs", methods=["POST"])
def save_prefs(req: func.HttpRequest) -> func.HttpResponse:
    try:
        data = json.loads(req.get_body() or b"{}")
        child_id = data.get("childId")
        if not child_id:
            return _bad_request("childId required")
        doc = {
            "id": f"prefs_{child_id}",
            "childId": child_id,
            "recent_videos": data.get("recent_videos", []),
            "favorite_videos": data.get("favorite_videos", []),
        }
    except Exception as ve:
        return _bad_request(str(ve))

    cont = _cosmos_container()
    if not cont:
        return _ok({"ok": False, "error": "cosmos_not_configured"})
    cont.upsert_item(doc)
    return _ok({"ok": True})


@app.route(route="tools/save_profile", methods=["POST"])
def save_profile(req: func.HttpRequest) -> func.HttpResponse:
    try:
        payload = SaveProfileReq.model_validate_json(req.get_body())
    except ValidationError as ve:
        return _bad_request(ve.json())

    cont = _cosmos_container()
    if not cont:
        return _ok(SaveProfileResp(ok=False, storedId=None).model_dump())

    doc_id = f"profile_{payload.childId}"
    item = {
        "id": doc_id,
        "childId": payload.childId,
        "type": "profile",
        "name": payload.name,
        "age": int(payload.age),
        "region": payload.region,
        "study": payload.study,
        "characters": payload.characters,
        "cefr": payload.cefr,
        "interest": payload.interest,
        "updatedAt": datetime.utcnow().isoformat() + "Z",
    }
    try:
        cont.upsert_item(item)
        return _ok(SaveProfileResp(ok=True, storedId=doc_id).model_dump())
    except Exception as e:
        return _ok(SaveProfileResp(ok=False, storedId=None).model_dump())


@app.route(route="tools/load_profile", methods=["POST"])
def load_profile(req: func.HttpRequest) -> func.HttpResponse:
    try:
        payload = LoadProfileReq.model_validate_json(req.get_body())
    except ValidationError as ve:
        return _bad_request(ve.json())

    cont = _cosmos_container()
    if not cont:
        return _ok(LoadProfileResp(ok=False, profile=None).model_dump())
    doc_id = f"profile_{payload.childId}"
    try:
        item = cont.read_item(item=doc_id, partition_key=doc_id)
        profile = {
            "childId": item.get("childId"),
            "name": item.get("name"),
            "age": item.get("age"),
            "region": item.get("region"),
            "study": item.get("study"),
            "characters": item.get("characters", []),
            "cefr": item.get("cefr"),
            "interest": item.get("interest"),
        }
        return _ok(LoadProfileResp(ok=True, profile=profile).model_dump())
    except Exception:
        return _ok(LoadProfileResp(ok=True, profile=None).model_dump())


@app.route(route="tools/load_prefs", methods=["POST"])
def load_prefs(req: func.HttpRequest) -> func.HttpResponse:
    try:
        data = json.loads(req.get_body() or b"{}")
        child_id = data.get("childId")
        if not child_id:
            return _bad_request("childId required")
        doc_id = f"prefs_{child_id}"
    except Exception as ve:
        return _bad_request(str(ve))

    cont = _cosmos_container()
    if not cont:
        return _ok({"ok": False, "error": "cosmos_not_configured"})
    try:
        item = cont.read_item(item=doc_id, partition_key=doc_id)
        return _ok({
            "ok": True,
            "recent_videos": item.get("recent_videos", []),
            "favorite_videos": item.get("favorite_videos", []),
        })
    except Exception:
        return _ok({"ok": True, "recent_videos": [], "favorite_videos": []})


@app.route(route="tools/parent_report", methods=["POST"])
def parent_report(req: func.HttpRequest) -> func.HttpResponse:
    try:
        payload = ParentReportReq.model_validate_json(req.get_body())
    except ValidationError as ve:
        return _bad_request(ve.json())

    # TODO: Aggregate KPIs; optionally precompute via Synapse Link + Power BI
    resp = ParentReportResp(
        summaryText="Great progress this week! Keep watching and practicing.",
        kpis={"watchMin": 120, "sessions": 4, "wordsLearned": 15, "levelChange": "+1"},
        chartData={"series": [{"name": "Sessions", "data": [1, 2, 1, 0, 0, 0, 0]}]},
    )
    return _ok(resp.model_dump())


@app.route(route="tools/say_word", methods=["POST"])
def say_word(req: func.HttpRequest) -> func.HttpResponse:
    try:
        payload = SayWordReq.model_validate_json(req.get_body())
    except ValidationError as ve:
        return _bad_request(ve.json())

    region = os.getenv("AZURE_SPEECH_REGION")
    key = os.getenv("AZURE_SPEECH_KEY")
    if not (region and key):
        # Fallback: return empty to let UI handle gracefully
        return _ok(SayWordResp(audioUrl=None, audioB64=None, contentType=None).model_dump())

    voice = payload.voice or "en-US-AvaNeural"
    word = payload.word
    ct = "audio-16khz-32kbitrate-mono-mp3"
    url = f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1"
    headers = {
        "Ocp-Apim-Subscription-Key": key,
        "Content-Type": "application/ssml+xml",
        "X-Microsoft-OutputFormat": ct,
        "User-Agent": "kids-english-agent/0.1",
    }
    ssml = f"""
<speak version='1.0' xml:lang='en-US'>
  <voice name='{voice}'>
    <prosody rate='-10.00%'> {word} </prosody>
  </voice>
</speak>
""".strip()
    try:
        with httpx.Client(timeout=15) as client:
            r = client.post(url, headers=headers, content=ssml.encode("utf-8"))
            r.raise_for_status()
            audio = r.content
            b64 = base64.b64encode(audio).decode("ascii")
            data_url = f"data:audio/mpeg;base64,{b64}"
            return _ok(SayWordResp(audioUrl=data_url, audioB64=b64, contentType="audio/mpeg").model_dump())
    except Exception as e:
        return _ok(SayWordResp(audioUrl=None, audioB64=None, contentType=None).model_dump())
