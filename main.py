import os
import json
import re
import time
import argparse
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv


class GeminiAPIError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(message)


def load_api_config():
    load_dotenv()

    gemini_api_key = os.getenv("GEMINI_API_KEY")
    google_api_key = os.getenv("GOOGLE_API_KEY")
    gemini_model = os.getenv("GEMINI_MODEL")

    missing = []
    if not gemini_api_key:
        missing.append("GEMINI_API_KEY")
    if not google_api_key:
        missing.append("GOOGLE_API_KEY")
    if not gemini_model:
        missing.append("GEMINI_MODEL")

    if missing:
        raise ValueError(f".env 파일에 다음 환경변수가 필요합니다: {', '.join(missing)}")

    return gemini_api_key, google_api_key, gemini_model


def validate_date(date_text: str) -> str:
    try:
        datetime.strptime(date_text, "%Y-%m-%d")
        return date_text
    except ValueError:
        raise ValueError("날짜 형식이 올바르지 않습니다. 예: 2026-08-16")


def list_available_gemini_models(api_key: str) -> list:
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    response = requests.get(url, timeout=20)
    response.raise_for_status()

    data = response.json()
    models = []

    for model in data.get("models", []):
        name = model.get("name", "")
        methods = model.get("supportedGenerationMethods", [])
        if "generateContent" in methods:
            models.append(name.replace("models/", ""))

    return models


def is_text_gemini_model(model_name: str) -> bool:
    name = model_name.lower()

    blocked_keywords = [
        "tts",
        "image",
        "embedding",
        "aqa",
        "vision",
        "transcribe",
        "gemma"
    ]

    if any(keyword in name for keyword in blocked_keywords):
        return False

    return name.startswith("gemini")


def build_model_candidates(api_key: str, preferred_model: str) -> list:
    available_models = list_available_gemini_models(api_key)
    filtered_models = [m for m in available_models if is_text_gemini_model(m)]

    if not filtered_models:
        raise RuntimeError("사용 가능한 텍스트 Gemini 모델을 찾지 못했습니다.")

    priority = [
        preferred_model,
        "gemini-pro-latest",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-1.5-pro",
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-pro"
    ]

    candidates = []

    for target in priority:
        if target in filtered_models and target not in candidates:
            candidates.append(target)

    for target in priority:
        for model in filtered_models:
            if target and target in model and model not in candidates:
                candidates.append(model)

    for model in filtered_models:
        if model not in candidates:
            candidates.append(model)

    return candidates


def build_prompt(travel_date: str) -> str:
    return f"""
당신은 한국 여행 추천 도우미입니다.
사용자의 여행 날짜는 {travel_date} 입니다.

다음 조건을 만족하는 결과를 JSON만 출력하세요.
설명문, 코드블록, 마크다운 없이 순수 JSON만 반환하세요.

조건:
1. 한국의 여행지 1곳만 추천
2. recommended_city: 도시명
3. weather_summary: 그 날짜 여행하기 좋은 날씨라고 가정한 간단한 설명
4. festivals: 해당 시기 즐길 수 있는 축제/행사 리스트 (없으면 빈 리스트)
5. reason: 추천 이유를 2~3문장으로 작성

반드시 아래 형식으로만 출력:
{{
  "recommended_city": "도시명",
  "weather_summary": "날씨 요약",
  "festivals": ["축제1", "축제2"],
  "reason": "추천 이유"
}}
""".strip()


def call_gemini_once(prompt: str, api_key: str, model: str, temperature: float = 0.3) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "temperature": temperature
        }
    }

    response = requests.post(url, json=payload, timeout=30)

    if response.status_code != 200:
        try:
            error_data = response.json()
            error_message = json.dumps(error_data, ensure_ascii=False)
        except Exception:
            error_message = response.text[:300]

        raise GeminiAPIError(
            response.status_code,
            f"{response.status_code} 오류 - {model} - {error_message}"
        )

    data = response.json()
    candidates = data.get("candidates", [])
    if not candidates:
        raise ValueError("Gemini 응답에 candidates가 없습니다.")

    content = candidates[0].get("content", {})
    parts = content.get("parts", [])
    text = "".join(part.get("text", "") for part in parts).strip()

    if not text:
        raise ValueError("Gemini 응답 텍스트가 비어 있습니다.")

    return text


def call_gemini_with_retry_and_fallback(prompt: str, api_key: str, preferred_model: str):
    candidates = build_model_candidates(api_key, preferred_model)
    retry_waits = [5, 10, 20]

    last_error = None

    for model in candidates:
        print(f"[시도] Gemini 모델 호출: {model}")

        for attempt in range(len(retry_waits) + 1):
            try:
                text = call_gemini_once(prompt, api_key, model)
                return text, model

            except GeminiAPIError as e:
                last_error = e

                if e.status_code == 429:
                    if attempt < len(retry_waits):
                        wait_time = retry_waits[attempt]
                        print(f"[경고] {model} 429 제한 발생 -> {wait_time}초 후 재시도")
                        time.sleep(wait_time)
                        continue
                    else:
                        print(f"[경고] {model} 429 재시도 초과 -> 다음 모델로 이동")
                        break

                elif e.status_code in [400, 404]:
                    print(f"[경고] {model} 사용 불가 -> 다음 모델로 이동")
                    break

                else:
                    print(f"[경고] {model} 실패: {e}")
                    break

            except Exception as e:
                last_error = e
                print(f"[경고] {model} 실패: {e}")
                break

    raise RuntimeError(f"모든 Gemini 모델 호출 실패: {last_error}")


def extract_json_text(text: str) -> str:
    text = text.strip()

    json_block = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if json_block:
        return json_block.group(1).strip()

    code_block = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
    if code_block:
        return code_block.group(1).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and start < end:
        return text[start:end + 1]

    return text


def parse_recommendation_json(text: str) -> dict:
    json_text = extract_json_text(text)

    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Gemini JSON 파싱 실패: {e}")

    required_keys = ["recommended_city", "weather_summary", "festivals", "reason"]
    for key in required_keys:
        if key not in data:
            raise ValueError(f"Gemini 응답에 '{key}' 필드가 없습니다.")

    if not isinstance(data["festivals"], list):
        data["festivals"] = []

    return data


def search_restaurants(city: str, google_api_key: str, max_results: int = 5) -> list:
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {
        "query": f"{city} 맛집",
        "language": "ko",
        "key": google_api_key
    }

    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()

    data = response.json()
    status = data.get("status")

    if status not in ("OK", "ZERO_RESULTS"):
        error_message = data.get("error_message", "알 수 없는 오류")
        raise RuntimeError(f"Google Places API 오류: {status} - {error_message}")

    restaurants = []
    seen = set()

    for place in data.get("results", []):
        name = place.get("name", "").strip()
        if not name or name in seen:
            continue

        seen.add(name)
        restaurants.append({
            "name": name,
            "address": place.get("formatted_address", "주소 정보 없음"),
            "rating": place.get("rating", "평점 정보 없음")
        })

        if len(restaurants) >= max_results:
            break

    return restaurants


def create_markdown_report(result: dict) -> str:
    festivals = result.get("festivals", [])
    restaurants = result.get("restaurants", [])
    errors = result.get("errors", [])

    festival_lines = "\n".join([f"- {festival}" for festival in festivals]) if festivals else "- 없음"
    restaurant_lines = "\n".join([
        f"- **{r['name']}** | 주소: {r['address']} | 평점: {r['rating']}"
        for r in restaurants
    ]) if restaurants else "- 없음"
    error_lines = "\n".join([f"- {e}" for e in errors]) if errors else "- 없음"

    md = f"""# 여행 추천 리포트

## 여행 날짜
- {result.get("travel_date", "")}

## 추천 여행지
- {result.get("recommended_city", "")}

## 날씨 요약
- {result.get("weather_summary", "")}

## 축제 / 행사
{festival_lines}

## 추천 이유
- {result.get("reason", "")}

## 추천 맛집
{restaurant_lines}

## 사용 모델
- {result.get("gemini_model", "")}

## 오류 로그
{error_lines}
"""
    return md


def save_results(result: dict, travel_date: str):
    results_dir = Path("results")
    results_dir.mkdir(exist_ok=True)

    file_stem = travel_date.replace("-", "")
    json_path = results_dir / f"trip_{file_stem}.json"
    md_path = results_dir / f"trip_{file_stem}.md"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    markdown_text = create_markdown_report(result)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(markdown_text)

    return json_path, md_path


def main():
    parser = argparse.ArgumentParser(description="Gemini + Google Places 여행 추천 프로그램")
    parser.add_argument("-date", required=True, help='여행 날짜 (형식: "YYYY-MM-DD")')
    args = parser.parse_args()

    errors = []
    recommendation = {}
    restaurants = []
    final_model = ""
    travel_date = ""

    try:
        travel_date = validate_date(args.date)
        print(f"[1] 입력 날짜 확인: {travel_date}")

        gemini_api_key, google_api_key, gemini_model = load_api_config()
        print("[2] API 키 로드 완료")

        model_candidates = build_model_candidates(gemini_api_key, gemini_model)
        print(f"[3] Gemini 모델 후보: {', '.join(model_candidates[:5])}")

        prompt = build_prompt(travel_date)
        gemini_text, final_model = call_gemini_with_retry_and_fallback(
            prompt,
            gemini_api_key,
            gemini_model
        )

        recommendation = parse_recommendation_json(gemini_text)
        print(f"[4] 여행 추천 생성 완료 (사용 모델: {final_model})")

        city = recommendation.get("recommended_city", "").strip()
        if city:
            restaurants = search_restaurants(city, google_api_key)
            print(f"[5] 맛집 검색 완료: {len(restaurants)}곳")
        else:
            print("[5] 추천 도시 정보가 없어 맛집 검색을 건너뜁니다")

        result = {
            "travel_date": travel_date,
            "recommended_city": recommendation.get("recommended_city", ""),
            "weather_summary": recommendation.get("weather_summary", ""),
            "festivals": recommendation.get("festivals", []),
            "reason": recommendation.get("reason", ""),
            "restaurants": restaurants,
            "gemini_model": final_model,
            "errors": errors
        }

        json_path, md_path = save_results(result, travel_date)
        print("[6] 결과 저장 완료")
        print(f" - JSON: {json_path}")
        print(f" - Markdown: {md_path}")

    except Exception as e:
        errors.append(str(e))
        print(f"[오류] {e}")

        if travel_date:
            result = {
                "travel_date": travel_date,
                "recommended_city": recommendation.get("recommended_city", ""),
                "weather_summary": recommendation.get("weather_summary", ""),
                "festivals": recommendation.get("festivals", []),
                "reason": recommendation.get("reason", ""),
                "restaurants": restaurants,
                "gemini_model": final_model,
                "errors": errors
            }
            save_results(result, travel_date)


if __name__ == "__main__":
    main()