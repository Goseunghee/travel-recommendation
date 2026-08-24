# 🌍 Gemini + Google Places 여행 추천 프로그램

## 📌 1. 프로젝트 소개

이 프로그램은 사용자가 입력한 여행 날짜를 기준으로 **Gemini API를 이용해 한국의 추천 여행지를 1곳 선정**하고, 추천된 지역을 **Google Places API를 이용하여 검색한 후 맛집 5곳을 찾아주는 CLI(Command Line Interface) 프로그램**이다.

사용자가 `YYYY-MM-DD` 형식으로 여행 날짜를 입력하면 먼저 날짜 형식을 검증한다. 이후 Gemini API에 여행지 추천을 요청하고, Gemini에서 반환된 결과를 JSON 형태로 구조화하여 추천 여행지 정보를 추출한다.

추출한 추천 여행지를 Google Places API의 검색어로 활용하여 해당 지역의 맛집을 검색하고, 검색 결과를 정리하여 JSON 파일과 Markdown 보고서로 저장한다.

또한 외부 API를 사용하는 과정에서 발생할 수 있는 다양한 오류에 대응하기 위해 오류 내용을 `errors` 배열에 기록하고, Gemini 모델 호출 실패 시 다른 모델로 자동 대체하는 fallback 기능과 429 오류 발생 시 재시도하는 기능을 구현하였다.

### 🔄 전체 프로그램 흐름

```text
👤 사용자
   ↓
📅 여행 날짜 입력
   ↓
🐍 Python 프로그램
   ↓
✅ 날짜 형식 검증
   ↓
🤖 Gemini API
   ↓
🌍 추천 여행지 1곳 선정
   ↓
🧩 JSON 형태로 결과 구조화
   ↓
📌 추천 도시 추출
   ↓
📍 Google Places API
   ↓
🍽️ 해당 지역 맛집 검색
   ↓
⭐ 맛집 5곳 선정
   ↓
💾 JSON 파일 저장
   ↓
📝 Markdown 보고서 저장
