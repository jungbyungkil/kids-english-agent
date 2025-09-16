## Kids English Agent

A family-friendly English learning assistant for children (ages 0–7+). 
The app recommends YouTube videos by age/CEFR and turns watched videos into bite‑size learning (top vocabulary, sentences, cheering sounds). 

가볍게 실행되는 **AI 에이전트 MVP**입니다.  
- 모델: Azure OpenAI (gpt-4.1-mini)
- 도구: Azure AI Search (RAG), Quick Calculator
- UI: Streamlit

아동용 영어 학습 도우미
🎯 목표
아이가 스스로 재미있게 영어와 친해지도록 동기 부여
나이·수준 맞춤 커리큘럼 & 자료 제공
선호 캐릭터 기반 시청·읽기 추천
지역·예산 맞춤 학원/튜터 탐색
부모용 진척·비용 리포트 제공

📌 주요 기능
나이별 커리큘럼
영어 수준 진단(CEFR 매핑)
리딩·리스닝·스피킹 평가 → 레벨(A0~B1)
콘텐츠 추천
캐릭터·주제별 에피소드, 리더스북, 활동지
학원/튜터 탐색
진척 관리 & 리워드
체크·스티커, 주간 리포트
부모 가이드

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
## URL > 

https://demo-kingbk-d6feb5awbrecd9ha.westus-01.azurewebsites.net/
