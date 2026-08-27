<#
.\open_docs.ps1
一键构建并打开 MkDocs 生成的文档（PowerShell 版本，UTF-8 支持）
使用方法：在项目根双击或在 PowerShell 中运行此脚本。
此脚本会：
  - 切换到脚本所在目录
  - 尝试激活常见虚拟环境（.venv311 或 .venv）
  - 使用 python -m mkdocs build 构建站点
  - 打开 site\index.html（如果存在）
#>

# 确保控制台输出为 UTF-8，以便正确显示中文
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

try {
	$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
} catch {
	$ScriptDir = Get-Location
}

Set-Location -Path $ScriptDir

Write-Host "脚本目录： $ScriptDir"

# 尝试激活虚拟环境（优先 .venv311，然后 .venv）
$venvCandidates = @('.\.venv311\Scripts\Activate.ps1', '.\.venv\Scripts\Activate.ps1')
$activated = $false
foreach ($candidate in $venvCandidates) {
	if (Test-Path $candidate) {
		try {
			Write-Host "正在激活虚拟环境： $candidate"
			& $candidate
			$activated = $true
			break
		} catch {
			Write-Warning "激活虚拟环境失败： $_"
		}
	}
}

if (-not $activated) {
	Write-Host "未检测到 .venv311 或 .venv 的 Activate.ps1；将使用当前环境的 python 来构建（如需虚拟环境请先激活）。"
}

Write-Host "使用 python -m mkdocs build 构建站点（请确保已安装 mkdocs）..."
try {
	# 使用 python -m mkdocs 避免 PATH 问题
	& python -m mkdocs build 2>&1 | ForEach-Object { Write-Host $_ }
} catch {
	Write-Error "构建过程发生异常： $_"
}

$index = Join-Path $ScriptDir 'site\index.html'
if (Test-Path $index) {
	Write-Host "文档构建完成，正在打开： $index"
	Start-Process $index
} else {
	Write-Warning "未找到 site\index.html。请检查 mkdocs 是否安装或构建输出是否成功。"
}

Write-Host "按回车退出..."
Read-Host | Out-Null
