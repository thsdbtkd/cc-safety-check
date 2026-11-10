#!/usr/bin/env python3
"""클로드 코드 안전 점검기 (AI가드레일, 무료 공개판)

이 컴퓨터의 클로드 코드 설정 파일을 읽기만 해서, 사고가 나기 쉬운 빈칸을 1분 안에 보여 줍니다.
- 아무것도 고치지 않고, 아무 데도 보내지 않습니다(인터넷 연결을 쓰지 않음).
- 파이썬 3.8 이상, 표준 라이브러리만 씁니다. 맥·리눅스에서 시험했습니다.

사용:  python3 cc_safety_check.py            (지금 폴더를 프로젝트로 봄)
       python3 cc_safety_check.py --project 경로
       python3 cc_safety_check.py --json     (결과를 JSON으로)

근거: 클로드 코드 공식 문서 code.claude.com/docs/en/permissions · /settings · /sandboxing
      OWASP 에이전트 응용 상위 10(2026판) ASI02 도구 오용 · ASI05 예상 밖 코드 실행
"""
import argparse, json, os, sys
from pathlib import Path

VERSION = "0.1.0"
MANAGED = [Path("/Library/Application Support/ClaudeCode/managed-settings.json"), Path("/etc/claude-code/managed-settings.json")]


def load(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except Exception as e:
        return {"__error__": str(e)}


def gather(home, project):
    files = [("사용자", home / ".claude" / "settings.json"),
             ("프로젝트 공유", project / ".claude" / "settings.json"),
             ("프로젝트 개인", project / ".claude" / "settings.local.json")] + [("조직 관리", m) for m in MANAGED]
    found = []
    for scope, p in files:
        d = load(p)
        if d is not None:
            found.append((scope, p, d))
    return found


def merged(found):
    perm = {"allow": [], "deny": [], "ask": []}
    mode, bypass_locked, sandbox, hooks = None, False, False, {}
    for scope, p, d in found:
        if not isinstance(d, dict) or "__error__" in d:
            continue
        pm = d.get("permissions") or {}
        for k in perm:
            perm[k] += [str(x) for x in (pm.get(k) or [])]
        if pm.get("defaultMode"):
            mode = pm.get("defaultMode") if (mode is None or scope == "조직 관리") else mode
        if str(pm.get("disableBypassPermissionsMode", "")).lower() == "disable":
            bypass_locked = True
        sb = d.get("sandbox") or {}
        if isinstance(sb, dict) and sb.get("enabled") is True:
            sandbox = True
        for ev, arr in (d.get("hooks") or {}).items():
            hooks.setdefault(ev, 0)
            hooks[ev] += len(arr or [])
    return perm, mode, bypass_locked, sandbox, hooks


def extra_hook_files(home):
    out = []
    for base in [home / ".claude" / "hooks", home / ".claude" / "plugins"]:
        if base.exists():
            for p in base.rglob("hooks.json"):
                if "marketplaces" in p.parts:
                    continue
                d = load(p)
                if isinstance(d, dict) and isinstance(d.get("hooks"), dict):
                    out.append((p, sorted(d["hooks"].keys())))
    return out


def mcp_servers(home, project):
    names = set()
    d = load(home / ".claude.json")
    if isinstance(d, dict):
        names |= set((d.get("mcpServers") or {}).keys())
        pr = (d.get("projects") or {}).get(str(project)) or {}
        names |= set((pr.get("mcpServers") or {}).keys())
    m = load(project / ".mcp.json")
    if isinstance(m, dict):
        names |= set((m.get("mcpServers") or {}).keys())
    return sorted(names)


def claude_md(home, project):
    out = []
    for p in [home / ".claude" / "CLAUDE.md", project / "CLAUDE.md", project / ".claude" / "CLAUDE.md"]:
        if p.exists():
            out.append((p, len(p.read_text(encoding="utf-8", errors="ignore"))))
    return out


def check(home, project):
    found = gather(home, project)
    perm, mode, bypass_locked, sandbox, hooks = merged(found)
    deny = " ".join(perm["deny"]).lower()
    allow = perm["allow"]
    extra = extra_hook_files(home)
    extra_events = sorted({e for _, evs in extra for e in evs})
    all_events = set(hooks) | set(extra_events)
    items = []

    def add(code, pts, title, ok, why, fix):
        items.append({"문항": code, "점수": pts, "점검": title, "답": ok, "근거": why, "고치는 법": fix})

    add("A5", 3, "「확인 없이 전부 실행」 모드를 잠갔다", "예" if bypass_locked else "아니오",
        "permissions.disableBypassPermissionsMode = \"disable\" " + ("있음" if bypass_locked else "없음"),
        'settings.json 의 "permissions" 안에 "disableBypassPermissionsMode": "disable"')
    risky_mode = mode in ("bypassPermissions", "auto", "acceptEdits")
    add("B1", 3, "기본 권한 모드가 자동 승인이 아니다", "아니오" if risky_mode else "예",
        "defaultMode = {}".format(mode or "설정 없음(매번 확인)"),
        "바깥 글(이슈·웹페이지)을 읽는 작업에서는 자동 승인 모드를 쓰지 않기")
    secret = any(k in deny for k in (".env", ".ssh", "secret", "credential", ".aws", "id_rsa"))
    add("A3", 3, "비밀 파일(.env · 키 파일) 읽기를 막았다", "예" if secret else "아니오",
        "deny 규칙에 비밀 파일 경로 " + ("있음" if secret else "없음"),
        '"deny": ["Read(./.env)", "Read(./.env.*)", "Read(~/.ssh/**)"]')
    wide = [a for a in allow if a.strip() in ("Bash", "Bash(*)", "Bash(**)")]
    danger_deny = any(k in deny for k in ("bash(rm", "bash(git push", "bash(sudo", "bash(curl"))
    pre = "PreToolUse" in all_events
    a4 = "아니오" if wide else ("예" if (danger_deny or pre) else "아니오")
    add("A4", 3, "위험 명령을 실행 전에 막는다", a4,
        ("모든 셸 명령 허용 규칙 있음: " + ", ".join(wide)) if wide else
        ("deny 위험 명령 규칙 " + ("있음" if danger_deny else "없음") + " · 실행 전 훅(PreToolUse) " + ("있음(내용은 확인 못 함)" if pre else "없음")),
        "위험 명령 deny 규칙이나 실행 전 훅 두기(deny 규칙은 sh -c 안의 명령을 못 잡는다고 공식 문서가 밝힘)")
    add("C1", 3, "샌드박스를 켰다", "예" if sandbox else "아니오",
        "sandbox.enabled " + ("true" if sandbox else "없음(기본은 꺼짐)"),
        '"sandbox": {"enabled": true} 또는 세션에서 /sandbox')
    stop = "Stop" in all_events
    add("D1", 2, "「끝났습니다」 전에 기계 확인을 거친다", "모름" if stop else "아니오",
        "마감 훅(Stop) " + ("있음(무엇을 확인하는지는 못 읽음)" if stop else "없음"),
        "마감 훅으로 시험 결과·검사 기록이 없으면 마감을 막기")
    post = "PostToolUse" in all_events
    add("E2", 2, "같은 오류가 이어지면 자동으로 멈춘다", "모름" if post else "아니오",
        "실행 뒤 훅(PostToolUse) " + ("있음(반복 감지 여부는 못 읽음)" if post else "없음"),
        "같은 오류 3번이면 다음 호출을 막는 훅")
    mcp = mcp_servers(home, project)
    add("A9", 2, "연결 도구(MCP 서버)마다 만든 곳을 확인했다", "모름" if mcp else "해당 없음",
        "MCP 서버 {}개: {}".format(len(mcp), ", ".join(mcp) if mcp else "없음"),
        "서버마다 만든 곳·권한 범위를 표로 남기기")

    app = [i for i in items if i["답"] != "해당 없음"]
    tot = sum(i["점수"] for i in app)
    got = sum(i["점수"] for i in app if i["답"] in ("아니오", "모름"))
    ratio = round(got / tot * 100, 1) if tot else 0.0
    gaps3 = [i["문항"] for i in items if i["점수"] == 3 and i["답"] in ("아니오", "모름")]
    band = "높음" if (ratio >= 50 or len(gaps3) >= 3) else ("보통" if (ratio >= 20 or gaps3) else "낮음")
    top = sorted([i for i in items if i["답"] in ("아니오", "모름")], key=lambda x: (-x["점수"], x["문항"]))[:3]
    md = claude_md(home, project)
    return {"점검기": VERSION, "읽은 설정 파일": [str(p) for _, p, _ in found],
            "깨진 설정 파일": [str(p) for _, p, d in found if isinstance(d, dict) and "__error__" in d],
            "추가 훅 파일": [str(p) for p, _ in extra], "결과": items,
            "요약": {"자동으로 본 문항": len(items), "해당 문항": len(app), "위험 비율": ratio, "3점 빈칸": gaps3, "구간": band,
                   "먼저 고칠 3개": [t["문항"] for t in top]},
            "참고": {"CLAUDE.md 글자 수": {str(p): n for p, n in md},
                   "설명": "CLAUDE.md 는 세션마다 읽혀 길수록 매번 토큰을 씁니다(공식 문서 code.claude.com/docs/en/memory)."}}


def show(r):
    s = r["요약"]
    print("\n클로드 코드 안전 점검기 {} · 읽기만 했고 아무 데도 보내지 않았습니다\n".format(r["점검기"]))
    print("읽은 설정 파일: " + (", ".join(r["읽은 설정 파일"]) or "없음(모두 기본값)"))
    if r["추가 훅 파일"]:
        print("추가 훅 파일(켜져 있는지는 클로드 코드 /hooks 화면으로 확인): " + ", ".join(r["추가 훅 파일"]))
    print()
    for i in r["결과"]:
        mark = {"예": "  예  ", "아니오": "아니오", "모름": " 모름 ", "해당 없음": "해당없음"}[i["답"]]
        print("[{}] {} {} ({}점)\n        {}".format(mark, i["문항"], i["점검"], i["점수"], i["근거"]))
    print("\n위험 비율 {}% · 구간 「{}」 · 3점 빈칸 {}개 ({})".format(s["위험 비율"], s["구간"], len(s["3점 빈칸"]), ", ".join(s["3점 빈칸"]) or "없음"))
    print("\n먼저 고칠 3개")
    for code in s["먼저 고칠 3개"]:
        i = next(x for x in r["결과"] if x["문항"] == code)
        print("  · {} {} → {}".format(code, i["점검"], i["고치는 법"]))
    for p, n in r["참고"]["CLAUDE.md 글자 수"].items():
        print("\n참고: {} {:,}자 — {}".format(p, n, r["참고"]["설명"]))
    print("\n이 점검기는 설정 파일로 알 수 있는 {}문항만 봅니다. 사람이 답해야 하는 문항(깃 보호·배포 승인·백업 복구 같은 것)까지 보는 37문항 진단표와".format(s["자동으로 본 문항"]))
    print("실행 전 관문 설치(보호 파일 · 완료 보고 검수 · 같은 오류 3번 멈춤 · 팀 PC별 개통 시험)는 크몽 「AI가드레일」에서 합니다.\n")


def main():
    ap = argparse.ArgumentParser(description="클로드 코드 안전 점검기(읽기 전용)")
    ap.add_argument("--project", default=os.getcwd())
    ap.add_argument("--home", default=str(Path.home()), help=argparse.SUPPRESS)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    r = check(Path(a.home).expanduser(), Path(a.project).expanduser().resolve())
    print(json.dumps(r, ensure_ascii=False, indent=1)) if a.json else show(r)


if __name__ == "__main__":
    sys.exit(main())
