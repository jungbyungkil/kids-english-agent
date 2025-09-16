## Kids English Agent

A family-friendly English learning assistant for children (ages 0–7+). 
The app recommends YouTube videos by age/CEFR and turns watched videos into bite‑size learning (top vocabulary, sentences, cheering sounds). 

가볍게 실행되는 **AI 에이전트 MVP**입니다.  
- 모델: Azure OpenAI (gpt-4.1-mini)
- 도구: Azure AI Search (RAG), Quick Calculator
- UI: Streamlit

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


