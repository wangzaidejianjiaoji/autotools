"""
作用：将单个 labelme json 转为 fiftyone 检测格式（坐标归一化为 [cx, cy, w, h] / 图像尺寸），
      并把整个目录下所有 json 合并写到一个 fiftyone.json 中，
      每个图片名映射到 { "ground_truth": { "detections": [...] } }。
用法：python labelme.json_to_fiftyone.json_format.py
      运行后按提示输入输入目录和输出 json 路径。
关键参数：
  - input_dir (交互输入)：存放 labelme json 的目录（仅顶层 *.json）
  - output_path (交互输入)：生成的 fiftyone.json 路径，默认 <input_dir>/fiftyone.json
  - bounding_box：取 shape['points'] 得到 x1,y1,x2,y2，转为
    [ (x_min+w/2)/imageWidth, (y_min+h/2)/imageHeight, w/imageWidth, h/imageHeight ]
  - 默认输入目录：脚本所在目录下的 labelme_input 子目录
"""

def convert_labelme_to_fiftyone(labelme_json_path):
    with open(labelme_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    image_path = data.get('imagePath', '')
    image_filename = os.path.basename(image_path)
    image_width = data.get('imageWidth', 1)
    image_height = data.get('imageHeight', 1)
    
    detections = []
    for shape in data.get('shapes', []):
        if shape.get('shape_type') == 'rectangle':
            points = shape['points']
            x1, y1 = points[0]
            x2, y2 = points[1]
            
            x_min = min(x1, x2)
            y_min = min(y1, y2)
            x_max = max(x1, x2)
            y_max = max(y1, y2)
            
            width = x_max - x_min
            height = y_max - y_min
            
            center_x = (x_min + width / 2) / image_width
            center_y = (y_min + height / 2) / image_height
            norm_width = width / image_width
            norm_height = height / image_height
            
            detections.append({
                "label": shape['label'],
                "bounding_box": [center_x, center_y, norm_width, norm_height]
            })
    
    return {
        image_filename: {
            "ground_truth": {
                "detections": detections
            }
        }
    }

def main():
    default_input_dir = os.path.join(os.path.dirname(__file__), 'labelme_input')
    default_output_dir = os.path.join(os.path.dirname(__file__), 'output')
    
    input_dir = input(f"请输入labelme.json文件所在文件夹路径: ").strip()
    if not input_dir:
        input_dir = default_input_dir
    
    output_path = input(f"请输入生成的fiftyone.json文件路径 (直接回车默认: {input_dir}\\fiftyone.json): ").strip()
    if not output_path:
        output_path = os.path.join(input_dir, 'fiftyone.json')
    elif not output_path.lower().endswith('.json'):
        output_path = output_path + '.json'
    
    if not os.path.exists(input_dir):
        print(f"错误: 输入文件夹不存在 - {input_dir}")
        return
    
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    
    json_files = glob.glob(os.path.join(input_dir, '*.json'))
    
    if not json_files:
        print(f"警告: 在 {input_dir} 中未找到任何json文件")
        return
    
    result = {}
    for json_file in json_files:
        try:
            converted = convert_labelme_to_fiftyone(json_file)
            result.update(converted)
            print(f"已转换: {os.path.basename(json_file)}")
        except Exception as e:
            print(f"转换失败 {os.path.basename(json_file)}: {str(e)}")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"\n转换完成! 输出文件: {output_path}")
    print(f"共转换 {len(result)} 个图片标注")

if __name__ == '__main__':
    main()