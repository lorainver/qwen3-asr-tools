# Git rebase message modifier for PowerShell
# Usage: .\fix-commits.ps1

# 设置 GIT_SEQUENCE_EDITOR 为 PowerShell 脚本
$GIT_SEQUENCE_EDITOR = @"
`$script = @'
const fs = require('fs');
const txt = fs.readFileSync(process.argv[2], 'utf8');
const lines = txt.split('\n');
for(let i = 0; i < lines.length; i++) {
    if(lines[i].startsWith('pick ')) {
        lines[i] = 'reword ' + lines[i].substring(5);
    }
}
fs.writeFileSync(process.argv[2], lines.join('\n'));
'@;
const { spawn } = require('child_process');
const node = spawn('node', ['-e', script]);
node.stdout.pipe(process.stdout);
node.stderr.pipe(process.stderr);
"@

# 临时文件路径
$tempFile = "$env:TEMP\git_rebase_editor.ps1"

# 写入临时脚本
Set-Content -Path $tempFile -Value $GIT_SEQUENCE_EDITOR -Encoding UTF8

# 设置环境变量
[Environment]::SetEnvironmentVariable("GIT_SEQUENCE_EDITOR", "powershell -File `"$tempFile`"", "Process")

Write-Host "GIT_SEQUENCE_EDITOR set to: powershell -File $tempFile"
Write-Host "Ready to run git rebase -i HEAD~N"
