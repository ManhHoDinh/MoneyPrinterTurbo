# Windows Agent Runner

Runner nay tach rieng khoi cac loop PowerShell cu de de kiem soat hon tren Windows.

Pipeline moi cycle:

1. `python scripts/auto_fix_recipes.py`
2. `python -m py_compile ...`
3. `python scripts/auto_agent.py --hours <auditHoursWindow>`
4. `agentCommand` trong file config (neu bat)

Tat ca state/log/control file nam o:

- `storage/windows-agent-runner/state.json`
- `storage/windows-agent-runner/lock.json`
- `storage/windows-agent-runner/runner.log`
- `storage/windows-agent-runner/pause.flag`
- `storage/windows-agent-runner/stop.flag`
- `storage/windows-agent-runner/cycles/<timestamp>/summary.json`

Lenh dung nhanh:

```powershell
# xem trang thai
powershell -File scripts\windows_agent_runner.ps1 -Action status

# chay foreground
powershell -File scripts\windows_agent_runner.ps1 -Action run

# chay 1 cycle
powershell -File scripts\windows_agent_runner.ps1 -Action run-once

# chay tach process tren Windows
powershell -File scripts\windows_agent_runner.ps1 -Action start

# tam dung / tiep tuc / dung
powershell -File scripts\windows_agent_runner.ps1 -Action pause
powershell -File scripts\windows_agent_runner.ps1 -Action resume
powershell -File scripts\windows_agent_runner.ps1 -Action stop
```

Ghi chu van hanh:

- `lock.json` ngan khong cho 2 runner cung sua repo.
- `pause.flag` duoc kiem tra giua cac cycle; runner khong cat ngang step dang chay.
- `stop.flag` duoc kiem tra truoc moi cycle; runner se thoat sach sau cycle hien tai.
- `git status --short` va `git diff --stat` duoc chup truoc/sau moi cycle de de review thay doi.
- Muon bat agent sua code that su, sua `agentCommand` va dat `steps.runAgentCommand = true` trong file config.
- Neu lock bi stale, dung `-Action unlock -Force`.
