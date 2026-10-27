# 이번 개선을 제출에 반영하기

1. 새 영상 `video/RTLRefine-independent-properties-demo.mp4`를 YouTube에
   **새로 업로드**하고 공개(Public)로 설정합니다. 기존 영상 URL의 내용을
   교체하는 방식이 아닙니다. 제목과 설명은 `YOUTUBE.md`를 사용합니다.
2. Devpost의 Video URL을 새 YouTube 주소로 바꿉니다. 기존 영상은 추가 링크로
   남겨도 됩니다. 새 영상은 독립 FIFO 속성 검증과 실제 수리를 보여줍니다.
3. About에는 `DEVPOST_ABOUT.md`를 붙여 넣습니다. 개인 참가 기준으로 I를
   사용했습니다. 프로젝트명은 같고, 피치와 실행 안내는 `PROJECT_FIELDS.md`를
   사용합니다. 테스트 빌드 URL은 v1.3.0으로 갱신합니다.
4. 갤러리에는 `screenshots/05-exact-count-fix-and-bounds.png`를 먼저 넣고,
   `01-smoke-pass-independent-failure.png`를 함께 넣습니다.
5. 도구 피드백을 갱신하고 최종 제출 상태를 확인합니다. 이미 제출했다면
   수정 내용이 저장됐는지 확인합니다.

검증 범위: 이번 FIFO 모드는 명시된 단일 클록·동기 리셋 계약을 사용합니다.
예제 결함 3개는 직접 구성한 사례이며 실제 외부 버그 3개를 새로 발견하거나
모두 모델로 고쳤다는 뜻이 아닙니다. 28단계 시간 초과 기록은 미검증으로
보존했고 기본 최종 검사 범위는 16·20단계입니다.
