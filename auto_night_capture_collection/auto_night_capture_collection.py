#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
  夜间多帧存图自动化脚本
================================================================================

功能说明：
    自动化完成夜间多帧图像采集的全流程，包括：
    1. 从 Seafile 下载临时版本文件
    2. 修改相机配置（密码、debug 模式）
    3. 停止原服务并启动多帧采集程序
    4. 采集完成后复制数据并上传到 Seafile

依赖安装：
    pip3 install requests pyyaml

使用方法：
    sudo python3 night_capture_automation.py

作者：OpenClaw AI
日期：2025-01
================================================================================
"""

import os
import sys
import time
import subprocess
import requests
import yaml
import shutil
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

# 禁用 HTTPS 警告（内网自签名证书）
requests.packages.urllib3.disable_warnings()


# ==================== 配置区域 ====================
class Config:
    """全局配置类 - 使用前请确认以下参数"""

    # ---------- Seafile 配置 ----------
    SEAFILE_BASE_URL = "https://file.lizhengtech.com:4443"
    SEAFILE_USERNAME = "zhangtengyu@lizhengtech.com"
    SEAFILE_PASSWORD = "2989zty"

    # 上传目标库 ID 和路径
    UPLOAD_REPO_ID = "e0d46121-60f6-4a11-ac1e-e47d9e54e6e1"
    UPLOAD_PARENT_DIR = "/openclawpy"

    # 临时版本文件 Seafile 路径（下载源）
    TEMP_VERSION_REPO = "7cda2314-3b67-4668-a3c2-cf0092d96f91"
    TEMP_VERSION_PATH = "临时版本文件/夜间多帧保存版本/夜间多帧图片保存"

    # ---------- 本地路径配置 ----------
    GVS_CONFIG_DIR = "/opt/lz/config/gvs"
    GVS_BINARY = "/opt/lz/config/gvs/gvs-latest-x86_64.AppImage"
    GVS_HISTORY_DIR = "/opt/lz/gvs/history/night/debug"
    TARGET_COPY_DIR = "/home/defsysoperator/zhangty"  # 修正路径

    # ---------- 相机配置 ----------
    CAMERA_PASSWORD = "lzno1root"
    NARROW_CAMERA_HOST = "192.178.1.64"
    WIDE_CAMERA_HOST = "192.178.1.61"
    CAMERA_PORT = 39020
    RTSP_PORT = 554
    CAMERA_USERNAME = "admin"

    # ---------- 超时配置 ----------
    SERVICE_CHECK_TIMEOUT = 30
    MAX_RETRIES = 3
    SERVICE_WAIT_TIME = 10


# ==================== 日志工具 ====================
def log(msg, level="INFO"):
    """
    打印带时间戳的日志

    Args:
        msg: 日志消息
        level: 日志级别 (INFO/WARN/ERROR/DEBUG)
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prefix = {
        "INFO": "✓",
        "WARN": "⚠",
        "ERROR": "✗",
        "DEBUG": "·"
    }.get(level, "•")

    print(f"[{timestamp}] [{level}] {prefix} {msg}")
    sys.stdout.flush()


# ==================== 命令执行工具 ====================
def run_command(cmd, sudo=False, check=True):
    """
    执行 shell 命令

    Args:
        cmd: 命令字符串或列表
        sudo: 是否使用 sudo 执行
        check: 是否检查返回码

    Returns:
        tuple: (success: bool, output: str)
    """
    try:
        if isinstance(cmd, str):
            cmd = cmd.split()

        if sudo:
            cmd = ["sudo"] + cmd

        log(f"执行：{' '.join(cmd)}", "DEBUG")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=check
        )

        if result.stdout:
            log(f"输出：{result.stdout.strip()}", "DEBUG")
        if result.stderr and result.returncode != 0:
            log(f"错误：{result.stderr.strip()}", "WARN")

        return result.returncode == 0, result.stdout

    except subprocess.CalledProcessError as e:
        log(f"命令失败：{e}", "ERROR")
        return False, str(e)
    except Exception as e:
        log(f"执行异常：{e}", "ERROR")
        return False, str(e)


# ==================== Seafile 客户端 ====================
class SeafileClient:
    """Seafile API 客户端"""

    def __init__(self, base_url, username, password):
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.token = None
        self.session = requests.Session()
        self.session.verify = False  # 忽略证书验证

    def login(self):
        """
        登录 Seafile 获取 token

        Returns:
            bool: 登录是否成功
        """
        url = f"{self.base_url}/api2/auth-token/"
        data = {"username": self.username, "password": self.password}

        try:
            log("正在登录 Seafile...")
            response = self.session.post(url, data=data)

            if response.status_code == 200:
                self.token = response.json().get('token')
                self.session.headers.update({"Authorization": f"Token {self.token}"})
                log("Seafile 登录成功")
                return True
            else:
                log(f"登录失败：{response.status_code}", "ERROR")
                return False

        except Exception as e:
            log(f"登录异常：{e}", "ERROR")
            return False

    def download_file(self, repo_id, file_path, local_path):
        """
        从 Seafile 下载文件

        Args:
            repo_id: 仓库 ID
            file_path: 文件路径
            local_path: 本地保存路径

        Returns:
            bool: 下载是否成功
        """
        if not self.token:
            log("未登录", "ERROR")
            return False

        url = f"{self.base_url}/api2/repos/{repo_id}/file/"
        params = {"p": f"/{file_path}", "op": "download"}

        try:
            log(f"下载：{file_path}")
            response = self.session.get(url, params=params, stream=True)

            if response.status_code == 200:
                os.makedirs(os.path.dirname(local_path), exist_ok=True)

                with open(local_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

                log(f"下载成功：{local_path}")
                return True
            else:
                log(f"下载失败：{response.status_code}", "ERROR")
                return False

        except Exception as e:
            log(f"下载异常：{e}", "ERROR")
            return False

    def upload_file(self, repo_id, local_path, parent_dir="/", filename=None):
        """
        上传文件到 Seafile

        Args:
            repo_id: 仓库 ID
            local_path: 本地文件路径
            parent_dir: 目标目录
            filename: 目标文件名（默认使用原文件名）

        Returns:
            bool: 上传是否成功
        """
        if not self.token:
            log("未登录", "ERROR")
            return False

        url = f"{self.base_url}/api2/repos/{repo_id}/file/"
        params = {"p": parent_dir}

        try:
            file_name = filename or os.path.basename(local_path)
            log(f"上传：{local_path} → {parent_dir}/{file_name}")

            with open(local_path, 'rb') as f:
                files = {'file': (file_name, f)}
                response = self.session.post(url, params=params, files=files)

            if response.status_code in [200, 201]:
                log("上传成功")
                return True
            else:
                log(f"上传失败：{response.status_code}", "ERROR")
                return False

        except Exception as e:
            log(f"上传异常：{e}", "ERROR")
            return False


# ==================== 配置修改工具 ====================
def modify_config_file(file_path, old_pattern, new_value):
    """
    修改配置文件中的指定项

    Args:
        file_path: 配置文件路径
        old_pattern: 要匹配的模式（键名）
        new_value: 新值

    Returns:
        bool: 修改是否成功
    """
    try:
        if not os.path.exists(file_path):
            log(f"文件不存在：{file_path}", "ERROR")
            return False

        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        modified = False
        for i, line in enumerate(lines):
            if old_pattern in line:
                # 保留缩进
                indent = len(line) - len(line.lstrip())
                lines[i] = ' ' * indent + f"{old_pattern.split(':')[0]}: {new_value}\n"
                modified = True
                log(f"修改：{line.strip()} → {lines[i].strip()}")

        if modified:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            return True
        else:
            log(f"未找到匹配项：{old_pattern}", "WARN")
            return False

    except Exception as e:
        log(f"修改失败：{e}", "ERROR")
        return False


# ==================== 服务控制工具 ====================
def check_service_status(service_name):
    """检查服务状态"""
    success, output = run_command(["systemctl", "is-active", service_name], sudo=True, check=False)
    return success and "active" in output


def stop_service(service_name):
    """停止服务"""
    log(f"停止服务：{service_name}")
    success, _ = run_command(["systemctl", "stop", service_name], sudo=True)
    return success


def start_gvs():
    """启动 GVS 程序"""
    log("启动 GVS 多帧程序")
    success, _ = run_command(["sudo", Config.GVS_BINARY])
    return success


# ==================== 主流程步骤 ====================
def step_download_version(seafile):
    """步骤 1: 下载临时版本文件"""
    log("=" * 50)
    log("步骤 1: 下载临时版本文件")
    log("=" * 50)

    local_file = "/tmp/gvs-latest-x86_64.AppImage"
    success = seafile.download_file(Config.TEMP_VERSION_REPO, Config.TEMP_VERSION_PATH, local_file)

    if success:
        run_command(["sudo", "chmod", "775", local_file])
        log("权限已设置为 775")

    return success


def step_modify_camera_config():
    """步骤 2: 修改相机密码配置"""
    log("=" * 50)
    log("步骤 2: 修改相机配置")
    log("=" * 50)

    config_file = f"{Config.GVS_CONFIG_DIR}/gvs_customer.yml"

    success1 = modify_config_file(config_file, "Password:", Config.CAMERA_PASSWORD)
    log(f"NarrowCamera/WideCameras 密码已更新")

    return success1


def step_stop_service():
    """步骤 3: 停止原服务"""
    log("=" * 50)
    log("步骤 3: 停止原 GVS 服务")
    log("=" * 50)

    success = stop_service("gvs")
    time.sleep(2)  # 等待服务完全停止

    return success


def step_enable_debug():
    """步骤 4: 启用 debug 模式"""
    log("=" * 50)
    log("步骤 4: 启用 Debug 模式")
    log("=" * 50)

    config_file = f"{Config.GVS_CONFIG_DIR}/gvs_customer.yml"
    success = modify_config_file(config_file, "LogMode:", "debug")

    return success


def step_enable_multi_frame():
    """步骤 5: 开启多帧采集"""
    log("=" * 50)
    log("步骤 5: 开启多帧采集")
    log("=" * 50)

    config_file = f"{Config.GVS_CONFIG_DIR}/gvs.yml"
    success = modify_config_file(config_file, "EnableCaptureMore:", "true")

    return success


def step_start_gvs():
    """步骤 6: 启动多帧程序"""
    log("=" * 50)
    log("步骤 6: 启动 GVS 多帧程序")
    log("=" * 50)

    success = start_gvs()

    if not success:
        log("首次启动失败，5 秒后重试", "WARN")
        time.sleep(5)
        success = start_gvs()

    return success


def step_check_service():
    """步骤 7: 检查服务状态"""
    log("=" * 50)
    log("步骤 7: 检查服务状态")
    log("=" * 50)

    log(f"等待 {Config.SERVICE_WAIT_TIME} 秒...")
    time.sleep(Config.SERVICE_WAIT_TIME)

    if check_service_status("gvs"):
        log("服务运行正常")
        return True
    else:
        log("服务未运行，尝试重启", "WARN")
        return start_gvs()


def step_copy_data():
    """步骤 8: 复制采集数据"""
    log("=" * 50)
    log("步骤 8: 复制多帧图数据")
    log("=" * 50)

    history_dir = Path(Config.GVS_HISTORY_DIR)

    if not history_dir.exists():
        log(f"目录不存在：{history_dir}", "ERROR")
        return False

    # 查找最新的日期目录
    date_dirs = sorted([d for d in history_dir.iterdir() if d.is_dir()], reverse=True)
    if not date_dirs:
        log("未找到历史数据", "ERROR")
        return False

    latest_dir = date_dirs[0]
    log(f"数据目录：{latest_dir}")

    # 查找最新的文件
    files = sorted([f for f in latest_dir.iterdir() if f.is_file()], reverse=True)
    if not files:
        log("未找到数据文件", "ERROR")
        return False

    latest_file = files[0]
    log(f"数据文件：{latest_file.name}")

    # 复制文件
    os.makedirs(Config.TARGET_COPY_DIR, exist_ok=True)
    target = Path(Config.TARGET_COPY_DIR) / latest_file.name

    try:
        shutil.copy2(latest_file, target)
        log(f"已复制：{target}")
        return True
    except Exception as e:
        log(f"复制失败：{e}", "ERROR")
        return False


def step_upload_data(seafile):
    """步骤 9: 上传数据到 Seafile"""
    log("=" * 50)
    log("步骤 9: 上传数据到 Seafile")
    log("=" * 50)

    target_dir = Path(Config.TARGET_COPY_DIR)

    if not target_dir.exists():
        log("目标目录不存在", "ERROR")
        return False

    files = sorted([f for f in target_dir.iterdir() if f.is_file()], reverse=True)
    if not files:
        log("未找到文件", "ERROR")
        return False

    latest_file = files[0]
    log(f"上传文件：{latest_file.name}")

    success = seafile.upload_file(
        Config.UPLOAD_REPO_ID,
        str(latest_file),
        Config.UPLOAD_PARENT_DIR
    )

    return success


# ==================== 主函数 ====================
def main():
    """主执行流程"""
    print("\n" + "=" * 60)
    print("  夜间多帧存图自动化脚本")
    print("  OpenClaw AI")
    print("=" * 60 + "\n")

    # 初始化 Seafile 客户端
    seafile = SeafileClient(
        Config.SEAFILE_BASE_URL,
        Config.SEAFILE_USERNAME,
        Config.SEAFILE_PASSWORD
    )

    if not seafile.login():
        log("Seafile 登录失败，退出", "ERROR")
        sys.exit(1)

    # 执行流程
    steps = [
        ("下载临时版本", lambda: step_download_version(seafile)),
        ("修改相机配置", step_modify_camera_config),
        ("停止原服务", step_stop_service),
        ("启用 Debug", step_enable_debug),
        ("开启多帧", step_enable_multi_frame),
        ("启动程序", step_start_gvs),
        ("检查服务", step_check_service),
        ("复制数据", step_copy_data),
        ("上传 Seafile", lambda: step_upload_data(seafile)),
    ]

    failed = []

    for name, func in steps:
        try:
            if func():
                log(f"✓ {name} 完成\n")
            else:
                log(f"✗ {name} 失败\n", "ERROR")
                failed.append(name)

                if name in ["下载临时版本", "启动程序"]:
                    log("关键步骤失败，终止", "ERROR")
                    break
        except Exception as e:
            log(f"{name} 异常：{e}", "ERROR")
            failed.append(name)

    # 总结
    print("\n" + "=" * 60)
    if failed:
        print(f"  失败：{', '.join(failed)}")
        print("  请检查日志后重试")
        sys.exit(1)
    else:
        print("  全部完成！✓")
        sys.exit(0)


if __name__ == "__main__":
    main()
