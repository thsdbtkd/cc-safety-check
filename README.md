# 클로드 코드 안전 점검기 (cc-safety-check)

명령 한 줄로 이 컴퓨터의 클로드 코드 설정을 읽고, 사고가 나기 쉬운 빈칸을 1분 안에 보여 줍니다.

- **읽기만 합니다.** 설정 파일을 고치지 않고, 인터넷으로 아무것도 보내지 않습니다(코드에 네트워크 호출 0줄).
- 파이썬 3.8 이상, 표준 라이브러리만. 맥·리눅스에서 시험했습니다(윈도우는 아직 시험 전).

```bash
python3 cc_safety_check.py --project /내/프로젝트/경로
```

## 무엇을 보나 (8문항)
| 문항 | 점검 | 보는 곳 |
|:-|:-|:-|
| A5 | 「확인 없이 전부 실행」 모드를 잠갔나 | `permissions.disableBypassPermissionsMode` |
| B1 | 기본 권한 모드가 자동 승인이 아닌가 | `permissions.defaultMode` |
| A3 | 비밀 파일(.env · 키 파일) 읽기를 막았나 | `permissions.deny` 의 Read 규칙 |
| A4 | 위험 명령을 실행 전에 막나 | `permissions.deny` 의 Bash 규칙 · 실행 전 훅 · 「모든 셸 명령 허용」 규칙 |
| C1 | 샌드박스를 켰나 | `sandbox.enabled` |
| D1 | 「끝났습니다」 전에 기계 확인을 거치나 | 마감 훅(Stop) |
| E2 | 같은 오류가 이어지면 멈추나 | 실행 뒤 훅(PostToolUse) |
| A9 | 연결 도구(MCP 서버) 목록 | `~/.claude.json` · `.mcp.json` |

읽는 설정 파일: `~/.claude/settings.json` · `.claude/settings.json` · `.claude/settings.local.json` · 조직 관리 설정(`/Library/Application Support/ClaudeCode/managed-settings.json`, `/etc/claude-code/managed-settings.json`).
근거: 클로드 코드 공식 문서 [권한](https://code.claude.com/docs/en/permissions) · [설정](https://code.claude.com/docs/en/settings) · [샌드박스](https://code.claude.com/docs/en/sandboxing), OWASP 에이전트 응용 상위 10(2026판) ASI02 · ASI05.

점수: 「아니오·모름」 문항의 점수 합 ÷ 해당 문항 점수 합. 3점 = 되돌릴 수 없는 손실 · 2점 = 복구는 되지만 크게 듦. 50% 이상이거나 3점 빈칸이 3개 이상이면 「높음」.

## 예시 — 만든 사람의 맥에서 돌린 결과 (2026-11-10)
```
위험 비율 68.4% · 구간 「높음」 · 3점 빈칸 3개 (A5, A3, C1)
먼저 고칠 3개
  · A3 비밀 파일(.env · 키 파일) 읽기를 막았다 → "deny": ["Read(./.env)", "Read(./.env.*)", "Read(~/.ssh/**)"]
  · A5 「확인 없이 전부 실행」 모드를 잠갔다 → "disableBypassPermissionsMode": "disable"
  · C1 샌드박스를 켰다 → "sandbox": {"enabled": true}
```

## 한계 (숨기지 않습니다)
- 훅이 **있는지**만 봅니다. 훅이 무엇을 확인하는지는 읽지 못해 「모름」으로 표시합니다.
- 사람이 답해야 하는 문항(깃 브랜치 보호 · 배포 승인 · 백업 복구 · 자료 기준)은 보지 않습니다. 그 문항까지 보려면 37문항 진단표를 쓰세요.
- 설정 파일로 알 수 없는 것(실제 세션에서 쓰는 권한 모드 · 플러그인 훅이 켜져 있는지)은 클로드 코드의 `/status` · `/hooks` 화면으로 확인하세요.

## 자가 시험
```bash
python3 test_checker.py
```
시험용 설정 네 가지(빈 설정 · 잠근 설정 · 넓게 연 설정 · 깨진 설정)를 임시 폴더에 만들어 돌리고, 내 컴퓨터 설정은 건드리지 않습니다. 결과 20/20 (2026-11-10).

## 만든 곳
AI가드레일 — 클로드 코드 실행 전 관문(보호 파일 · 완료 보고 검수 · 같은 오류 3번 멈춤 · 팀 PC별 개통 시험) 설치. 크몽에서 「AI가드레일」을 찾으세요.

라이선스: MIT (LICENSE). 그대로 제공되며, 이 점검기 결과만으로 안전을 보장하지 않습니다.
