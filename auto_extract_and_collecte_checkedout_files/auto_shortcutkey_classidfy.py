import cv2
import json
import os
import shutil
import numpy as np
import datetime

def load_labelme_json(json_path):
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data

def resize_image_to_fit_screen(img, max_width=1600, max_height=900):
    height, width = img.shape[:2]
    #  # 确保最小分辨率为1080p
    # min_width = 1920
    # min_height = 1080
    # 确保最小分辨率为720p
    min_width = 1280
    min_height = 720
    
    # 如果图片尺寸小于最小分辨率，进行放大
    if width < min_width or height < min_height:
        scale = max(min_width / width, min_height / height)
        new_width = int(width * scale)
        new_height = int(height * scale)
        img = cv2.resize(img, (new_width, new_height))
    # 如果图片尺寸大于最大分辨率，进行缩小
    elif width > max_width or height > max_height:
        scale = min(max_width / width, max_height / height)
        new_width = int(width * scale)
        new_height = int(height * scale)
        img = cv2.resize(img, (new_width, new_height))
    
    return img

def draw_labelme_annotations(img, labelme_data):
    for shape in labelme_data.get('shapes', []):
        points = shape.get('points', [])
        label = shape.get('label', '')
        if len(points) >= 2:
            points = [(int(p[0]), int(p[1])) for p in points]
            if shape.get('shape_type') == 'rectangle':
                cv2.rectangle(img, points[0], points[1], (0, 255, 0), 2)
                cv2.putText(img, label, (points[0][0], points[0][1] - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            elif shape.get('shape_type') == 'polygon':
                points_array = np.array(points, np.int32)
                cv2.polylines(img, [points_array], True, (0, 255, 0), 2)
                cv2.putText(img, label, (points[0][0], points[0][1] - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
    return img

def create_directory(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)

def copy_files_to_category(img_path, json_path, category):
    base_dir = os.path.dirname(img_path)
    base_dir_name = os.path.basename(base_dir)
    class_dir = os.path.join(os.path.dirname(base_dir), f'{base_dir_name}_classidfy')
    
    category_map = {
        '1': 'drone',
        '2': 'similar_Fixed_Object_False_Alarm',
        '3': 'ufo',
        '4': 'bird',
        '5': 'plane',
        '6': 'uao'
    }
    
    if category not in category_map:
        print(f"Invalid category: {category}")
        return
    
    dest_dir = os.path.join(class_dir, category_map[category])
    create_directory(dest_dir)
    
    img_name = os.path.basename(img_path)
    dest_img_path = os.path.join(dest_dir, img_name)
    shutil.copy2(img_path, dest_img_path)
    
    # 只有当json_path存在时才复制json文件
    if json_path:
        json_name = os.path.basename(json_path)
        dest_json_path = os.path.join(dest_dir, json_name)
        shutil.copy2(json_path, dest_json_path)
        print(f"Files copied to: {dest_dir}")
    else:
        print(f"Image copied to: {dest_dir} (no JSON file)")

def get_image_json_pairs(directory):
    pairs = []
    img_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']
    
    for file in os.listdir(directory):
        if any(file.lower().endswith(ext) for ext in img_extensions):
            img_path = os.path.join(directory, file)
            json_path = os.path.join(directory, os.path.splitext(file)[0] + '.json')
            # 无论是否存在json文件，都添加到列表中
            pairs.append((img_path, json_path if os.path.exists(json_path) else None))
    
    return pairs

def main():
    show_annotations = True  # 默认显示标注框
    window_name = 'Image Classification'  # 窗口名称
    
    input_path = input("Enter image directory path (or 'q' to quit): ")
    if input_path.lower() == 'q':
        return
    
    if not os.path.exists(input_path):
        print(f"Error: Directory not found: {input_path}")
        return
    
    if not os.path.isdir(input_path):
        print(f"Error: {input_path} is not a directory")
        return
    
    image_json_pairs = get_image_json_pairs(input_path)
    if not image_json_pairs:
        print(f"Error: No image-json pairs found in {input_path}")
        return
    
    # 按照图片名称排序
    image_json_pairs.sort(key=lambda x: os.path.basename(x[0]))
    
    # 输入开始图片名
    start_image_name = input("Enter start image name (press Enter to use first image): ")
    
    # 确定开始索引
    start_index = 0
    if start_image_name:
        for i, (img_path, _) in enumerate(image_json_pairs):
            if os.path.basename(img_path) == start_image_name:
                start_index = i
                break
        else:
            print(f"Warning: Image {start_image_name} not found, using first image")
    
    # 生成固定的日志文件路径
    log_file = os.path.join(input_path, "classification.log")
    
    # 记录开始日志
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write("\n" + "=" * 70 + "\n")
        f.write(f"Classification started at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Start image: {os.path.basename(image_json_pairs[start_index][0])} (position: {start_index + 1}/{len(image_json_pairs)})\n")
        f.write(f"Total images: {len(image_json_pairs)}\n")
        f.write("=" * 70 + "\n")
    
    print(f"Found {len(image_json_pairs)} image-json pairs")
    print("Press 'h' to toggle annotations display")
    print("Press 'a' to go back to previous image")
    print("Press 'd' to go to next image")
    print("Press '1' for drone, '2' for similar_Fixed_Object_False_Alarm, '3' for ufo, '4' for bird, '5' for plane, '6' for uao")
    
    # 处理图片对，从开始索引开始
    i = 0
    while i < len(image_json_pairs[start_index:]):
        img_path, json_path = image_json_pairs[start_index + i]
        current_position = start_index + i + 1
        print(f"Processing: {os.path.basename(img_path)} (position: {current_position}/{len(image_json_pairs)})")
        
        img = cv2.imread(img_path)
        if img is None:
            print(f"Error: Failed to read image: {img_path}")
            # 记录错误日志
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"Error: Failed to read image: {os.path.basename(img_path)} (position: {current_position}/{len(image_json_pairs)})\n")
            i += 1
            continue
        
        try:
            labelme_data = None
            if json_path:
                labelme_data = load_labelme_json(json_path)
            
            while True:
                # 根据show_annotations状态显示或不显示标注框
                if show_annotations and labelme_data:
                    display_img = draw_labelme_annotations(img.copy(), labelme_data)
                else:
                    display_img = img.copy()
                
                display_img = resize_image_to_fit_screen(display_img)
                
                # 显示图片（如果窗口不存在会自动创建）
                cv2.imshow(window_name, display_img)
                
                key = cv2.waitKey(0)
                
                if key == 27:  # ESC key
                    print("Exiting program...")
                    # 记录退出日志
                    with open(log_file, 'a', encoding='utf-8') as f:
                        f.write(f"\nExited at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                        f.write(f"Last processed image: {os.path.basename(img_path)} (position: {current_position}/{len(image_json_pairs)})\n")
                        f.write("=" * 70 + "\n")
                    cv2.destroyAllWindows()
                    return
                elif key == ord('h'):  # 'h' key to toggle annotations
                    show_annotations = not show_annotations
                    print(f"Annotations {'enabled' if show_annotations else 'disabled'}")
                    continue
                elif key == ord('a'):  # 'a' key to go back
                    if i > 0:
                        i -= 1
                        print("Going back to previous image")
                    else:
                        print("Already at the first image")
                    break
                elif key == ord('d'):  # 'd' key to go forward
                    if i < len(image_json_pairs[start_index:]) - 1:
                        i += 1
                        print("Going to next image")
                    else:
                        print("Already at the last image")
                    break
                else:
                    category = chr(key)
                    if category in ['1', '2', '3', '4', '5', '6']:
                        copy_files_to_category(img_path, json_path, category)
                        # 记录分类日志
                        with open(log_file, 'a', encoding='utf-8') as f:
                            f.write(f"{os.path.basename(img_path)} (position: {current_position}/{len(image_json_pairs)}) -> Category {category}\n")
                        i += 1
                    else:
                        print(f"Invalid key pressed: {category}. Please press 1, 2, 3, 4, 5, or 6.")
                        # 记录无效输入日志
                        with open(log_file, 'a', encoding='utf-8') as f:
                            f.write(f"{os.path.basename(img_path)} (position: {current_position}/{len(image_json_pairs)}) -> Invalid input: {category}\n")
                    break
        except Exception as e:
            print(f"Error processing {img_path}: {e}")
            # 记录异常日志
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"Error processing {os.path.basename(img_path)} (position: {current_position}/{len(image_json_pairs)}): {str(e)}\n")
            i += 1
            continue
    
    # 所有图片处理完成后记录完成日志
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"\nClassification completed at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 70 + "\n")
    
    # 所有图片处理完成后关闭窗口
    cv2.destroyAllWindows()
    print("Classification completed successfully!")

if __name__ == "__main__":
    main()