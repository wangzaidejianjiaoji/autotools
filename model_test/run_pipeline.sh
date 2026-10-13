#!/bin/bash

# 作用：流水线脚本——读取 video_config.txt（每行一个视频路径），
#      对每个视频反复执行 ./run.sh 共 RUN_COUNT 次（默认 5 次），
#      最后清空本地结果目录并把结果移动到按当日日期新建的结果目录
#      （RESULT_BASE_DIR/ostrack-YYMMDD）。
#
# 用法：
#     1) 准备 video_config.txt：每行一个 mp4 路径，支持 # 注释行。
#     2) bash run_pipeline.sh
#        # 或：./run_pipeline.sh （需 chmod +x）
#
# 关键参数（请根据部署环境修改）：
#     - CONFIG_FILE        —— 视频列表配置文件，默认 video_config.txt（与脚本同目录）。
#     - VIDEO_DIR          —— 视频所在目录（仅作参考，路径以 CONFIG_FILE 为准）。
#     - RESULT_BASE_DIR    —— 结果汇总根目录，会按当日日期创建 ostrack-YYMMDD 子目录。
#     - LOCAL_RESULT_DIR   —— 单次 ./run.sh 的本地结果目录，结束时会被清空并搬走。
#     - RUN_COUNT          —— 每个视频重复执行 ./run.sh 的次数，默认 5。
#     - 运行 ./run.sh 时任一次失败会立即停止整个 pipeline（exit 非 0）。

CONFIG_FILE="video_config.txt"
VIDEO_DIR="/home/lz/zhangty/ostrack/20260525/mp4_test"
RESULT_BASE_DIR="/home/lz/zhangty/ostrack_py/videos/result_dir"
LOCAL_RESULT_DIR="/home/lz/zhangty/ostrack/20260525/results"
RUN_COUNT=5

if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: $CONFIG_FILE not found!"
    exit 1
fi

# 清空本地结果目录
echo "Cleaning local results directory: $LOCAL_RESULT_DIR"
if [ -d "$LOCAL_RESULT_DIR" ]; then
    rm -f "$LOCAL_RESULT_DIR"/*
    echo "Local results directory cleaned"
else
    echo "Warning: $LOCAL_RESULT_DIR does not exist"
fi

echo "Starting pipeline execution..."
echo "-----------------------------"

while IFS= read -r line || [[ -n "$line" ]]; do
    line=$(echo "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    
    [ -z "$line" ] && continue
    
    if [[ "$line" == \#* ]]; then
        continue
    fi
    
    video_path=$(echo "$line" | cut -d',' -f1)
    
    if [ -z "$video_path" ]; then
        continue
    fi
    
    video_name=$(basename "$video_path")
    
    echo "Processing video: $video_path"
    echo "Executing 5 runs..."
    echo "----------------------------------------"
    
    for i in $(seq 1 $RUN_COUNT); do
        echo "Run $i/$RUN_COUNT: ./run.sh $video_path"
        
        ./run.sh "$video_path"
        
        exit_code=$?
        if [ $exit_code -ne 0 ]; then
            echo "Error: run.sh failed with exit code $exit_code on run $i for $video_path"
            echo "Stopping pipeline execution."
            exit $exit_code
        fi
        
        echo "Completed run $i for $video_name"
    done
    
    echo "----------------------------------------"
    echo "Completed all 5 runs for: $video_path"
    echo ""
    
done < "$CONFIG_FILE"

echo "-----------------------------"
echo "All videos processed successfully!"
echo ""

# 创建结果目录
current_date=$(date +%y%m%d)
result_dir="${RESULT_BASE_DIR}/ostrack-${current_date}"

echo "Creating result directory: $result_dir"
mkdir -p "$result_dir"

if [ $? -ne 0 ]; then
    echo "Error: Failed to create result directory"
    exit 1
fi

# 移动本地结果数据到结果目录
echo "Moving local results from $LOCAL_RESULT_DIR to $result_dir"

if [ -d "$LOCAL_RESULT_DIR" ]; then
    mv "$LOCAL_RESULT_DIR"/* "$result_dir"/ 2>/dev/null
    
    if [ $? -ne 0 ]; then
        echo "Warning: No files to move or move operation failed"
    else
        echo "Local results moved successfully"
    fi
else
    echo "Warning: Local result directory $LOCAL_RESULT_DIR does not exist"
fi

echo "-----------------------------"
echo "Pipeline execution completed successfully!"