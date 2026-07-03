import os
import py7zr
import rarfile
import zipfile
from typing import List, Optional


class ArchiveExtractor:
    """压缩文件解压器"""

    def __init__(self):
        self.supported_formats = {
            '.7z': self._extract_7z,
            '.rar': self._extract_rar,
            '.zip': self._extract_zip,
        }

    def extract_archive(self, file_path: str, extract_to: Optional[str] = None) -> bool:
        """
        解压压缩文件
        :param file_path: 压缩文件路径
        :param extract_to: 解压目标路径（None则使用默认名称）
        :return: 是否成功解压
        """
        try:
            # 获取文件扩展名
            ext = os.path.splitext(file_path)[1].lower()

            # 检查是否支持该格式
            if ext not in self.supported_formats:
                print(f"⚠️ 不支持的压缩格式: {ext}")
                return False

            # 如果没有指定解压路径，使用压缩文件名作为文件夹名
            if extract_to is None:
                extract_to = self._get_default_extract_path(file_path)

            # 如果目标文件夹已存在，直接跳过
            if os.path.exists(extract_to):
                print(f"📁 跳过解压，文件夹已存在: {os.path.basename(extract_to)}")
                return False

            # 创建解压目录
            os.makedirs(extract_to, exist_ok=True)

            # 调用对应的解压方法
            self.supported_formats[ext](file_path, extract_to)

            print(f"✅ 解压成功: {os.path.basename(file_path)} -> {os.path.basename(extract_to)}")
            return True

        except Exception as e:
            print(f" 解压失败 {os.path.basename(file_path)}: {e}")
            return False

    def _get_default_extract_path(self, file_path: str) -> str:
        """生成默认解压目录路径（同名文件夹）"""
        return os.path.splitext(file_path)[0]

    def _extract_7z(self, file_path: str, extract_to: str):
        """解压7z文件"""
        with py7zr.SevenZipFile(file_path, mode='r') as archive:
            archive.extractall(path=extract_to)

    def _extract_rar(self, file_path: str, extract_to: str):
        """解压rar文件"""
        with rarfile.RarFile(file_path, 'r') as archive:
            archive.extractall(path=extract_to)

    def _extract_zip(self, file_path: str, extract_to: str):
        """解压zip文件"""
        with zipfile.ZipFile(file_path, 'r') as archive:
            archive.extractall(path=extract_to)


def find_and_extract_archives(root_dir: str, formats: tuple = ('.7z', '.rar', '.zip')) -> List[str]:
    """
    在目录中查找并解压所有支持的压缩文件
    :param root_dir: 搜索目录路径
    :param formats: 要查找的文件格式
    :return: 已解压的目录列表
    """
    extractor = ArchiveExtractor()
    extracted_dirs = []

    print(f"🔍 正在扫描目录: {root_dir}")

    for root, dirs, files in os.walk(root_dir):
        for file in files:
            file_ext = os.path.splitext(file)[1].lower()

            # 检查是否是支持的压缩格式
            if file_ext in formats:
                file_path = os.path.join(root, file)
                print(f"📦 找到压缩文件: {os.path.relpath(file_path, root_dir)}")

                # 解压文件（使用默认路径）
                if extractor.extract_archive(file_path):
                    extracted_dirs.append(os.path.splitext(file_path)[0])

    return extracted_dirs


def print_banner():
    """打印程序横幅"""
    banner = """
    ╔══════════════════════════════════════════════════════╗
    ║          自动解压工具 v2.0                             ║
    ║          支持格式: .7z .rar .zip                      ║
    ╚══════════════════════════════════════════════════════╝
    """
    print(banner)


def main():
    """主函数"""
    print_banner()

    # 获取用户输入的目录路径
    target_dir = input("请输入目录路径: ").strip().strip('"').strip("'")

    # 检查目录是否存在
    if not os.path.exists(target_dir):
        print(f" 错误: 目录 '{target_dir}' 不存在")
        return

    if not os.path.isdir(target_dir):
        print(f" 错误: '{target_dir}' 不是一个目录")
        return

    print(f"📁 开始处理目录: {target_dir}")
    print("=" * 60)

    # 查找并解压所有压缩文件
    extracted_dirs = find_and_extract_archives(target_dir)

    # 输出统计信息
    print("\n" + "=" * 60)
    if extracted_dirs:
        print(f"✅ 解压完成！成功解压 {len(extracted_dirs)} 个压缩文件")
    else:
        print("ℹ️  未找到或无需解压压缩文件")

    print("\n按Enter键退出...")
    input()


if __name__ == "__main__":
    # 检查必要的库是否安装
    try:
        import py7zr
        import rarfile
    except ImportError as e:
        print(" 缺少必要的库，请安装：")
        print(f"错误详情: {e}")
        input("\n按Enter键退出...")
        exit(1)

    main()