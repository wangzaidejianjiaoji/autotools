# This script is used to scan a folder, find all images in that folder, and generate labelme-type json by applying a DNN on those images
# These labels are served as pre-labels, and must be double-checked by a human labeling expert.
# We make the assumption that each frame contains at most one drone.
# Sample usage:
# python data_prelabel -i [path-to-folder]
# Optional arguments:
# -r : go into the folder recursively.

import argparse
from collections import defaultdict
import json
import os
import cv2
import sys
import os.path as osp

sys.path.insert(0, os.getcwd())
sys.path.insert(0, osp.dirname(os.getcwd()))
from bvDetectFramework import BVModel
from utils_bvtrain import get_dist_zoom_ftime_from_fname, list_images, replace_ext, bcolors


class LabelBot:
    def __init__(self, folder, out, recursive, weights, names, resize, conf_thresh_dict, max_dets, skip_existing, device):
        self.folder = folder
        self.droneDNN = BVModel(
            model_type="YOLOV5",
            weights=weights,
            obj_names=names,
            nms_conf_threshold=0.1,
            resize=resize,
            cuda_device=device,
            use_tensorrt=weights.endswith("engine")
        )
        self.recursive = recursive
        if out:
            self.out_dir = out
            os.makedirs(self.out_dir, exist_ok=True)
        else:
            self.out_dir = ""
        self.conf_thresh_dict = conf_thresh_dict
        self.max_dets = max_dets
        self.skip_existing = skip_existing

    def label(self):
        img_list = list_images(self.folder, self.recursive)

        for idx, imgPath in enumerate(img_list):
            print(f"[{idx+1} / {len(img_list)}] {osp.basename(imgPath)}")
            if self.out_dir:
                out_file = osp.join(self.out_dir, replace_ext(osp.basename(imgPath), ".json"))
            else:
                name, _ = osp.splitext(imgPath)
                out_file = name + ".json"
            if self.skip_existing and osp.exists(out_file):
                print(f"{bcolors.WARNING}json already exists! Skipping label generation{bcolors.ENDC}\n")
                continue

            img = cv2.imread(imgPath)
            detections = self.droneDNN.detect_single_image(img)
            print(detections)
            if img is None:
                print("读取失败，跳过：", imgPath)
                continue
            height, width, _ = img.shape
            
            self.save(detections, imgPath, width, height, out_file)

    def save(self, detections, imgPath, width, height, out_file):
        detections = [det for det in detections if det[1] > self.conf_thresh_dict[det[0]]]
        detections.sort(key=lambda det: det[1], reverse=True)
        label_dict = {
            "version": "4.5.7",
            "flags": {},
            "shapes": [],
            "imagePath": osp.basename(imgPath),
            "imageData": None,
            "imageHeight": height,
            "imageWidth": width,
        }
        if detections:
            for dt in detections[: self.max_dets]:
                label = dt[0]
                dist, zoom, _ = get_dist_zoom_ftime_from_fname(fname=imgPath)
                print(f"LABEL: {label}, SCORE: {dt[1]:.4f}")
                shape = {
                    "label": label,
                    "line_color": None,
                    "fill_color": None,
                    "points": [[dt[2][0], dt[2][1]], [dt[2][2], dt[2][3]]],
                    "shape_type": "rectangle",
                    "flags": {},
                }
                label_dict["shapes"].append(shape)

            with open(out_file, "w") as outfile:
                json.dump(label_dict, outfile)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input", type=str, help="The input source, folder or image.")
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default="",
        help="output folder to save json files. Default is to save in original input folder.",
    )
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        default=False,
        help="recursively find images or videos in a folder",
    )
    parser.add_argument(
        "-n", "--names", type=str, required=True, help="path to .json file containing class to id mapping"
    )
    parser.add_argument(
        "-w", "--weights", type=str, default="./yolov5/weights/mixed/best.pt", help="path to the YOLOV5 model weights"
    )
    parser.add_argument("--resize", nargs=2, type=int, default=None, help="resize images during detection")
    parser.add_argument(
        "--conf",
        type=str,
        default="",
        help="minimum confidence score per class (if not specified, class will be skipped). Only keep label if confidence is larger than this threshold. e.g. --conf mavic,0.2,p4,0.1",
    )
    parser.add_argument("--max", type=int, default=1, help="max number of detections to save per img")
    parser.add_argument(
        "--skip_existing", default=False, action="store_true", help="if json file already exists, do not overwrite it"
    )
    parser.add_argument("--cuda_device", type=str, default="0", help="cuda device to use")
    args = parser.parse_args()

    resize = ()
    if args.resize is not None:
        resize = tuple(args.resize)

    conf_thresh_dict = defaultdict(lambda: 1.0)
    if args.conf:
        class_confs = args.conf.split(",")
        print(f"###### Confidence thresholds for classes: ######\n")
        print(class_confs)
        for i in range(0, len(class_confs), 2):
            conf_thresh_dict[class_confs[i]] = float(class_confs[i + 1])
    labelBot = LabelBot(
        folder=args.input,
        out=args.output,
        recursive=args.recursive,
        weights=args.weights,
        names=args.names,
        resize=resize,
        conf_thresh_dict=conf_thresh_dict,
        max_dets=args.max,
        skip_existing=args.skip_existing,
        device=args.cuda_device
    )
    labelBot.label()
