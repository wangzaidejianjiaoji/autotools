import os
import subprocess

def extract_7z_file(file_path, extract_to=None):
    """解压 7z 文件"""
    try:
        if extract_to is None:
            extract_to = os.path.splitext(file_path)[0]
        if os.path.exists(extract_to):
            print(f"文件夹已存在，跳过：{extract_to}")
            return extract_to
        os.makedirs(extract_to, exist_ok=True)
        
        # 检查文件是否存在
        if not os.path.exists(file_path):
            print(f"✗ 解压失败：文件不存在 {file_path}")
            return None
        
        # 构建PowerShell脚本路径
        powershell_script = os.path.join(os.path.dirname(__file__), 'extract_7z.ps1')
        
        print(f"正在使用subprocess调用PowerShell脚本解压：{os.path.basename(file_path)}")
        
        try:
            # 构建命令
            cmd = [
                'powershell',
                '-ExecutionPolicy', 'Bypass',
                '-File', powershell_script,
                '-filePath', file_path,
                '-extractTo', extract_to
            ]
            
            # 执行命令
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=False,  # 不使用文本模式，使用字节模式
                check=False,
                timeout=120  # 设置120秒超时
            )
            
            # 输出PowerShell脚本的输出，处理编码
            if result.stdout:
                try:
                    print(result.stdout.decode('utf-8').strip())
                except UnicodeDecodeError:
                    print(result.stdout.decode('gbk', errors='ignore').strip())
            
            if result.stderr:
                try:
                    print(f"  错误：{result.stderr.decode('utf-8').strip()}")
                except UnicodeDecodeError:
                    print(f"  错误：{result.stderr.decode('gbk', errors='ignore').strip()}")
            
            if result.returncode == 0:
                print(f"✓ 解压成功：{os.path.basename(file_path)} -> {os.path.basename(extract_to)}")
                return extract_to
            else:
                print(f"✗ 解压失败：PowerShell脚本返回错误码 {result.returncode}")
                return None
                
        except FileNotFoundError:
            print(f"✗ 失败：找不到PowerShell")
            return None
        except Exception as e:
            print(f"✗ 失败：{e}")
            return None

    except Exception as e:
        print(f"✗ 解压失败 {file_path}: {e}")
        return None

def main():
    print("=" * 60)
    # 硬编码目录路径以便测试
    target_dir = r"D:\data\Night\multi_frame_test_set"
    output_dir = r"D:\data\Night\multi_frame_test_set"

    if not os.path.exists(target_dir):
        print(f"错误：目录 '{target_dir}' 不存在")
        return

    print(f"  输入目录：{target_dir}")
    print(f"  输出目录：{output_dir}")

    max_frames = 5

    print(f"  使用最大帧数：{max_frames}（必须正好此数量）")
    print(f"  时间判定：前 17 位字符必须完全一致")

    print("\n" + "=" * 60)
    print("步骤 1: 查找 7z 文件")
    print("=" * 60)
    seven_z_files = [f for f in os.listdir(target_dir) if f.lower().endswith('.7z')]
    print(f"  找到 {len(seven_z_files)} 个 7z 文件")

    if not seven_z_files:
        print("  没有找到 7z 文件")
        return

    print("\n" + "=" * 60)
    print("步骤 2: 解压 7z 文件")
    print("=" * 60)
    extracted_dirs = []
    for seven_z_file in seven_z_files:
        file_path = os.path.join(target_dir, seven_z_file)
        extracted_path = extract_7z_file(file_path)
        if extracted_path:
            extracted_dirs.append(extracted_path)

    print(f"  共解压 {len(extracted_dirs)} 个文件")

if __name__ == "__main__":
    main()