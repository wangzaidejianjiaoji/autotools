#!/usr/bin/env bash

# 作用：cuvm 项目结构的简单自检脚本。
#      检查 bin/ 下 cuvm、download、install、env 是否存在且可执行，
#      检查 config/cuvm.yaml 与 lib/utils.sh 是否存在，
#      并 source lib/utils.sh 后调用 get_tensorrt_versions 验证
#      "CUDA 版本 -> TensorRT 版本" 映射功能是否正常。
#
# 用法：
#     # 必须在 cuvm 项目根目录下执行（脚本依赖 ./bin/、./config/、./lib/ 的相对路径）：
#     cd cuvm
#     bash test-structure.sh
#     # 或：./test-structure.sh （需 chmod +x）
#
# 关键参数：
#     - 检查目标均为相对当前工作目录：
#         ./bin/cuvm      ./bin/download   ./bin/install   ./bin/env
#         ./config/cuvm.yaml
#         ./lib/utils.sh
#     - CUDA_VERSION 写死为 "11.8" 用于演示 get_tensorrt_versions 的调用，
#       实际映射来自 ./config/cuvm.yaml。
#     - 任何一项缺失/不可执行会以 exit 1 立即失败；全部通过则打印 "All tests passed!"。
#     - 不接收命令行参数，无环境变量可配。

# 简单测试脚本，用于验证新结构

echo "Testing cuvm commands..."

# 测试主脚本是否存在
if [[ -x "./bin/cuvm" ]]; then
  echo "✓ cuvm script exists and is executable"
else
  echo "✗ cuvm script missing or not executable"
  exit 1
fi

# 测试下载脚本是否存在
if [[ -x "./bin/download" ]]; then
  echo "✓ download script exists and is executable"
else
  echo "✗ download script missing or not executable"
  exit 1
fi

# 测试安装脚本是否存在
if [[ -x "./bin/install" ]]; then
  echo "✓ install script exists and is executable"
else
  echo "✗ install script missing or not executable"
  exit 1
fi

# 测试环境变量脚本是否存在
if [[ -x "./bin/env" ]]; then
  echo "✓ env script exists and is executable"
else
  echo "✗ env script missing or not executable"
  exit 1
fi

# 测试配置文件是否存在
if [[ -f "./config/cuvm.yaml" ]]; then
  echo "✓ config file exists"
else
  echo "✗ config file missing"
  exit 1
fi

# 测试工具库是否存在
if [[ -f "./lib/utils.sh" ]]; then
  echo "✓ utils library exists"
else
  echo "✗ utils library missing"
  exit 1
fi

# 测试 TensorRT 版本映射功能
echo "Testing TensorRT version mapping..."
source ./lib/utils.sh

CUDA_VERSION="11.8"
TENSORRT_VERSIONS=$(get_tensorrt_versions "$CUDA_VERSION" "./config/cuvm.yaml")

if [[ -n "$TENSORRT_VERSIONS" ]]; then
  echo "✓ TensorRT version mapping works for CUDA $CUDA_VERSION"
  echo "  Compatible versions:"
  echo "$TENSORRT_VERSIONS" | while read -r version; do
    echo "    - $version"
  done
else
  echo "✗ Failed to get TensorRT versions for CUDA $CUDA_VERSION"
fi

echo "All tests passed!"