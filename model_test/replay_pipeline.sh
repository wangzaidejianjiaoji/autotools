#!/bin/bash

# 作用：批量执行 gvs replay 的 Pipeline 脚本。
#      依次完成：清空 track 目录 -> 遍历每个 mp4 调用 gvs replay ->
#      json 转 txt -> 转移数据到带日期的结果目录 ->
#      执行评估脚本 eval_versions.py -> 启动 Web 报告服务器（端口 8083）。
#
# 用法：
#     bash replay_pipeline.sh
#     # 或：./replay_pipeline.sh （需 chmod +x）
#
# 关键参数（请根据部署环境修改）：
#     - GVS_APP          —— gvs replay 程序路径，默认 /home/lz/zhangty/gvs-0722.app。
#     - CONFIG_PATH      —— gvs 配置目录，默认 /opt/lz/config/gvs/。
#     - VIDEO_DIR        —— 待回放视频目录（仅扫描 maxdepth=1 的 *.mp4）。
#     - TRACK_DIR        —— gvs 推理输出 track 目录，运行前会被清空。
#     - RESULT_BASE      —— 推理结果汇总根目录，会按当日日期创建子目录。
#     - JSON_SCRIPT      —— json_to_txt_batch.py 路径（用于将 json 转为 txt）。
#     - EVAL_SCRIPT_DIR  —— 评估脚本所在目录（eval_versions.py 位于其下）。
#     - HTTP_SERVER_SCRIPT / REPORT_DIR / SERVER_PORT
#                         —— 评估结束后启动的 HTTP 服务脚本、报告目录与端口。
#     - 当前日期 RESULT_DIR 命名规则：${RESULT_BASE}replay-YYYYMMDD。

set -e

# 配置参数
GVS_APP="/home/lz/zhangty/gvs-0722.app"
CONFIG_PATH="/opt/lz/config/gvs/"
VIDEO_DIR="/home/lz/zhangty/ostrack/20260525/mp4_test/"
TRACK_DIR="/opt/lz/gvs/history/day/track/"
RESULT_BASE="/home/lz/zhangty/ostrack_py/videos/result_dir/"
JSON_SCRIPT="/home/lz/zhangty/ostrack_py/videos/result_dir/json_to_txt_batch.py"

# 获取当前日期，格式：YYYYMMDD
CURRENT_DATE=$(date +%Y%m%d)
RESULT_DIR="${RESULT_BASE}replay-${CURRENT_DATE}"

echo "=========================================="
echo "Pipeline 开始执行"
echo "时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="

# 1. 清空track目录
echo "[步骤1] 清空 ${TRACK_DIR} 目录..."
sudo rm -rf "${TRACK_DIR}"*
echo "清空完成"

# 2. 获取所有mp4文件
echo "[步骤2] 扫描视频文件..."
mapfile -t VIDEO_FILES < <(find "${VIDEO_DIR}" -maxdepth 1 -name "*.mp4" -type f | sort)
VIDEO_COUNT=${#VIDEO_FILES[@]}
echo "找到 ${VIDEO_COUNT} 个视频文件"

if [ ${VIDEO_COUNT} -eq 0 ]; then
    echo "错误：未找到任何mp4文件"
    exit 1
fi

# 3. 遍历每个视频执行replay
echo "[步骤3] 开始执行replay..."
TOTAL_RUNS=${VIDEO_COUNT}
CURRENT_RUN=0

for video_path in "${VIDEO_FILES[@]}"; do
    CURRENT_RUN=$((CURRENT_RUN + 1))
    video_name=$(basename "${video_path}")
    echo ""
    echo "[${CURRENT_RUN}/${TOTAL_RUNS}] 视频: ${video_name}"
    
    # 停止gvs服务
    echo "  停止gvs服务..."
    sudo systemctl stop gvs
    
    # 执行replay命令
    echo "  执行: sudo ${GVS_APP} -replay ${CONFIG_PATH} -video ${video_path}"
    sudo "${GVS_APP}" -replay "${CONFIG_PATH}" -video "${video_path}"
    
    echo "  完成"
done

echo ""
echo "=========================================="
echo "所有视频执行完毕"
echo "=========================================="

# 4. 执行json转txt脚本
echo ""
echo "[步骤4] 执行json转txt脚本..."
python3 "${JSON_SCRIPT}" "${TRACK_DIR}"

# 5. 创建结果目录并转移数据
echo ""
echo "[步骤5] 创建结果目录并转移数据..."
mkdir -p "${RESULT_DIR}"
echo "创建目录: ${RESULT_DIR}"

# 转移所有数据
sudo mv "${TRACK_DIR}"* "${RESULT_DIR}/" 2>/dev/null || true
echo "数据转移完成"

# 显示结果
echo ""
echo "=========================================="
echo "Pipeline 执行完成"
echo "时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "结果目录: ${RESULT_DIR}"
echo "=========================================="

# 列出结果目录内容
echo ""
echo "结果文件列表:"
ls -la "${RESULT_DIR}"

# 6. 执行评估脚本
echo ""
echo "[步骤6] 执行评估脚本..."
VERSION_NAME=$(basename "${RESULT_DIR}")
EVAL_SCRIPT_DIR="/home/lz/zhangty/ostrack_py/execute_script"

cd "${EVAL_SCRIPT_DIR}"
python3 eval_versions.py "${VERSION_NAME}"

if [ $? -ne 0 ]; then
    echo "错误：评估脚本执行失败"
    exit 1
fi

echo "评估完成"

# 7. 启动web服务器（端口8081）
echo ""
echo "[步骤7] 启动web服务器..."
HTTP_SERVER_SCRIPT="/home/lz/zhangty/ostrack_py/videos/result_dir/start_http_server.py"
REPORT_DIR="/home/lz/zhangty/ostrack_py/videos/report_dir"
SERVER_PORT=8083

# 查找最新的报告目录
LATEST_REPORT=$(ls -td "${REPORT_DIR}"/*/ 2>/dev/null | head -n 1)

if [ -z "${LATEST_REPORT}" ]; then
    echo "警告：未找到报告目录"
else
    # 检查端口是否已被占用，尝试释放
    if ss -tlnp | grep -q ":${SERVER_PORT} "; then
        echo "端口${SERVER_PORT}已被占用，尝试停止旧服务..."
        fuser -k ${SERVER_PORT}/tcp 2>/dev/null || true
        sleep 3
    fi
    
    # 如果端口仍然被占用，尝试多次启动
    MAX_RETRIES=3
    RETRY=0
    STARTED=false
    
    while [ $RETRY -lt $MAX_RETRIES ]; do
        RETRY=$((RETRY + 1))
        echo "  尝试启动 (第${RETRY}次)..."
        
        nohup python3 "${HTTP_SERVER_SCRIPT}" --port ${SERVER_PORT} --bind 0.0.0.0 --dir "${LATEST_REPORT}" > /tmp/http_server_${SERVER_PORT}.log 2>&1 &
        SERVER_PID=$!
        
        # 等待服务器启动
        sleep 3
        
        # 验证服务器是否启动成功
        if curl -s -o /dev/null -w "%{http_code}" http://localhost:${SERVER_PORT}/ 2>/dev/null | grep -q "200"; then
            echo "Web服务器启动成功 (PID: ${SERVER_PID})"
            echo "访问地址: http://192.168.87.107:${SERVER_PORT}/"
            echo "报告目录: ${LATEST_REPORT}"
            STARTED=true
            break
        else
            echo "  启动失败，等待2秒后重试..."
            kill $SERVER_PID 2>/dev/null || true
            sleep 2
        fi
    done
    
    if [ "$STARTED" != "true" ]; then
        echo "警告：Web服务器启动失败，请检查日志: /tmp/http_server_${SERVER_PORT}.log"
        cat /tmp/http_server_${SERVER_PORT}.log 2>/dev/null || true
    fi
fi

echo ""
echo "=========================================="
echo "Pipeline 全部完成"
echo "时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "结果目录: ${RESULT_DIR}"
echo "报告地址: http://localhost:8081/"
echo "=========================================="