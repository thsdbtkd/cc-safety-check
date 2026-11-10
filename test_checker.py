"""점검기 자가 시험: 설정 4가지에서 기대한 답이 나오는지 확인."""
import json, os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
FIX = {  # 시험용 설정 4가지 (임시 폴더에 만들고, 실제 설정은 건드리지 않음)
    "empty/h/.claude": None, "empty/p": None,
    "locked/h/.claude/settings.json": '{"permissions":{"disableBypassPermissionsMode":"disable","defaultMode":"default","deny":["Read(./.env)","Read(~/.ssh/**)","Bash(rm -rf *)","Bash(git push --force *)"]},"sandbox":{"enabled":true},"hooks":{"PreToolUse":[{"hooks":[{"type":"command","command":"x"}]}],"Stop":[{"hooks":[]}],"PostToolUse":[{"hooks":[]}]}}',
    "locked/p": None,
    "wide/h/.claude/settings.json": '{"permissions":{"defaultMode":"bypassPermissions"}}',
    "wide/p/.claude/settings.json": '{"permissions":{"allow":["Bash(*)"]}}',
    "wide/p/.mcp.json": '{"mcpServers":{"github":{}}}',
    "broken/h/.claude/settings.json": '{"permissions": {',
    "broken/p": None,
}
T = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="ccsc_test_")
for rel, body in FIX.items():
    path = os.path.join(T, rel)
    if body is None:
        os.makedirs(path, exist_ok=True)
    else:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if not os.path.exists(path):
            with open(path, "w") as f: f.write(body)
def run(c):
    out = subprocess.run([sys.executable, os.path.join(HERE, "cc_safety_check.py"), "--home", f"{T}/{c}/h", "--project", f"{T}/{c}/p", "--json"], capture_output=True, text=True, check=True).stdout
    r = json.loads(out); return {i["문항"]: i["답"] for i in r["결과"]}, r
ok = 0; tot = 0
def exp(name, got, want):
    global ok, tot
    for k, v in want.items():
        tot += 1; good = got.get(k) == v; ok += good
        print(("통과" if good else "실패"), name, k, "기대", v, "실제", got.get(k))
a, _ = run("empty"); exp("빈 설정", a, {"A5":"아니오","B1":"예","A3":"아니오","A4":"아니오","C1":"아니오","D1":"아니오","E2":"아니오","A9":"해당 없음"})
a, _ = run("locked"); exp("잠근 설정", a, {"A5":"예","B1":"예","A3":"예","A4":"예","C1":"예","D1":"모름","E2":"모름"})
a, _ = run("wide"); exp("넓게 연 설정", a, {"A5":"아니오","B1":"아니오","A4":"아니오","A9":"모름"})
a, r = run("broken"); tot += 1; good = len(r["깨진 설정 파일"]) == 1; ok += good; print(("통과" if good else "실패"), "깨진 설정 파일 감지", r["깨진 설정 파일"])
print(f"자가 시험 {ok}/{tot}")
sys.exit(0 if ok == tot else 1)
