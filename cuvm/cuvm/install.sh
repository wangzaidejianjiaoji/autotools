#!/usr/bin/env bash

# 作用：cuvm 的安装脚本。把当前 cuvm 项目目录下的 bin/ 加入到用户的 PATH，
#      自动识别 shell 类型（bash/zsh/sh），并把 export PATH 写入对应的
#      rc 文件（~/.bashrc / ~/.zshrc / ~/.profile，macOS 优先 ~/.bash_profile）。
#
# 用法：
#     bash install.sh
#     # 或：./install.sh （需 chmod +x）
#     # 完成后重启终端或执行 source ~/.bashrc（或对应 rc 文件）生效。
#
# 关键参数：
#     - PROJECT_DIR     —— 自动通过 BASH_SOURCE 解析为脚本所在目录的绝对路径。
#     - shell_profile   —— 自动按 ZSH_VERSION / BASH_VERSION / uname=Darwin 选择
#                          ~/.zshrc / ~/.bashrc / ~/.bash_profile(macOS) / ~/.profile。
#     - PATH 注入       —— 若 $PATH 中尚未包含 "$PROJECT_DIR/bin"，则追加 export 语句；
#                          已存在则打印 "cuvm 已经在 ... 中"，不会重复添加。
#     - 该脚本只追加 PATH，不会安装/下载任何 CUDA/cuDNN/TensorRT 真实软件。

# cuvm installer

# 获取项目根目录
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 检测 shell 类型
if [[ -n "$ZSH_VERSION" ]]; then
  shell_profile="$HOME/.zshrc"
elif [[ -n "$BASH_VERSION" ]]; then
  shell_profile="$HOME/.bashrc"
  # 对于 macOS，如果存在 .bash_profile 则使用它
  if [[ "$(uname)" == "Darwin" ]] && [[ -f "$HOME/.bash_profile" ]]; then
    shell_profile="$HOME/.bash_profile"
  fi
else
  shell_profile="$HOME/.profile"
fi

# 将 cuvm 添加到 PATH（如果尚未添加）
if ! echo "$PATH" | grep -q "$PROJECT_DIR/bin"; then
  echo "" >> "$shell_profile"
  echo "# cuvm" >> "$shell_profile"
  echo "export PATH=\"$PROJECT_DIR/bin:\$PATH\"" >> "$shell_profile"
  echo "已将 cuvm 添加到 $shell_profile"
else
  echo "cuvm 已经在 $shell_profile 中"
fi

echo "安装完成。请重启终端或运行 'source $shell_profile' 开始使用 cuvm。"