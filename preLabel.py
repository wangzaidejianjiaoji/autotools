import warnings
warnings.filterwarnings("ignore")
import argparse
import cv2
import os
from lib.test.utils import TrackerParams
from lib.config.ostrack.config import cfg, update_config_from_file

from lib.test.tracker.ostrack_x3 import OSTrack
from pathlib import Path
from datetime import datetime
from utils.heatmap_vis import visualize_score_map
import numpy as np
from utils.csv_util import FrameLogger
from lib.test.utils.DataLogger import BBoxDataLogger


def draw_bbox(image,bbox,color=(0,255,255),space=0):
    x,y,w,h = [int(i) for i in bbox]
    cv2.rectangle(image,(x-space,y-space),(x+w+space,y+h+space),color,2)
    return image

def get_parameters(tracker_param="vitb_384_mae_ce_32x4_ep300",checkpoint=None):
    params = TrackerParams()
    prj_dir = Path(__file__).resolve().parent
    yaml_file = os.path.join(prj_dir, 'experiments','ostrack',f'{tracker_param}.yaml')
    update_config_from_file(yaml_file)
    params.cfg = cfg
    #print("test config: ", cfg)

    # template and search region
    params.template_factor = cfg.TEST.TEMPLATE_FACTOR
    params.template_size = cfg.TEST.TEMPLATE_SIZE
    params.search_factor = cfg.TEST.SEARCH_FACTOR
    params.search_size = cfg.TEST.SEARCH_SIZE
    params.debug = False
    params.checkpoint = checkpoint
    # whether to save boxes from all queries
    params.save_all_boxes = False

    return params


def create_tracker(checkpoint,tracker_param="vitb_384_mae_ce_32x4_ep300",enabled_CE=True):

    params = get_parameters(tracker_param=tracker_param,checkpoint=checkpoint)

    if not enabled_CE:
        params.cfg["MODEL"]["BACKBONE"]["CE_LOC"] = None
        params.cfg["MODEL"]["BACKBONE"]["CE_KEEP_RATIO"] = [1.0,1.0,1.0]

    tracker = OSTrack(params, None)
    return tracker


def run_video(videofilepath,tracker,optional_box=None,save_results=False,save_video=False):

    cap = cv2.VideoCapture(videofilepath)
    display_name = 'Display: ' + "autoLabel"
    cv2.namedWindow(display_name, cv2.WND_PROP_FULLSCREEN)

    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    output_boxes = {}
    detail = {}

    now_str = datetime.now().strftime("%Y-%m-%d_%H_%M_%S")
    if save_video:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        vid_name = videofilepath.rsplit(".", 1)[0] + f"_{now_str}.mp4"
        writer = cv2.VideoWriter(vid_name, fourcc, fps, (width, height))


    def _build_init_info(box):
        return {'init_bbox': box}


    reSelect = False
    bbox = []
    conf = 0
    logger = FrameLogger(drop_keys=["search_img","origin_score_map","weight_score_map"])
    debug = False

    if save_results:
        txt_name = videofilepath.rsplit(".", 1)[0] + f"_{now_str}.txt"
        bbox_logger = BBoxDataLogger(filepath=txt_name)

    # cap.set(cv2.CAP_PROP_POS_FRAMES, 12000)
    while True:
        idx = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
        ret, frame = cap.read()

        if frame is None:
            break

        weight_img = None
        origin_score_map = None
        weight_score_map = None
        #1155
        frame_disp = frame.copy()

        #cv2.putText(frame_disp, f"R reSelect", (20, height - 90), cv2.FONT_HERSHEY_COMPLEX_SMALL, 1, (255, 0, 255), 1)
        #cv2.putText(frame_disp, f"Space Pause, Esc quit", (20, height - 60), cv2.FONT_HERSHEY_COMPLEX_SMALL, 1,3 (255, 0, 255), 1)
        cv2.putText(frame_disp, f"{idx}/{total}", (width-230, 80), cv2.FONT_HERSHEY_COMPLEX, 1, (255, 0, 255), 1)
        img_name = str(idx).zfill(6) + ".jpg"
        json_name = str(idx).zfill(6) + ".json"
        color = (0, 255, 0)

        if idx in [0] or reSelect  or optional_box:
            if optional_box is not None:
                init_state = optional_box
                optional_box = None
            else:
                reSelect = False
                x, y, w, h = cv2.selectROI(display_name, frame_disp, False, False)
                init_state = [x, y, w, h]
                print(f"idx:{idx}, init_state: {init_state}")

            tracker.initialize(frame, _build_init_info(init_state))

            conf = 1
            bbox = [init_state[0], init_state[1], init_state[0] + init_state[2], init_state[1] + init_state[3]]

        else:
            # Draw box
            out = tracker.track(frame,debug=debug)

            state = out['target_bbox']
            conf = out["conf"]

            if debug:
                search_img = out["search_img"]
                origin_score_map = out["origin_score_map"]
                weight_score_map = out["weight_score_map"]

            space = 0
            bbox = [state[0] - space, state[1] - space, state[2] + state[0] + space, state[3] + state[1] + space]
            color = (0, 255, 0)
            logger.update(frame_id=idx,out=out.copy())
            if debug and "d2" in out:
                d2 = out["d2"]
                pred_cx = out["pred_cx"]
                pred_cy = out["pred_cy"]
                lost = out["lost"]
                psr = out["psr"]
                status = out["status"]
                raw_bbox = out["raw_bbox"]
                reason = out["reason"]
                dir_angle = out["dir_angle"]
                obs_velocity = out["obs_velocity"]
                pred_velocity = out["pred_velocity"]
                vd2 = out["vd2"]


                cv2.rectangle(frame_disp, (width - 450, height - 130), (width, height), (255, 255, 255), -1)

                cv2.putText(frame_disp, f"d2:{d2:.2f},vd2:{vd2:.2f}", (width - 450, height-10),
                            cv2.FONT_HERSHEY_DUPLEX, 1, (255, 0, 255), 1)
                cv2.putText(frame_disp, f"obsv:{obs_velocity:.2f},predv:{pred_velocity:.2f}",
                            (width - 450, height - 40),
                            cv2.FONT_HERSHEY_DUPLEX, 1, (255, 0, 255), 1)

                cv2.putText(frame_disp, f"psr:{psr:.2f},angle:{dir_angle:.2f}",
                            (width - 450, height - 70),
                            cv2.FONT_HERSHEY_DUPLEX, 1, (255, 0, 255), 1)

                cv2.putText(frame_disp, f"{lost},{status},{reason}", (width - 450, height - 100),
                            cv2.FONT_HERSHEY_DUPLEX, 1, (255, 0, 255), 1)



                raw_x,raw_y,raw_w,raw_h = [int(t) for t in raw_bbox]
                cv2.rectangle(frame_disp, (raw_x, raw_y),(raw_x + raw_w, raw_y + raw_h), (255, 0, 255), 2)
                cv2.circle(frame_disp, (int(pred_cx), int(pred_cy)), 5, (0,0,255), -1)

        if debug and origin_score_map is not None:
            weight_img = visualize_score_map(weight_score_map, search_img)

            origin_score_map = (origin_score_map * 255).astype(np.uint8)
            weight_score_map = (weight_score_map * 255).astype(np.uint8)
            origin_score_map = cv2.cvtColor(origin_score_map,cv2.COLOR_GRAY2RGB)
            weight_score_map = cv2.cvtColor(weight_score_map,cv2.COLOR_GRAY2BGR)

            score_h,score_w = origin_score_map.shape[:2]
            scale = 0.8
            max_h = height // 3

            max_scale = max_h / score_h
            scale = min(scale, max_scale)
            origin_score_map = cv2.resize(origin_score_map, None,fx=scale,fy=scale)
            weight_score_map = cv2.resize(weight_score_map,None,fx=scale,fy=scale)
            weight_img = cv2.resize(weight_img,None,fx=scale,fy=scale)

            w = origin_score_map.shape[1]
            cv2.putText(origin_score_map,f"origin",(10,20),cv2.FONT_HERSHEY_COMPLEX_SMALL, 1, (0, 255, 255), 1)
            cv2.putText(weight_score_map, f"weight", (10, 20), cv2.FONT_HERSHEY_COMPLEX_SMALL, 1, (0, 255, 255), 1)

            frame_disp[0:w,0:w] = origin_score_map
            frame_disp[w:w*2,0:w] = weight_score_map
            frame_disp[w*2:w*3,0:w] = weight_img

        cv2.rectangle(frame_disp, (int(bbox[0]), int(bbox[1])), (int(bbox[2]), int(bbox[3])), color, 2)
        cv2.putText(frame_disp, f'{conf:.2f}', (int(bbox[0]), int(bbox[1]) - 20), cv2.FONT_HERSHEY_COMPLEX_SMALL, 2, color, 1)

        if save_results:
            bbox_logger.log_frame(frame_id=idx,x=bbox[0],y=bbox[1],w=bbox[2]-bbox[0],h=bbox[3]-bbox[1])

        if save_video:
            writer.write(frame_disp)

        interval = 1

        cv2.imshow(display_name, frame_disp)
        key = cv2.waitKey(interval) & 0xFF
        if key == 27:
            break
        elif key == 32:
            cv2.waitKey(0)

        elif key == ord("r"):
            reSelect = True

    cap.release()
    cv2.destroyAllWindows()

    if save_video:
        writer.release()


def main():

    parser = argparse.ArgumentParser(description='Run the tracker on your webcam.')
    parser.add_argument('--videofile',  type=str, help='path to a video file.',required=True)
    parser.add_argument('--optional_box', type=float, nargs="+", help='optional_box with format x y w h.')
    parser.add_argument('--save_results', dest='save_results', action='store_true', default=True,help='Save bounding boxes')
    parser.add_argument('--save_video', dest='save_video', action='store_true', default=False, help='Save bounding boxes')
    parser.add_argument('--checkpoint', type=str,
                        default=r"/home/lz/wanghd/OSTrack/weights/ostrack-260415.pth.tar", help='Save bounding boxes')

    args = parser.parse_args()
    tarcker = create_tracker(checkpoint=args.checkpoint, enabled_CE=False)
    run_video(args.videofile, tracker=tarcker, optional_box=args.optional_box, save_results=args.save_results, save_video=args.save_video)



if __name__ == '__main__':

    main()




