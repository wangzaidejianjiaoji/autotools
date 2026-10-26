# cuvm - CUDA Version Manager

CUDA Version Manager (cuvm) 是一个用于管理多个 CUDA、cuDNN 和 TensorRT 版本的工具，类似于 Node.js 的 nvm。

## 特性

- 安装、切换和卸载 CUDA 版本
- 自动安装与 CUDA 版本匹配的 cuDNN
- 支持为同一 CUDA 版本安装多个兼容的 TensorRT 版本
- 独立管理每个组件的环境变量
- 通过配置文件轻松定制

## 项目结构

```
cuvm/
├── bin/                 # 可执行脚本
│   ├── cuvm             # 主脚本
│   ├── download         # 下载脚本
│   ├── install          # 安装脚本
│   └── env              # 环境变量脚本
├── config/              # 配置文件
│   └── cuvm.yaml        # 主配置文件
├── lib/                 # 库文件
│   └── utils.sh         # 工具函数
├── downloads/           # 下载文件存储目录
├── versions/            # 安装版本存储目录
├── README.md
└── install.sh           # 安装脚本
```

## 安装

1. 克隆此仓库：
   ```bash
   git clone https://github.com/yourusername/cuvm.git
   cd cuvm
   ```

2. 运行安装脚本：
   ```bash
   ./install.sh
   ```

3. 重启终端或运行：
   ```bash
   source ~/.bashrc  # 或者 ~/.zshrc, ~/.bash_profile，取决于您的 shell
   ```

## 使用方法

### CUDA 管理

```bash
# 安装 CUDA 版本
cuvm install 11.8

# 切换到 CUDA 版本
cuvm use 11.8

# 卸载 CUDA 版本
cuvm uninstall 11.8

# 列出已安装的 CUDA 版本
cuvm list

# 显示当前 CUDA 版本
cuvm current
```

### cuDNN 管理

```bash
# 为当前 CUDA 版本安装 cuDNN
cuvm install-cudnn 8.9.7

# 切换到 cuDNN 版本
cuvm use-cudnn 8.9.7

# 卸载 cuDNN 版本
cuvm uninstall-cudnn 8.9.7

# 列出当前 CUDA 版本的已安装 cuDNN 版本
cuvm list-cudnn
```

### TensorRT 管理

```bash
# 为当前 CUDA 版本安装 TensorRT
cuvm install-tensorrt 8.6.1

# 切换到 TensorRT 版本
cuvm use-tensorrt 8.6.1

# 卸载 TensorRT 版本
cuvm uninstall-tensorrt 8.6.1

# 列出当前 CUDA 版本的已安装 TensorRT 版本
cuvm list-tensorrt

# 列出与当前 CUDA 版本兼容的 TensorRT 版本
cuvm list-compatible-tensorrt
```

### 带依赖安装

```bash
# 安装 CUDA 及匹配的 cuDNN
cuvm install 11.8 --with-cudnn

# 安装 CUDA 及特定版本的 TensorRT
cuvm install 11.8 --with-tensorrt 8.6.1
```

## 配置

所有配置都存储在 `config/cuvm.yaml` 文件中，包括目录路径、下载 URL 模板和版本映射。

### 版本映射

cuvm 支持两种版本映射：
1. CUDA 与 cuDNN 的一对一映射
2. CUDA 与 TensorRT 的一对多映射

您可以在配置文件中自定义这些映射关系。

## 贡献

欢迎提交 Issue 和 Pull Request。

## 许可证

本项目采用 [MIT 许可证](LICENSE)。