# 개발·제출 자료

현재 제출 자료는 [functional-v1](functional-v1/README.md)입니다. 독립 검증,
실행 가능한 회귀 테스트 내보내기, JSON 없는 설정과 합성 자원 비교를 포함합니다.
이전 독립 FIFO 속성 제출 자료는 [property-v1](property-v1/README.md)에 보존했습니다.
이전 사용자 프로젝트 제출 자료는 [hackathon-2026](hackathon-2026/README.md)에
보존했습니다.
아래 자료들은 이전 개발 단계의 기록으로 보존합니다.

이전 확장은 [제한된 패치 탐색 비교](search-v1/)입니다.
[소스·증거 ZIP](search-v1/RTLRefine-search-evidence.zip),
[1분 28초 영상](search-v1/video/RTLRefine-constrained-search-demo.mp4),
[영문 설명](search-v1/DEVPOST_ABOUT.md)을 준비했습니다. 동일 후보 풀·각 최대
8회 검사에서 탐색만 사용하면 3/9, NVIDIA가 순서를 안내하면 4/9가 정해진
검사를 통과했습니다. 대조군은 둘 다 2/2이며 모델은 코드를 쓰지 않았습니다.
추가 통과는 FIFO B 경로만 바꾸므로 전체 뱅크 정확성으로 표현하지 않습니다.
기존 V2와는 계산 예산이 달라 합산하거나 동일 예산 성능 향상으로 주장하지 않습니다.

이전 별도 제출 준비본은 [알려진 버그 V2 평가](known-bugs-v2/)입니다.
[소스·증거 ZIP](known-bugs-v2/RTLRefine-known-bugs-v2-evidence.zip),
[1분 33초 영상](known-bugs-v2/video/RTLRefine-known-bugs-v2-demo.mp4),
[Devpost 설명](known-bugs-v2/DEVPOST_ABOUT.md)을 준비했습니다.
수정된 입력 영역·유효 출력 조건을 먼저 고정한 평가에서 자체 검토 1/9,
검증 피드백 2/9가 회귀 검사를 통과했습니다. 대조군 통과는 각각 1/2, 2/2입니다.
한 사례 차이를 일반적 성능 우위로 표현하지 않습니다. V1의 정상 코드 손상
해석은 오라클 입력 범위 오류라 철회했고 원본 기록은 별도 보존했습니다.

아래는 이전 개발 자료이며 각 실험의 범위와 결과를 합산하지 않습니다.

최신 외부 사례는 [ZipCPU UART CTS 실증](external-uart-v1/)입니다.
[독립 실행 소스 ZIP](external-uart-v1/RTLRefine-external-UART-source.zip)과
[검증 범위·실패 기록](../docs/EXTERNAL_UART.md)을 준비했습니다. NVIDIA 네 번째
응답을 그대로 실행해 12개 시뮬레이션·두 제한 깊이 속성 검사를 통과했으며,
초기 거부를 유발한 공백 파서의 사후 수정과 앞선 실패도 공개합니다.

이전 확장은 [명세 기반 인위적 오류 실험](mutation-v1/)입니다.
[전체 자료 ZIP](mutation-v1/RTLRefine-contract-submission.zip),
[1분 56초 새 영상](mutation-v1/video/RTLRefine-contract-demo.mp4),
[새 Devpost 설명](mutation-v1/DEVPOST_ABOUT.md)을 준비했습니다.
정답 RTL을 채점에 사용하지 않고 6/6 주입 사례의 NVIDIA 수정을 검증했습니다.
정상 대조군 2개 중 1개에 대한 불필요 수정도 공개하며, 과거 실제 버그 비교와
집계하거나 실제 현장 버그 발견으로 표현하지 않습니다.

이전 집중 제출 버전은 [RTLRefine 초기 최종 준비 폴더](rtlrefine-final/)에 있습니다.
[프로젝트 필드](rtlrefine-final/PROJECT_FIELDS.md),
[Devpost 영문 설명](rtlrefine-final/DEVPOST_ABOUT.md),
[소스 ZIP](rtlrefine-final/RTLRefine-source.zip)을 준비했습니다.
실제 사례 3개·직접 수정/업로드·독립 검증·9쌍 NVIDIA 비교가 포함됩니다.
비교 결과는 자체 리뷰 3/9, 검증 피드백 2/9로 우위 주장을 하지 않습니다.

**공식 제출 마감: 한국 시간 2026-10-31(토) 02:00.**
내부 제출 목표는 10/29이며 [공식 규정과 상세 일정](../docs/SUBMISSION_SCHEDULE.md)을 따른다.

제출 방향은 **RTLRefine: 웹 RTL 디버깅·수정 검증**으로 고정했습니다.
[RTL 홈](http://localhost:8501), [실제 FIFO 버그 사례](http://localhost:8501/reset),
[수상 경쟁력 검증 계획과 현재 한계](../docs/RTL_AWARD_PLAN.md)를 확인할 수 있습니다.
NVIDIA Ultra의 새 수정안이 실제 과거 RTL 버그의 세 회귀 검사와 16단계 비교를 통과했습니다.
새 버그 발견, 무제한 증명, AI 성능 우위는 주장하지 않습니다.
두 번째 [AXI 바이트 유효성 사례](http://localhost:8501/keep)는 실제 버그를 재현하고,
4/6만 통과하는 NVIDIA 부분 수정을 거부합니다. 관리자 수정본의 양성 대조군과
구분하며, 이 사례에서 성공한 NVIDIA 수정은 아직 없습니다.
[두 번째 사례 증거 ZIP](rtl-keep/RTLRefine-AXI-byte-validity-evidence.zip)과
[158개 검사·브라우저 검증 기록](rtl-keep/VALIDATION.json)을 보존했습니다.
예약 실험실은 [별도 보존 ZIP](booking-lab/SpecWitness-booking.zip)에 있으며 RTL 제출 대상이 아닙니다.
이전 수치 명세 프로토타입은 [별도 ZIP](specwitness/SpecWitness-prototype.zip)과 [기록](../docs/SPECWITNESS.md)으로 보존했습니다.
아래 Devpost 초안과 영상은 이전 RTLRefine v3 기준입니다.

## 이전 RTLRefine 제출 자료 — v3

이전 버전은 **실제 NVDLA RTL 검토와 검증된 시프트 구조 탐색**을 포함합니다.
회로 선정·구현·실험·제출 자료 준비는 로컬에서 완료했고, 공개 게시는 아직 하지 않았습니다.

- [실행 화면 — 로컬 NVDLA 워크스페이스](http://localhost:8501/external)
- [프로젝트 이름·Elevator pitch](review-v3/PROJECT_FIELDS.md)
- [Devpost About the project 영문 초안](review-v3/DEVPOST_ABOUT.md)
- [새 영문 자막 데모 — 약 2분](video-external-v3/RTLRefine-NVDLA-demo.mp4)
- [소스 ZIP — 키·장부·도구 제외, 원본 라이선스 포함](review-v3/RTLRefine-source.zip)
- [최종 검증 기록](review-v3/VALIDATION.json), [소스 파일 해시](review-v3/SHA256SUMS.json)
- [외부 RTL 지원 범위](../docs/EXTERNAL_RTL.md), [알고리즘과 측정 결과](../docs/STICKY_SHIFT_SEARCH.md)

## 실제 외부 회로에서 확인한 결과

NVDLA 고정 커밋의 원본 산술 모듈 세 개를 가져왔습니다. 원본은 변경하지 않고,
기본 파라미터를 고정한 어댑터가 원본과 같은지 별도로 증명했습니다.
프로젝트에 구현한 sticky-shift 변환은 매 단계에서 가드·스티키 정보를 보존합니다.

| 모듈 | 라이브러리 면적 추정: 원본 → 기본 변환 | Xilinx LUT 합성 수: 원본 → 기본 변환 |
|---|---:|---:|
| 49→32 반올림 우측 시프트 | 785.232 → 714.210 (9.04% 감소) | 362 → 297 (17.96% 감소) |
| 49→32 양방향 시프트 | 1441.986 → 1276.534 (11.47% 감소) | 700 → 504 (28.00% 감소) |

두 변환 모두 22,272개 독립 정수 모델·시뮬레이션 입력과 32개 출력 비트 전체의
동등성 검증을 통과했습니다. 수치는 합성 추정이며 배치·배선, 타이밍, 전력,
FPGA 실기, NVDLA 전체 가속 성능은 측정하지 않았습니다. 모든 mux/carry 자원도
보존했고, 우측 시프트의 MUXF8 증가 같은 상충 결과도 표시합니다.

## NVIDIA 역할과 비교 근거

변환 알고리즘은 프로젝트에서 공급합니다. NVIDIA가 알고리즘을 발견했다고
주장하지 않습니다. NVIDIA는 허용된 단계 순서와 묶음을 제안하고, 컴파일러가
RTL을 만든 뒤 독립 도구가 검사합니다.

- 기본 배치 2개, 무작위 계획 8개, 실제 NVIDIA 계획 8개: 컴파일한 18개 모두 검증 통과.
- NVIDIA 탐색의 최선은 기본 변환과 같아서 추가 개선은 입증하지 못했습니다.
- 별도 직접 RTL 생성 비교는 24회 요청·6개 비교 쌍 완료: 7개 검증 통과, 17개 실패,
  해당 조건에서 라이브러리 면적 개선 없음. 이 결과도 보존했습니다.
- 이전 JSON-object 형식 실험은 21회 요청 후 형식 오류·시간 초과 등을 기록했고,
  엄격한 스키마를 쓴 24회 비교와 합산하지 않습니다.
- 실제 브라우저에서 새 NVIDIA 계획 요청 1회와 기본 회로 보존까지 확인했습니다.

## 검증·예산·남은 게시 작업

자동 검사 119개와 실제 Chrome의 회로 업로드, 원본·후보 증명, 합성,
추천 코드 및 라이선스 포함 증거 ZIP 다운로드 검증이 통과했습니다.
기존 108회 비교 실험의 평가기 소스도 변경하지 않았습니다.

현재 누적 비용·예약 반영액은 약 **$1.18 / $50**입니다. 응답을 받지 못한
요청 두 건의 보수적 예약을 유지하며 실제 청구서는 별도로 확인해야 합니다.

```bash
python3 -m streamlit run app.py
```

실제 외부 개발자의 사용성 평가, 공개 저장소, 심사용 배포, YouTube 업로드,
Devpost 최종 제출은 아직 완료하지 않았습니다. 자동 브라우저 검증을 실제
사용자 평가로 표현하지 않습니다. 이전 v1·v2 자료와 영상은 별도로 보존합니다.
