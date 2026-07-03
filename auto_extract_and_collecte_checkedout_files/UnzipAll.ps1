# 定义源文件夹路径和目标文件夹路径
$sourceFolder = "D:\Model_testing_project\test_set_video\train\train"
$destinationFolder = "D:\Model_testing_project\test_set_video\train\train"

# 获取源文件夹中的所有 .zip 文件
$zipFiles = Get-ChildItem -Path $sourceFolder -Filter *.zip

# 遍历每个 .zip 文件并解压
foreach ($zipFile in $zipFiles) {
    # 创建与 zip 文件同名的目标文件夹
    $extractPath = Join-Path -Path $destinationFolder -ChildPath ([System.IO.Path]::GetFileNameWithoutExtension($zipFile.Name))
    
    # 检查目标文件夹是否存在，如果不存在则创建
    if (-Not (Test-Path -Path $extractPath)) {
        New-Item -ItemType Directory -Path $extractPath | Out-Null
    }
    
    # 解压文件
    Expand-Archive -Path $zipFile.FullName -DestinationPath $extractPath
}

Write-Output "所有文件已成功解压。"