import os
import asyncio
import base64
from io import BytesIO
from typing import List, Dict, Any

import streamlit as st
from dotenv import load_dotenv

from app.azure_tools import tool_router as http_tool_router, TOOLS_SPEC as _  # noqa: F401


load_dotenv()
st.set_page_config(page_title="Kids English Agent", page_icon="🎈", layout="wide")
st.title("Kids English Agent")


def use_functions_tools() -> bool:
    return os.getenv("USE_FUNCTION_TOOLS", "false").lower() in ("1", "true", "yes")


async def call_tool(name: str, args: Dict[str, Any]):
    if use_functions_tools():
        try:
            return await http_tool_router(name, args)
        except Exception:
            pass
    # Local stubs
    if name == "search_youtube_videos":
        chs = args.get("characters") or ["블루이"]
        vids = [
            "dQw4w9WgXcQ",
            "J---aiyznGQ",
            "9bZkp7q19f0",
            "kJQP7kiw5Fk",
            "3JZ_D3ELwOQ",
        ]
        out = []
        for i, vid in enumerate(vids):
            out.append({
                "id": vid,
                "title": f"{chs[0]} learns colors #{i+1}",
                "channel": "Kids Channel",
                "url": f"https://www.youtube.com/watch?v={vid}",
                "durationSec": 180 + i * 15,
                "hasCaptions": True,
                "thumbnail": f"https://img.youtube.com/vi/{vid}/hqdefault.jpg",
                "tags": [args.get("cefr", "A1"), chs[0]],
            })
        maxn = max(1, min(int(args.get("max", 5)), len(out)))
        return out[:maxn]
    if name == "index_video":
        return {"transcriptId": "tx_local_1", "lang": "en", "wordCounts": {}, "segments": []}
    if name == "extract_top_words":
        return [
            {"word": "forest", "pos": "noun", "cefr": "A1", "definition": "a large area of trees"},
            {"word": "climb", "pos": "verb", "cefr": "A1", "definition": "go up something"},
            {"word": "brave", "pos": "adj", "cefr": "A2", "definition": "showing no fear"},
        ][: args.get("count", 5)]
    if name == "extract_top_expressions":
        c = int(args.get("count", 3))
        phrases = ["Let's go!", "Good job!", "Come on!"]
        return {"phrases": phrases[:c]}
    if name == "example_sentence":
        return {"sentence": f"The {args.get('word','word')} is fun to say."}
    if name == "update_progress":
        return {"ok": True, "newLevel": "A1", "streak": 1}
    if name == "parent_report":
        return {
            "summaryText": "이번 주 잘했어요! 4회 학습, 15단어.",
            "kpis": {"watchMin": 120, "sessions": 4, "wordsLearned": 15, "levelChange": "+1"},
            "chartData": {"series": [{"name": "Sessions", "data": [1, 2, 1, 0, 0, 0, 0]}]},
        }
    if name == "find_local_academies":
        return [
            {"name": "해피 잉글리시", "phone": "010-1234-5678", "address": args.get("address", ""), "mapUrl": None, "distanceM": 850}
        ]
    if name == "say_word":
        return {"audioB64": None, "audioUrl": None}
    if name == "play_cheer":
        return {"audioUrl": None}
    return {"error": f"unknown tool {name}"}


def derive_cefr(age: int, study: str) -> str:
    if age <= 5:
        return "PREA1"
    if age <= 7:
        return "A1"
    return "A2" if study and study != "없다" else "A1"


# Session state
if "profile" not in st.session_state:
    st.session_state["profile"] = None
if "selected_video" not in st.session_state:
    st.session_state["selected_video"] = None
if "learning_cards" not in st.session_state:
    st.session_state["learning_cards"] = []
if "watched_ids" not in st.session_state:
    st.session_state["watched_ids"] = set()
if "watch_history" not in st.session_state:
    st.session_state["watch_history"] = []  # {videoId,title,watched,learned}
    # Try loading existing profile from backend on first run
    try:
        resp = asyncio.run(call_tool("load_profile", {"childId": "local_child"}))
        if isinstance(resp, dict) and resp.get("ok") and resp.get("profile") and not st.session_state.get("profile"):
            prof = resp.get("profile") or {}
            prof["childId"] = prof.get("childId") or "local_child"
            st.session_state["profile"] = prof
    except Exception:
        pass


def setup_view():
    st.subheader("초기 설정")
    with st.form("setup_form", clear_on_submit=False):
        age = st.number_input("나이(만)", min_value=1, max_value=15, value=7)
        region = st.text_input("지역", value="서울 은평구 응암동", placeholder="예: 서울 은평구 응암동")
        study = st.selectbox("영어 공부 기간", ["없다", "1~3개월", "3~6개월", "6개월 이상"], index=0)
        characters = st.multiselect("좋아하는 캐릭터", ["블루이", "뽀로로", "페파 피그", "포켓몬", "핑크퐁"], default=["블루이"]) 
        other = st.text_input("기타 캐릭터(쉼표로 구분)", placeholder="예: 페파 피그, 피카츄")
        child_id = st.text_input("ID", value="local_child")
        col_s1, col_s2 = st.columns(2)
        save_clicked = col_s1.form_submit_button("설정 저장")
        save_and_go_clicked = col_s2.form_submit_button("저장 후 아동 화면 이동")

    # ← 폼 밖에서 처리
    if save_clicked or save_and_go_clicked:
        chars = list(characters) if characters else []
        if other.strip():
            chars.extend([c.strip() for c in other.split(",") if c.strip()])
        cefr = derive_cefr(int(age), study)
        st.session_state.update({
            "profile": {
                "age": int(age),
                "region": region.strip(),
                "study": study,
                "characters": chars or ["블루이"],
                "cefr": cefr,
                "childId": (child_id.strip() or "local_child"),
            },
            "setup_saved": True,
            "goto_child": bool(save_and_go_clicked),
        })
        try:
            _ = asyncio.run(call_tool("save_profile", {
                "childId": st.session_state["profile"]["childId"],
                "name": st.session_state["profile"].get("name", ""),
                "age": st.session_state["profile"]["age"],
                "region": st.session_state["profile"]["region"],
                "study": st.session_state["profile"]["study"],
                "characters": st.session_state["profile"]["characters"],
                "cefr": st.session_state["profile"]["cefr"],
                "interest": st.session_state["profile"].get("interest", 4),
            }))
        except Exception:
            pass
        st.success("설정이 저장되었습니다.")
        if save_and_go_clicked:
            st.rerun()


def child_view():
    prof = st.session_state["profile"]
    st.subheader("아동용 — 영상 시청 및 학습")
    col_left, col_right = st.columns([3, 2], gap="large")

    # Get 2 recommendations and filter out watched
    results: List[Dict[str, Any]] = []
    try:
        results = asyncio.run(call_tool("search_youtube_videos", {
            "age": prof["age"], "cefr": prof["cefr"], "characters": prof["characters"], "max": 2
        }))
    except Exception as e:
        st.warning(f"추천 검색 실패: {e}")
    watched_ids = set(st.session_state.get("watched_ids", set()))
    results = [it for it in (results or []) if it.get("id") not in watched_ids]

    with col_left:
        sel = st.session_state.get("selected_video")
        st.markdown("#### 시청 화면")
        if sel:
            st.write(sel["title"])
            st.video(sel["url"])
            if st.button("시청 완료", key="btn_watch_done"):
                vid_id = sel.get("id", ""); title = sel.get("title", "")
                st.session_state["watched_ids"].add(vid_id)
                # 기록 업데이트
                found = False
                for it in st.session_state["watch_history"]:
                    if it.get("videoId") == vid_id:
                        it["watched"] = True; found = True; break
                if not found:
                    st.session_state["watch_history"].append({"videoId": vid_id, "title": title, "watched": True, "learned": False})
                # 바로 학습 카드 생성 (상위 5 단어)
                try:
                    idx = asyncio.run(call_tool("index_video", {"videoUrl": sel["url"]}))
                    tx_id = idx.get("transcriptId", "tx")
                    words = asyncio.run(call_tool("extract_top_words", {"transcriptId": tx_id, "count": 5, "cefr": prof["cefr"]}))
                    cards = []
                    for w in words:
                        ex = asyncio.run(call_tool(
                            "example_sentence",
                            {"word": w.get("word",""), "cefr": prof["cefr"], "context": {"videoTitle": sel.get("title",""), "character": (prof.get("characters") or [""])[0]}}
                        ))
                        cards.append({
                            "word": w.get("word",""),
                            "definition": w.get("definition", ""),
                            "sentence": ex.get("sentence", ""),
                            "imageUrl": f"https://source.unsplash.com/400x240/?{w.get('word','')},kids",
                        })
                    st.session_state["learning_cards"] = cards
                    st.success("시청 완료! 해당 영상의 학습 카드 5개를 준비했어요.")
                except Exception as e:
                    st.error(f"학습 카드 생성 실패: {e}")
            if st.button("학습 시작", key="start_learning_btn"):
                try:
                    idx = asyncio.run(call_tool("index_video", {"videoUrl": sel["url"]}))
                    tx_id = idx.get("transcriptId", "tx")
                    words = asyncio.run(call_tool("extract_top_words", {"transcriptId": tx_id, "count": 5, "cefr": prof["cefr"]}))
                    cards = []
                    for w in words:
                        ex = asyncio.run(call_tool("example_sentence", {"word": w["word"], "cefr": prof["cefr"], "context": {"videoTitle": sel["title"], "character": (prof["characters"] or [""])[0]}}))
                        cards.append({"word": w["word"], "definition": w.get("definition", ""), "sentence": ex.get("sentence", ""), "imageUrl": f"https://source.unsplash.com/400x240/?{w['word']},kids"})
                    st.session_state["learning_cards"] = cards
                    st.success("학습 카드가 준비되었습니다.")
                except Exception as e:
                    st.error(f"학습 카드 생성 실패: {e}")
        else:
            st.info("아래 추천 목록에서 영상을 선택하세요.")

        st.markdown("#### 추천 영상")
        if results:
            cols = st.columns(2)
            for i, item in enumerate(results):
                with cols[i % 2]:
                    if item.get("thumbnail"):
                        st.image(item["thumbnail"], width='stretch')
                    st.caption(item.get("channel", ""))
                    st.write(f"**{item['title']}**")
                    if st.button("시청", key=f"watch_{i}"):
                        st.session_state["selected_video"] = item
                        st.session_state["learning_cards"] = []
                        st.rerun()
        else:
            st.write("새로운 추천이 없습니다. 잠시 후 다시 시도해 주세요.")

    with col_right:
        st.markdown("#### 학습 화면")
        cards: List[Dict[str, Any]] = st.session_state.get("learning_cards", [])
        if cards:
            st.markdown("학습 카드 (5)")
            for idx, c in enumerate(cards):
                st.markdown(f"**{idx+1}. {c['word']}** — {c['definition']}")
                cc1, cc2 = st.columns([2, 1])
                with cc1:
                    if c.get("imageUrl"):
                        st.image(c["imageUrl"], width='stretch')
                with cc2:
                    st.caption("예문")
                    st.write(c.get("sentence", ""))
                    if st.button("발음 듣기", key=f"say_{idx}"):
                        try:
                            resp = asyncio.run(call_tool("say_word", {"word": c["word"], "voice": "en-US-AvaNeural"}))
                            b64 = resp.get("audioB64")
                            if b64:
                                st.audio(BytesIO(base64.b64decode(b64)), format="audio/mp3")
                            elif resp.get("audioUrl"):
                                st.audio(resp["audioUrl"])  # fallback
                        except Exception as e:
                            st.warning(f"발음 생성 실패: {e}")
            if st.button("완료(진행도 저장)", key="save_progress_btn"):
                try:
                    sel = st.session_state.get("selected_video") or {}
                    _ = asyncio.run(call_tool("update_progress", {
                        "childId": prof["childId"],
                        "videoId": sel.get("id", ""),
                        "learnedWords": [c["word"] for c in cards],
                        "quizScore": 90,
                        "durationSec": sel.get("durationSec", 300),
                    }))
                    # mark learned
                    vid_id = sel.get("id", ""); title = sel.get("title", "")
                    found = False
                    for it in st.session_state["watch_history"]:
                        if it.get("videoId") == vid_id:
                            it["learned"] = True; found = True; break
                    if not found:
                        st.session_state["watch_history"].append({"videoId": vid_id, "title": title, "watched": False, "learned": True})
                    # cheer
                    try:
                        cheer = asyncio.run(call_tool("play_cheer", {"voice": "child", "style": "cheerful"}))
                        if cheer.get("audioUrl"):
                            st.audio(cheer["audioUrl"]) 
                    except Exception:
                        pass
                    st.success("완료! 잘했어요 🎉")
                except Exception as e:
                    st.error(f"저장 실패: {e}")
        else:
            st.write("영상에서 ‘학습 시작’을 누르면 추천 단어가 여기에 나타납니다.")


def parent_view():
    prof = st.session_state["profile"]
    st.subheader("부모용 — 진행 체크 및 학원 찾기")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### 학습 요약 (7일)")
        try:
            rep = asyncio.run(call_tool("parent_report", {"childId": prof["childId"], "period": "7d"}))
            st.write(rep.get("summaryText", ""))
            k = rep.get("kpis", {})
            st.metric("시청 분", k.get("watchMin", 0))
            st.metric("세션", k.get("sessions", 0))
            st.metric("학습 단어", k.get("wordsLearned", 0))
            st.metric("레벨 변화", k.get("levelChange", "+0"))
        except Exception as e:
            st.warning(f"요약 조회 실패: {e}")

        # Local summary
        hist = st.session_state.get("watch_history", [])
        watched_cnt = sum(1 for h in hist if h.get("watched"))
        learned_cnt = sum(1 for h in hist if h.get("learned"))
        st.markdown("#### 로컬 요약")
        st.metric("시청 완료 영상 수", watched_cnt)
        st.metric("학습 카드 완료 수", learned_cnt)
        if hist:
            st.caption("최근 활동")
            for h in hist[-5:][::-1]:
                st.write(f"- {h.get('title','(제목없음)')} — 시청:{'O' if h.get('watched') else 'X'} / 학습:{'O' if h.get('learned') else 'X'}")

    with col2:
        st.markdown("#### 프로필 설정")
        study_opts = ["없다", "1~3개월", "3~6개월", "6개월 이상"]
        idx = study_opts.index(prof.get("study", "없다")) if prof.get("study", "없다") in study_opts else 0
        with st.form("edit_profile_form"):
            age = st.number_input("나이(만)", min_value=1, max_value=15, value=int(prof.get("age", 7)))
            region = st.text_input("지역", value=prof.get("region", ""), placeholder="예: 서울 은평구 응암동")
            study = st.selectbox("영어 공부 기간", study_opts, index=idx)
            saved = st.form_submit_button("변경 사항 저장")
            if saved:
                new_cefr = derive_cefr(int(age), study)
                prof.update({"age": int(age), "region": region.strip(), "study": study, "cefr": new_cefr})
                st.success(f"저장 완료 (CEFR: {new_cefr})")
                try:
                    _ = asyncio.run(call_tool("save_profile", {
                        "childId": prof.get("childId", "local_child"),
                        "name": name.strip(),
                        "age": int(age),
                        "region": region.strip(),
                        "study": study,
                        "characters": list(dict.fromkeys(all_chars)),
                        "cefr": new_cefr,
                        "interest": int(interest),
                    }))
                except Exception:
                    pass
                st.session_state["selected_video"] = None
                st.session_state["learning_cards"] = []
                st.rerun()

        st.markdown("#### 흥미도 체크")
        interest = st.slider("아동의 흥미도", 1, 5, 4)
        st.caption("높을수록 더 어려운 영상을 추천합니다.")
        if st.button("수준 재조정 제안"):
            st.success("다음 추천에서 한 단계 높은 영상을 시도해 볼게요.")

    st.markdown("---")
    st.markdown("#### 우리 동네 학원 찾기")
    radius = st.select_slider("반경(미터)", options=[1000, 2000, 3000, 5000], value=3000)
    if st.button("학원 검색"):
        try:
            results = asyncio.run(call_tool("find_local_academies", {"address": prof["region"], "radiusMeters": int(radius), "tags": ["english", "kids"], "topK": 5}))
            for a in results:
                st.write(f"- {a['name']} ({a.get('distanceM','?')}m) — {a['address']} — {a.get('phone','')}")
        except Exception as e:
            st.error(f"학원 검색 실패: {e}")


# New helper: suggest characters by age buckets
def suggest_characters_by_age(age: int) -> list[str]:
    if age <= 3:
        return [
            "Cocomelon",
            "Super Simple Songs",
            "Baby Einstein",
            "Hey Duggee",
            "Pocoyo",
            "Shaun the Sheep",
        ]
    if age <= 6:
        return [
            "Peppa Pig",
            "Bluey",
            "Ben & Holly's Little Kingdom",
            "Thomas & Friends",
            "Octonauts",
            "Alphablocks",
            "Numberblocks",
        ]
    if age <= 9:
        return [
            "Wild Kratts",
            "The Magic School Bus",
            "Odd Squad",
            "Hilda",
            "Carmen Sandiego",
        ]
    return ["Crash Course Kids", "TED-Ed", "BBC Newsround"]


# New setup view v2 per spec
def setup_view_v2_old():
    st.subheader("초기 설정")
    with st.form("setup_form_v2"):
        age = st.number_input("나이(만)", min_value=0, max_value=10, value=6)
        region = st.text_input("지역", value="서울 마포구 합정동", placeholder="예) 서울 마포구 합정동")
        study = st.selectbox("영어 공부 기간", ["처음이다", "1~3개월", "3~6개월", "6개월 이상"], index=0)
        name = st.text_input("이름", value="")
        child_id = st.text_input("ID", value="local_child")
        name = st.text_input("이름", value="")
        suggested = suggest_characters_by_age(int(age))
        base_options = list(dict.fromkeys(suggested + [
            "Pororo", "Peppa Pig", "Bluey", "Pikachu", "Pinkfong",
            "Ben & Holly's Little Kingdom", "Thomas & Friends", "Octonauts",
            "Alphablocks", "Numberblocks", "Cocomelon", "Super Simple Songs",
            "Pocoyo", "Shaun the Sheep",
        ]))
        characters = st.multiselect("좋아하는 캐릭터", options=base_options, default=suggested)
        other = st.text_input("기타 캐릭터(쉼표로 구분)", placeholder="예) Pororo, Pikachu")
        save_clicked = st.form_submit_button("설정 저장")
        if save_clicked:
            chars = list(characters)
            if other.strip():
                chars.extend([c.strip() for c in other.split(",") if c.strip()])
            cefr = derive_cefr(int(age), study)
            st.session_state["profile"] = {
                "age": int(age),
                "region": region.strip(),
                "study": study,
                "characters": chars or suggested,
                "cefr": cefr,
                "childId": "local_child",
                "interest": 4,
                "name": name.strip() or "",
            }
            st.success("설정을 저장했어요. 확인을 누르면 탭으로 이동합니다.")
            if st.button("확인", key="confirm_setup_go_tabs"):
                # 바로 탭 화면으로 전환 (프로필이 설정되었으므로 다음 렌더에서 탭 노출)
                st.rerun()
    # 확인 버튼(폼 바깥)
    if st.session_state.get("setup_saved"):
        if st.button("확인", key="confirm_setup_go_tabs"):
            st.session_state["setup_saved"] = False
            st.rerun()

# New child view v2 per spec
def child_view_v2():
    prof = st.session_state["profile"]
    st.subheader("아동용 추천 및 학습")
    col_left, col_right = st.columns([3, 2], gap="large")

    results: list[dict[str, Any]] = []
    try:
        fetched = asyncio.run(call_tool("search_youtube_videos", {
            "age": prof["age"], "cefr": prof["cefr"], "characters": prof.get("characters", []), "max": 8
        })) or []
        watched_ids = set(st.session_state.get("watched_ids", set()))
        results = [it for it in fetched if it.get("id") not in watched_ids][:2]
    except Exception as e:
        st.warning(f"추천 실패: {e}")

    hist = st.session_state.get("watch_history", [])
    recent_watched = [h for h in hist if h.get("watched")][-2:][::-1]
    if recent_watched:
        st.markdown("##### 최근 시청 완료")
        cols = st.columns(len(recent_watched))
        for i, h in enumerate(recent_watched):
            with cols[i]:
                st.write(h.get("title", "(제목 없음)"))
                if st.button("다시 보기", key=f"rewatch_{i}"):
                    vid = h.get("videoId", "")
                    st.session_state["selected_video"] = {
                        "id": vid,
                        "title": h.get("title", ""),
                        "url": f"https://www.youtube.com/watch?v={vid}",
                        "durationSec": 300,
                        "hasCaptions": True,
                    }
                    st.session_state["learning_cards"] = []
                    st.rerun()

    with col_left:
        sel = st.session_state.get("selected_video")
        st.markdown("#### 시청 화면")
        if sel:
            st.write(sel.get("title", ""))
            st.video(sel.get("url", ""))
            if st.button("시청 완료", key="btn_watch_done_v2"):
                vid_id = sel.get("id", "")
                title = sel.get("title", "")
                st.session_state.setdefault("watched_ids", set()).add(vid_id)
                found = False
                for it in st.session_state["watch_history"]:
                    if it.get("videoId") == vid_id:
                        it["watched"] = True
                        found = True
                        break
                if not found:
                    st.session_state["watch_history"].append({"videoId": vid_id, "title": title, "watched": True, "learned": False})
                try:
                    idx = asyncio.run(call_tool("index_video", {"videoUrl": sel.get("url", "")}))
                    tx_id = idx.get("transcriptId", "tx")
                    exps = asyncio.run(call_tool("extract_top_expressions", {"transcriptId": tx_id, "count": 3, "cefr": prof.get("cefr")}))
                    phrases = exps.get("phrases") if isinstance(exps, dict) else exps
                    cards = [{"phrase": p, "imageUrl": f"https://source.unsplash.com/400x240/?kids"} for p in (phrases or [])]
                    st.session_state["learning_cards"] = cards
                    st.success("시청 완료! 자주 나온 표현 3가지를 준비했어요.")
                except Exception as e:
                    st.error(f"학습 카드 생성 실패: {e}")
                st.rerun()
        else:
            st.info("아래 추천 목록에서 영상을 선택하세요")

        st.markdown("#### 추천 영상 (2)")
        if results:
            cols = st.columns(2)
            for i, item in enumerate(results):
                with cols[i % 2]:
                    if item.get("thumbnail"):
                        st.image(item["thumbnail"], use_container_width=True)
                    st.caption(item.get("channel", ""))
                    st.write(f"**{item.get('title','')}**")
                    if st.button("시청", key=f"watch_v2_{i}"):
                        st.session_state["selected_video"] = item
                        st.session_state["learning_cards"] = []
                        st.rerun()
        else:
            st.write("추천이 부족해요. 잠시 후 다시 시도해 주세요.")

    with col_right:
        st.markdown("#### 학습 화면")
        cards: List[Dict[str, Any]] = st.session_state.get("learning_cards", [])
        if cards:
            st.markdown("표현 카드 (3)")
            for idx, c in enumerate(cards):
                st.markdown(f"**{idx+1}. {c['phrase']}**")
                cc1, cc2 = st.columns([2, 1])
                with cc1:
                    if c.get("imageUrl"):
                        st.image(c["imageUrl"], use_container_width=True)
                with cc2:
                    if st.button("발음 듣기", key=f"say_phrase_{idx}"):
                        try:
                            resp = asyncio.run(call_tool("say_word", {"word": c["phrase"], "voice": "en-US-AvaNeural"}))
                            b64 = resp.get("audioB64")
                            if b64:
                                st.audio(BytesIO(base64.b64decode(b64)), format="audio/mp3")
                            elif resp.get("audioUrl"):
                                st.audio(resp["audioUrl"])  # fallback
                        except Exception as e:
                            st.warning(f"발음 생성 실패: {e}")
            if st.button("학습 완료(진행 저장)", key="save_progress_btn_v2"):
                try:
                    sel = st.session_state.get("selected_video") or {}
                    _ = asyncio.run(call_tool("update_progress", {
                        "childId": prof["childId"],
                        "videoId": sel.get("id", ""),
                        "learnedWords": [c["phrase"] for c in cards],
                        "quizScore": 90,
                        "durationSec": sel.get("durationSec", 300),
                    }))
                    vid_id = sel.get("id", ""); title = sel.get("title", "")
                    found = False
                    for it in st.session_state["watch_history"]:
                        if it.get("videoId") == vid_id:
                            it["learned"] = True
                            found = True
                            break
                    if not found:
                        st.session_state["watch_history"].append({"videoId": vid_id, "title": title, "watched": False, "learned": True})
                    st.success("완료! 잘했어요 🎉")
                except Exception as e:
                    st.error(f"저장 실패: {e}")
        else:
            st.write("영상을 시청하면 학습 표현이 준비됩니다.")


# New parent view v2 per spec
def parent_view_v2():
    prof = st.session_state["profile"]
    st.subheader("부모용 진행 체크 및 설정")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### 학습 요약 (7일)")
        try:
            rep = asyncio.run(call_tool("parent_report", {"childId": prof["childId"], "period": "7d"}))
            st.write(rep.get("summaryText", ""))
            k = rep.get("kpis", {})
            st.metric("시청 분", k.get("watchMin", 0))
            st.metric("세션", k.get("sessions", 0))
            st.metric("학습 단어", k.get("wordsLearned", 0))
            st.metric("레벨 변화", k.get("levelChange", "+0"))
        except Exception as e:
            st.warning(f"요약 조회 실패: {e}")

        hist = st.session_state.get("watch_history", [])
        watched_cnt = sum(1 for h in hist if h.get("watched"))
        learned_cnt = sum(1 for h in hist if h.get("learned"))
        st.markdown("#### 로컬 요약")
        st.metric("시청 완료 영상 수", watched_cnt)
        st.metric("학습 카드 완료 수", learned_cnt)
        if hist:
            st.caption("최근 활동")
            for h in hist[-5:][::-1]:
                st.write(f"- {h.get('title','(제목 없음)')} ▶시청:{'O' if h.get('watched') else 'X'} / 학습:{'O' if h.get('learned') else 'X'}")

    with col2:
        st.markdown("#### 프로필 설정")
        study_opts = ["처음이다", "1~3개월", "3~6개월", "6개월 이상"]
        cur_study = prof.get("study", "처음이다")
        idx = study_opts.index(cur_study) if cur_study in study_opts else 0
        with st.form("edit_profile_form_v2"):
            name = st.text_input("이름", value=prof.get("name", ""))
            age = st.number_input("나이(만)", min_value=0, max_value=10, value=int(prof.get("age", 6)))
            region = st.text_input("지역", value=prof.get("region", ""), placeholder="예) 서울 마포구 합정동")
            study = st.selectbox("영어 공부 기간", study_opts, index=idx)
            suggested = suggest_characters_by_age(int(age))
            current_chars = list(prof.get("characters", []))
            options = list(dict.fromkeys(suggested + current_chars))
            selected_chars = st.multiselect("좋아하는 캐릭터(추가/삭제)", options=options, default=current_chars)
            extra = st.text_input("캐릭터 추가(쉼표로 구분)", placeholder="예) Pororo, Pikachu")
            interest = st.slider("아이의 영어 흥미도", 1, 5, int(prof.get("interest", 4)))
            saved = st.form_submit_button("변경사항 저장")
            if saved:
                all_chars = list(selected_chars)
                if extra.strip():
                    all_chars.extend([c.strip() for c in extra.split(",") if c.strip()])
                new_cefr = derive_cefr(int(age), study)
                prof.update({
                    "name": name.strip(),
                    "age": int(age),
                    "region": region.strip(),
                    "study": study,
                    "characters": list(dict.fromkeys(all_chars)),
                    "cefr": new_cefr,
                    "interest": int(interest),
                })
                st.success(f"저장 완료 (CEFR: {new_cefr})")
                st.session_state["selected_video"] = None
                st.session_state["learning_cards"] = []
                st.rerun()

# Override setup view to avoid buttons inside form
def setup_view_v2():
    st.subheader("초기 설정")
    with st.form("setup_form_v2"):
        age = st.number_input("나이(만)", min_value=0, max_value=10, value=6)
        region = st.text_input("지역", value="서울 마포구 합정동", placeholder="예) 서울 마포구 합정동")
        study = st.selectbox("영어 공부 기간", ["처음이다", "1~3개월", "3~6개월", "6개월 이상"], index=0)
        suggested = suggest_characters_by_age(int(age))
        base_options = list(dict.fromkeys(suggested + [
            "Pororo", "Peppa Pig", "Bluey", "Pikachu", "Pinkfong",
            "Ben & Holly's Little Kingdom", "Thomas & Friends", "Octonauts",
            "Alphablocks", "Numberblocks", "Cocomelon", "Super Simple Songs",
            "Pocoyo", "Shaun the Sheep",
        ]))
        characters = st.multiselect("좋아하는 캐릭터", options=base_options, default=suggested)
        other = st.text_input("기타 캐릭터(쉼표로 구분)", placeholder="예) Pororo, Pikachu")
        saved = st.form_submit_button("설정 저장")
        if saved:
            chars = list(characters)
            if other.strip():
                chars.extend([c.strip() for c in other.split(",") if c.strip()])
            cefr = derive_cefr(int(age), study)
            st.session_state["profile"] = {
                "age": int(age),
                "region": region.strip(),
                "study": study,
                "characters": chars or suggested,
                "cefr": cefr,
                "childId": ((st.session_state.get("profile") or {}).get("childId") or "local_child"),
                "interest": 4,
                "name": (st.session_state.get("profile") or {}).get("name", ""),
            }
            try:
                _ = asyncio.run(call_tool("save_profile", {
                    "childId": st.session_state["profile"]["childId"],
                    "name": st.session_state["profile"].get("name", ""),
                    "age": st.session_state["profile"]["age"],
                    "region": st.session_state["profile"]["region"],
                    "study": st.session_state["profile"]["study"],
                    "characters": st.session_state["profile"]["characters"],
                    "cefr": st.session_state["profile"]["cefr"],
                    "interest": st.session_state["profile"].get("interest", 4),
                }))
            except Exception:
                pass
            st.session_state["setup_saved"] = True
    # Confirm outside the form
    if st.session_state.get("setup_saved"):
        st.success("설정을 저장했어요. 확인을 누르면 탭으로 이동합니다.")
        if st.button("확인", key="confirm_setup_go_tabs"):
            st.session_state["setup_saved"] = False
            st.rerun()

# App flow
if not st.session_state["profile"]:
    setup_view_v2()
else:
    tabs = st.tabs(["아동", "부모"])
    with tabs[0]:
        child_view_v2()
    with tabs[1]:
        parent_view_v2()
