# Gemini + Google Places 여행 추천 프로그램

## 1. 프로젝트 소개
이 프로그램은 사용자가 입력한 여행 날짜를 기준으로,  
Gemini API를 이용해 한국의 추천 여행지를 1곳 선정하고,  
Google Places API를 이용해 해당 지역의 맛집 5곳을 검색하여  
JSON 파일과 Markdown 보고서로 저장하는 CLI 프로그램입니다.

---

## 2. 주요 기능
1. CLI 인자 `-date "YYYY-MM-DD"` 형태로 여행 날짜 입력
2. 입력 날짜 형식 검증
3. `.env` 파일에서 API 키 및 모델 정보 로드
4. Gemini API를 이용한 여행지 추천
5. Google Places API를 이용한 맛집 5곳 검색
6. 결과를 `results` 폴더에 JSON / Markdown 파일로 저장
7. 오류 발생 시 `errors` 배열에 기록
8. Gemini 모델 호출 실패 시 다른 모델로 자동 대체
9. 429(속도 제한) 발생 시 재시도 후 fallback 수행

---

## 3. 사용 기술
- Python
- Gemini API
- Google Places API
- requests
- python-dotenv

---

## 4. 실행 환경
- Python 3.10 이상 권장

---

## 5. 설치 방법

### 5-1. 필요한 패키지 설치
```bash
pip install requests python-dotenv
