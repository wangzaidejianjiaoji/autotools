import os
import glob

def delete_jpg_files():
    path = input("请输入要删除.jpg文件的路径: ").strip()
    
    if not os.path.isdir(path):
        print(f"错误: 路径 '{path}' 不存在或不是有效目录")
        return
    
    jpg_files = glob.glob(os.path.join(path, "*.jpg"))
    
    if not jpg_files:
        print("该路径下没有找到任何.jpg文件")
        return
    
    print(f"\n找到 {len(jpg_files)} 个.jpg文件，开始删除...")
    
    deleted_count = 0
    for jpg_file in jpg_files:
        try:
            os.remove(jpg_file)
            deleted_count += 1
            print(f"已删除: {jpg_file}")
        except Exception as e:
            print(f"删除失败 {jpg_file}: {e}")
    
    print(f"\n操作完成! 共删除 {deleted_count} 个文件")

if __name__ == "__main__":
    delete_jpg_files()