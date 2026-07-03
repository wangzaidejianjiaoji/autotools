param(
    [string]$filePath,
    [string]$extractTo
)

Write-Host "正在解压文件：$filePath"
Write-Host "解压到：$extractTo"

# 确保输出目录存在
if (-not (Test-Path -Path $extractTo)) {
    New-Item -ItemType Directory -Path $extractTo -Force | Out-Null
    Write-Host "创建输出目录：$extractTo"
}

# 尝试使用7z.exe
$sevenZipPaths = @(
    "7z",
    "7z.exe",
    "C:\Program Files\7-Zip\7z.exe",
    "C:\Program Files (x86)\7-Zip\7z.exe",
    "D:\Program Files\7-Zip\7z.exe",
    "D:\Program Files (x86)\7-Zip\7z.exe",
    "C:\Users\51698\AppData\Roaming\Tencent\xwechat\XPlugin\Plugins\CourgettePatch\20\extracted\7z.exe"
)

$success = $false

foreach ($sevenZipPath in $sevenZipPaths) {
    Write-Host "  尝试7z路径：$sevenZipPath"
    
    try {
        # 检查7z是否存在
        if ($sevenZipPath -ne "7z" -and $sevenZipPath -ne "7z.exe") {
            if (-not (Test-Path -Path $sevenZipPath)) {
                Write-Host "  失败：找不到文件 $sevenZipPath"
                continue
            }
        }
        
        # 执行7z命令
        & $sevenZipPath x "$filePath" -o"$extractTo" -aoa
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✓ 解压成功：$filePath"
            $success = $true
            break
        } else {
            Write-Host "  失败：7z返回错误码 $LASTEXITCODE"
        }
    } catch {
        Write-Host "  失败：$($_.Exception.Message)"
    }
}

# 如果7z失败，尝试使用PowerShell的Expand-Archive
if (-not $success) {
    Write-Host "  尝试PowerShell Expand-Archive"
    try {
        Expand-Archive -Path "$filePath" -DestinationPath "$extractTo" -Force
        Write-Host "✓ 解压成功：$filePath"
        $success = $true
    } catch {
        Write-Host "  失败：$($_.Exception.Message)"
    }
}

if (-not $success) {
    Write-Host "✗ 解压失败：所有方法都尝试失败"
    exit 1
} else {
    Write-Host "✓ 解压完成"
    exit 0
}