# Yatzy 게임 프로젝트

## 1. 프로젝트 개요

본 프로젝트는 주사위 게임인 Yatzy를 Python의 `pygame` 라이브러리를 사용하여 구현한 2인용 보드게임이다. 이 프로그램은 표준 Yatzy 규칙을 따르면서도, 외부 API를 적용함으로써 사용자 경험과 기술적 완성도를 높이는 데 중점을 두었다. 사용자는 주사위를 굴리고, 점수를 기록하며, 턴이 끝날 때까지 외부 명언 API를 통해 제공되는 조언을 볼 수 있다. 이를 통해 게임의 긴장도를 높이고 지루함을 줄였다.

## 2. 구현 기능 및 핵심 규칙

### Yatzy 규칙

프로젝트에 구현된 Yatzy의 핵심 규칙은 다음과 같다.

| 카테고리 | 규칙 | 구현 방식 |
| :--- | :--- | :--- |
| **Upper Section (Aces~Sixes)** | 해당 숫자가 나온 주사위의 합을 점수로 기록한다.(숫자 * 개수) | `calc_score` 함수에서 해당 숫자의 개수와 값을 곱하여 계산한다. |
| **Upper Section 보너스** | Aces부터 Sixes까지의 점수 합계가 63점 이상일 경우, 총점에 35점이 보너스 점수로 부여된다. | `Player.bonus()` 메서드가 이 조건을 확인하고 35점을 반환하도록 구현되었다. |
| **Yatzy 점수 부여** | 5개의 주사위가 모두 같은 숫자일 때 Yatzy를 달성하며, 'Yatzy' 카테고리를 선택하면 50점을 얻는다. | `click_score` 함수에서 `is_yat` 조건을 확인하여 'Yatzy' 카테고리에만 50점을 할당한다. 다른 카테고리를 선택하면 `calc_score` 결과가 적용된다(오류 수정). |
| **Lower Section** | 3/4 of a Kind, Full House, Small/Large Straight, Chance 등의 표준 계산 로직이 `calc_score` 함수에 구현되어 있다. | 예를 들어, Large Straight는 `[1,2,3,4,5]` 또는 `[2,3,4,5,6]`을 달성했을 때만 점수(40점)를 계산한다. |

### 기술적 구현 상세

| 구현 항목 | 상세 내용 |
| :--- | :--- |
| **비동기 API 처리** | 외부 명언 API (`https://api.adviceslip.com/advice`) 호출을 `threading` 모듈을 사용한 비동기 스레드로 실행한다. |
| **성능 최적화** | API 통신으로 인한 메인 UI 루프의 멈춤 현상(렉)을 완전히 방지하여 부드러운 사용자 경험을 제공한다(개선점 반영). |
| **코드 구조** | `Player` 클래스는 상태 및 점수 관리를, `Game` 클래스는 이벤트 처리 및 렌더링을 담당하는 객체 지향적으로 구성되었다. |
| **환경 재현** | `pyproject.toml` 및 `uv.lock` 파일을 포함하여 `uv` 도구를 통해 동일한 Python 환경을 정확하게 재현할 수 있도록 구성되었다. |

## 3. 환경 설정 및 실행 방법

본 프로젝트는 `uv` 패키지 관리 도구를 사용하여 환경을 재현한다.

### 1) 의존성 설치 및 환경 재현

프로젝트 루트 디렉토리에서 다음 명령어를 순서대로 실행하여 필요한 환경을 구축할 수 있다.

1. 가상 환경 생성
```bash
uv venv
```

2. 가상 환경 활성화
```bash
source .venv/bin/activate #(Linux/macOS)
```
```bash
venv\Scripts\activate.bat #(Windows Command Prompt)
```

3. pyproject.toml 및 uv.lock 파일에 정의된 의존성 설치 및 동기화
```bash
uv sync
```

### 2) 게임 실행

가상 환경이 활성화된 상태에서 메인 스크립트를 실행한다.
```bash
python yatzy_advice_3.py
```

## 4. 파일 목록

| 파일 / 디렉토리 | 설명 |
| :--- | :--- |
| yatzy_advice_3.py | 게임 소스 코드 |
| pyproject.toml | uv 환경 재현을 위한 설정 파일 |
| uv.lock | uv 환경 재현을 위한 잠금 파일 |
| README.md | 프로젝트 설명 파일 |

## 5. API Key

본 프로젝트에서 사용하는 API는 별도의 API Key 및 환경 변수를 요구하지 않는다.
