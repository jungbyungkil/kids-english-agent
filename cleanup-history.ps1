# cleanup-history.ps1
param(
  [string]$Branch = "main"
)

# 0) 사전 조건: 워킹트리 깨끗하게
git status --porcelain
if ($LASTEXITCODE -ne 0) { throw "Git이 설치되어 있지 않거나 저장소가 아닙니다." }
if ((git status --porcelain) -ne "") { throw "커밋되지 않은 변경이 있습니다. 먼저 commit 하세요." }

# 1) git-filter-repo 설치 (없다면)
pip show git-filter-repo 1>$null 2>$null
if ($LASTEXITCODE -ne 0) {
  python -m pip install --upgrade git-filter-repo
}

# 2) 최신 원격 반영
git fetch --all --tags

# 3) 히스토리 정리 (완전 삭제 대상 목록)
#   필요시 항목 추가/삭제 가능
$paths = @(
  "local.settings.json",
  ".env",
  ".venv/",
  "env/",
  "__pycache__/",
  "node_modules/",
  "dist/",
  "build/",
  ".DS_Store",
  "Thumbs.db"
)

# git-filter-repo 실행
$pathArgs = @()
foreach ($p in $paths) { $pathArgs += @("--path", $p) }
python -m git_filter_repo @pathArgs --invert-paths --force

# 4) .gitignore 추가/갱신
@"
# Python
.venv/
env/
__pycache__/
*.pyc

# Azure Functions local
local.settings.json

# Node
node_modules/
dist/
build/

# OS/IDE
.DS_Store
Thumbs.db
.vscode/
"@ | Out-File -Encoding utf8 -FilePath .gitignore

git add .gitignore
git commit -m "chore: add/update .gitignore" 2>$null

# 5) 강제 푸시 (브랜치 + 태그)
git branch -M $Branch
git push origin --force --all
git push origin --force --tags

Write-Host "✅ 완료! 백업은 .git/filter-repo/ 아래에 저장됩니다. 문제가 있으면 롤백 가능."
