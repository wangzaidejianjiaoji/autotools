import os

# 删除空目录
dir_path = r"D:\data\Night\multi_frame_test_set\20260408_135424"

if os.path.exists(dir_path):
    if not os.listdir(dir_path):
        os.rmdir(dir_path)
        print(f"已删除空目录：{dir_path}")
    else:
        print(f"目录不为空：{dir_path}")
else:
    print(f"目录不存在：{dir_path}")

print("清理完成")