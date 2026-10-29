# 최신 UART 실증 제출 자료

1. `video/RTLRefine-UART-peer-demo.mp4`를 YouTube Public으로 올립니다.
   실제 모델 결과는 저장된 실행이라고 표시했고, native 검사는 새로 실행했습니다.
2. About을 `DEVPOST_ABOUT.md`, 도구 피드백을 `NEBIUS_FEEDBACK.md`로 갱신합니다.
   개인 참가자 I 문구이며, 실제 UART 여섯 요청과 실패를 함께 설명합니다.
3. 테스트 빌드는 `PROJECT_FIELDS.md`의 v1.6.0 주소, Video URL은 새 영상 주소로
   교체합니다. 갤러리는 실제 UART 비트·모델 기록·CI 결과 화면을 사용합니다.
4. 트랙은 Coding and Agentic Engineering입니다. 최종 제출 후 Submitted 상태와
   로그인하지 않은 상태의 저장소·영상 접근을 확인합니다.

UART 사례는 알려진 과거 비트 순서 변경을 명시적 LSB-first peer 계약으로 검사한
것입니다. 새로운 버그 발견이나 최근 도입된 회귀로 표현하지 않습니다. 루프백만
검사하는 원본 프로젝트의 PASS는 그 제한된 테스트 범위입니다. TX/RX 두 모듈의
소유자는 verilog-axis와 같은 Alex Forencich이므로 독립 저자 수를 부풀리지 않습니다.

추가 요청은 여섯 번, 기록된 추정 비용은 $0.085415입니다. 마지막 성공 실행만
따로 두 요청이라고 표시하며 전체가 두 요청만 사용했다고 쓰지 않습니다.
같은 검사를 원본/복원 소스에 실행한 0→1→0은 회귀 검출 실증입니다.
