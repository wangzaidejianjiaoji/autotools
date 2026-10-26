#!/usr/bin/env bash

# 作用：cuvm 项目的 bash 工具函数库，被其它脚本通过 `source ./lib/utils.sh` 加载。
#      提供：
#        1) load_config <yaml>           —— 解析 cuvm.yaml 并导出 CUVB_* 路径变量；
#        2) get_cudnn_version <cuda> <yaml> —— 查询 CUDA 对应的 cuDNN 版本；
#        3) get_tensorrt_versions <cuda> <yaml> —— 查询 CUDA 对应的 TensorRT 版本列表；
#        4) print_info / print_warning / print_error  —— 带 ANSI 颜色的日志输出；
#        5) command_exists <cmd>         —— 判断命令是否可用。
#
# 用法：
#     # 在其它脚本中通过 source 引入：
#     source "$(dirname "$0")/lib/utils.sh"
#     load_config "./config/cuvm.yaml"
#     print_info "下载目录: $CUVB_DOWNLOADS_DIR"
#     get_tensorrt_versions "11.8" "./config/cuvm.yaml"
#
# 关键参数（不接收命令行参数，全部为函数调用参数 / 环境变量）：
#     - load_config <config_file>：
#         CUVB_DOWNLOADS_DIR  —— 由 yaml 的 downloads 路径解析（~ 展开为 $HOME）；
#         CUVB_VERSIONS_DIR   —— 由 yaml 的 versions 路径解析；
#         CUVB_CUDA_SYMLINK   —— yaml 中 cuda_symlink 字段。
#         并自动 mkdir -p 下载与版本目录。
#     - get_cudnn_version <cuda_version> <config_file>：返回形如 "8.9" 的字符串。
#     - get_tensorrt_versions <cuda_version> <config_file>：
#         最多返回 3 个版本，每行一个（如 8.6.1 / 8.5.3 / 8.2.5）。
#     - print_info/print_warning/print_error 颜色：绿/黄/红（\033[32m/33m/31m）。
#     - YAML 解析使用 awk + sed，属于极简解析；不要求严格的 YAML 库。

# 工具函数库

# 加载 YAML 配置文件
load_config() {
  local config_file="$1"
  if [[ ! -f "$config_file" ]]; then
    echo "错误：找不到配置文件 $config_file"
    return 1
  fi
  
  # 使用 awk 解析简单的 YAML 格式
  # 注意：这只是基本的解析，实际项目中可能需要更复杂的解析器
  export CUVB_DOWNLOADS_DIR=$(awk '/downloads:/ {getline; print $2}' "$config_file" | sed 's/~/$HOME/')
  export CUVB_VERSIONS_DIR=$(awk '/versions:/ {getline; print $2}' "$config_file" | sed 's/~/$HOME/')
  export CUVB_CUDA_SYMLINK=$(awk '/cuda_symlink:/ {getline; print $2}' "$config_file")
  
  # 创建目录
  mkdir -p "$CUVB_DOWNLOADS_DIR"
  mkdir -p "$CUVB_VERSIONS_DIR"
}

# 获取 CUDA 版本对应的 cuDNN 版本
get_cudnn_version() {
  local cuda_version="$1"
  local config_file="$2"
  
  # 从配置文件中获取映射
  local cudnn_version=$(awk "/$cuda_version:/ {print \$2}" "$config_file")
  echo "$cudnn_version"
}

# 获取 CUDA 版本对应的 TensorRT 版本列表
get_tensorrt_versions() {
  local cuda_version="$1"
  local config_file="$2"
  
  # 使用我们之前测试过可以工作的命令
  grep -A 20 "\"$cuda_version\":" "$config_file" 2>/dev/null | \
    grep -E '^\s*-\s*"[0-9.]+"' | \
    sed -E 's/^[[:space:]]*-[[:space:]]*"([0-9.]+)".*/\1/' | \
    head -n 3
}

# 打印带颜色的信息
print_info() {
  echo -e "\033[32m$1\033[0m"  # 绿色
}

print_warning() {
  echo -e "\033[33m$1\033[0m"  # 黄色
}

print_error() {
  echo -e "\033[31m$1\033[0m"  # 红色
}

# 检查命令是否存在
command_exists() {
  command -v "$1" >/dev/null 2>&1
}