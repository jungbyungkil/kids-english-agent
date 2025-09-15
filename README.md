# Kids English Agent (Visual Studio / Windows)

가볍게 실행되는 **AI 에이전트 MVP**입니다.  
- 모델: Azure OpenAI (gpt-4.1-mini)
- 도구: Azure AI Search (RAG), Quick Calculator
- UI: Streamlit

## 1) 환경 준비 (Windows, PowerShell)
```powershell
# 라이브러리 설치용 가상환경 만들기 (uv 권장)
uv venv
uv pip install -r requirements.txt

# (또는) pip 사용
# py -m venv .venv
# .\.venv\Scripts\activate
# pip install -r requirements.txt
```

## 2) 환경변수(.env) 설정
`.env.example`를 복사하여 `.env`를 만들고 값 채우기:
```
AZURE_OPENAI_ENDPOINT=https://<your-openai>.openai.azure.com
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_DEPLOYMENT=dev-gpt-4.1-mini

AZURE_SEARCH_ENDPOINT=https://<your-search>.search.windows.net
AZURE_SEARCH_API_KEY=...
AZURE_SEARCH_INDEX=kidsenglish
```

## 3) 실행
```powershell
streamlit run streamlit_app.py
```

## 4) Visual Studio에서 열기
- Visual Studio에서 "열기 > 폴더 열기"로 이 폴더 선택
- Python 환경을 uv/venv로 설정
- "도구 > Python > 환경"에서 가상환경 선택
- "디버그 시작"을 `streamlit run streamlit_app.py`로 설정하여 실행

## 구조
```
kids-english-agent/
  app/
    agent.py           # Azure OpenAI 도구 호출 루프
    tools.py           # search_docs, quick_calc 라우터
    search_client.py   # Azure AI Search REST 클라이언트
    prompts.py         # 시스템 프롬프트
  streamlit_app.py     # 챗 UI
  requirements.txt
  .env.example
  README.md
```

## 체크리스트
- 401/404 발생 시: 엔드포인트/키/배포명 확인
- AI Search 인덱스가 비어있다면, 임시로 quick_calc로 동작 여부 확인
- 회사 프록시/방화벽 환경이면 http/https 프록시 설정 필요

행운을 빕니다! 🚀
# kids-english-agent
