#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SSH 快捷命令工具 - 可视化按钮操作，免密登录 Linux 服务器
支持自定义命令按钮和密码输入
依赖安装：pip install paramiko
"""

import json
import threading
import queue
import time
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, simpledialog
import paramiko

# ==================== 配置管理 ====================
SERVERS_CONFIG_FILE = "servers.json"
COMMANDS_CONFIG_FILE = "commands.json"

def load_servers():
    """从 JSON 文件加载服务器列表"""
    try:
        with open(SERVERS_CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_servers(servers):
    """保存服务器列表到 JSON 文件"""
    with open(SERVERS_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(servers, f, indent=2, ensure_ascii=False)

def load_custom_commands():
    """从 JSON 文件加载自定义命令列表"""
    try:
        with open(COMMANDS_CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        # 返回默认命令
        return [
            {"name": "磁盘使用", "command": "df -h", "need_password": False},
            {"name": "内存使用", "command": "free -m", "need_password": False},
            {"name": "CPU负载", "command": "top -bn1 | head -5", "need_password": False},
            {"name": "当前目录", "command": "pwd", "need_password": False},
            {"name": "列出文件", "command": "ls -la", "need_password": False},
            {"name": "系统日志", "command": "tail -10 /var/log/messages", "need_password": False},
        ]

def save_custom_commands(commands):
    """保存自定义命令列表到 JSON 文件"""
    with open(COMMANDS_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(commands, f, indent=2, ensure_ascii=False)

# ==================== SSH 连接与命令执行线程 ====================
class SSHThread(threading.Thread):
    def __init__(self, host, port, username, password, output_queue):
        super().__init__()
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.output_queue = output_queue   # 用于向 GUI 传递输出信息
        self.command_queue = queue.Queue() # 接收要执行的命令
        self.client = None
        self.running = True
        self.current_channel = None        # 当前执行的命令通道
        self.current_command = None        # 当前执行的命令

    def run(self):
        try:
            # 建立 SSH 连接
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.client.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=10
            )
            self.output_queue.put(("status", f"✅ 已连接到 {self.username}@{self.host}:{self.port}"))

            # 循环等待执行命令
            while self.running:
                try:
                    cmd_data = self.command_queue.get(timeout=1)  # 每秒检查一次退出标志
                except queue.Empty:
                    continue
                if cmd_data == "__EXIT__":
                    break
                
                # 解析命令数据
                if isinstance(cmd_data, dict):
                    cmd = cmd_data.get("command", "")
                    need_password = cmd_data.get("need_password", False)
                    password_input = cmd_data.get("password_input", "")
                else:
                    cmd = cmd_data
                    need_password = False
                    password_input = ""
                
                # 执行命令
                try:
                    # 先显示执行的命令
                    self.output_queue.put(("output", f"$ {cmd}"))
                    
                    # 保存当前命令信息
                    self.current_command = cmd
                    
                    if need_password and password_input:
                        # 使用 sudo 执行命令，自动输入密码
                        full_cmd = f"echo '{password_input}' | sudo -S {cmd}"
                        stdin, stdout, stderr = self.client.exec_command(full_cmd, timeout=30)
                    else:
                        # 检查是否是持续运行的命令（如 ping）
                        is_continuous_cmd = any(
                            cmd.strip().startswith(c) 
                            for c in ['ping', 'tail -f', 'watch', 'top', 'htop']
                        )
                        
                        if is_continuous_cmd:
                            # 对于持续运行的命令，添加超时限制
                            # ping 命令默认只发送4个包
                            if cmd.strip().startswith('ping') and '-c' not in cmd:
                                cmd = cmd + ' -c 4'
                            stdin, stdout, stderr = self.client.exec_command(cmd, timeout=30)
                        else:
                            stdin, stdout, stderr = self.client.exec_command(cmd, timeout=60)
                    
                    # 保存当前通道以便中断
                    self.current_channel = stdout.channel
                    
                    # 实时读取输出，避免阻塞
                    import select
                    import socket
                    
                    output_lines = []
                    error_lines = []
                    command_terminated = False
                    
                    # 设置通道为非阻塞模式
                    stdout.channel.setblocking(False)
                    stderr.channel.setblocking(False)
                    
                    # 立即检查初始输出（确保ping命令的初始信息能及时显示）
                    # 第一次检查不等待，立即显示初始信息
                    if stdout.channel.recv_ready():
                        data = stdout.channel.recv(1024).decode('utf-8', errors='ignore')
                        if data:
                            output_lines.append(data)
                            self.output_queue.put(("output", data))
                    
                    if stderr.channel.recv_stderr_ready():
                        data = stderr.channel.recv_stderr(1024).decode('utf-8', errors='ignore')
                        if data:
                            error_lines.append(data)
                            self.output_queue.put(("output", data))
                    
                    # 等待命令完成或超时
                    start_time = time.time()
                    while not stdout.channel.exit_status_ready():
                        # 检查是否收到终止信号
                        try:
                            check_cmd = self.command_queue.get_nowait()
                            if check_cmd == "__TERMINATE__":
                                # 终止当前命令
                                stdout.channel.close()
                                command_terminated = True
                                self.output_queue.put(("output", "^Z"))
                                self.output_queue.put(("output", "[命令已终止]"))
                                break
                            else:
                                # 放回队列
                                self.command_queue.put(check_cmd)
                        except queue.Empty:
                            pass
                        
                        # 检查是否超时
                        if time.time() - start_time > 30:  # 30秒超时
                            self.output_queue.put(("output", "[命令执行超时，已终止]"))
                            stdout.channel.close()
                            break
                        
                        # 读取可用输出
                        if stdout.channel.recv_ready():
                            data = stdout.channel.recv(1024).decode('utf-8', errors='ignore')
                            if data:
                                output_lines.append(data)
                                # 实时显示输出
                                self.output_queue.put(("output", data))
                        
                        if stderr.channel.recv_stderr_ready():
                            data = stderr.channel.recv_stderr(1024).decode('utf-8', errors='ignore')
                            if data:
                                error_lines.append(data)
                                self.output_queue.put(("output", data))
                        
                        # 减少等待时间，提高响应速度
                        time.sleep(0.05)
                    
                    # 清除当前通道
                    self.current_channel = None
                    self.current_command = None
                    
                    # 如果命令被终止，跳过读取剩余输出
                    if command_terminated:
                        continue
                    
                    # 读取剩余输出
                    remaining_out = stdout.read().decode('utf-8', errors='ignore')
                    remaining_err = stderr.read().decode('utf-8', errors='ignore')
                    
                    if remaining_out:
                        self.output_queue.put(("output", remaining_out))
                    if remaining_err:
                        self.output_queue.put(("output", f"(stderr) {remaining_err}"))
                    
                    # 如果没有实时输出，显示完整输出
                    if not output_lines and not error_lines:
                        out = stdout.read().decode('utf-8', errors='ignore')
                        err = stderr.read().decode('utf-8', errors='ignore')
                        
                        if out:
                            self.output_queue.put(("output", out))
                        if err:
                            self.output_queue.put(("output", f"(stderr) {err}"))
                    
                except Exception as e:
                    self.output_queue.put(("error", f"命令执行失败: {str(e)}"))
        except Exception as e:
            self.output_queue.put(("error", f"连接失败: {str(e)}"))
        finally:
            if self.client:
                self.client.close()
            self.output_queue.put(("status", "🔌 已断开连接"))

    def stop(self):
        """停止线程"""
        self.running = False
        self.command_queue.put("__EXIT__")
    
    def terminate_current_command(self):
        """终止当前正在执行的命令（模拟 Ctrl+Z）"""
        if self.current_channel and not self.current_channel.exit_status_ready():
            self.command_queue.put("__TERMINATE__")
            return True
        return False

# ==================== 主界面 ====================
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SSH 快捷命令工具")
        self.geometry("900x700")
        self.resizable(True, True)

        # 加载配置
        self.servers = load_servers()
        self.custom_commands = load_custom_commands()
        self.current_thread = None
        self.output_queue = queue.Queue()
        self.command_buttons = []  # 存储自定义命令按钮

        # 创建界面组件
        self.create_widgets()
        
        # 绑定全局快捷键 Ctrl+Z
        self.bind('<Control-z>', self.on_ctrl_z)
        self.bind('<Control-Z>', self.on_ctrl_z)

        # 每隔 100ms 检查输出队列，更新界面
        self.poll_output_queue()

    def create_widgets(self):
        # 顶部：服务器选择与连接控制
        top_frame = ttk.Frame(self, padding="5")
        top_frame.pack(fill=tk.X)

        ttk.Label(top_frame, text="服务器:").pack(side=tk.LEFT, padx=(0,5))
        self.server_var = tk.StringVar()
        self.server_combo = ttk.Combobox(top_frame, textvariable=self.server_var, width=30)
        self.server_combo['values'] = [f"{s['name']} ({s['host']}:{s['port']})" for s in self.servers]
        self.server_combo.pack(side=tk.LEFT, padx=5)
        self.server_combo.bind('<<ComboboxSelected>>', self.on_server_selected)

        ttk.Button(top_frame, text="添加服务器", command=self.add_server).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_frame, text="删除服务器", command=self.delete_server).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_frame, text="连接", command=self.connect_server).pack(side=tk.LEFT, padx=20)
        ttk.Button(top_frame, text="断开", command=self.disconnect_server).pack(side=tk.LEFT, padx=5)

        # 自定义命令按钮区域
        self.cmd_frame = ttk.LabelFrame(self, text="自定义命令按钮", padding="5")
        self.cmd_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # 刷新自定义命令按钮
        self.refresh_command_buttons()

        # 命令管理按钮
        cmd_manage_frame = ttk.Frame(self, padding="5")
        cmd_manage_frame.pack(fill=tk.X, padx=5)
        ttk.Button(cmd_manage_frame, text="➕ 添加命令", command=self.add_custom_command).pack(side=tk.LEFT, padx=5)
        ttk.Button(cmd_manage_frame, text="✏️ 编辑命令", command=self.edit_custom_command).pack(side=tk.LEFT, padx=5)
        ttk.Button(cmd_manage_frame, text="🗑️ 删除命令", command=self.delete_custom_command).pack(side=tk.LEFT, padx=5)

        # 自定义命令输入
        custom_frame = ttk.Frame(self, padding="5")
        custom_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(custom_frame, text="自定义命令:").pack(side=tk.LEFT)
        self.custom_cmd_var = tk.StringVar()
        custom_entry = ttk.Entry(custom_frame, textvariable=self.custom_cmd_var, width=50)
        custom_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        custom_entry.bind('<Return>', lambda e: self.execute_command(self.custom_cmd_var.get()))
        
        # 密码输入选项
        self.need_password_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(custom_frame, text="需要密码", variable=self.need_password_var).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(custom_frame, text="执行", command=lambda: self.execute_custom_command()).pack(side=tk.LEFT)

        # 输出区域
        output_frame = ttk.LabelFrame(self, text="输出", padding="5")
        output_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.output_text = scrolledtext.ScrolledText(output_frame, wrap=tk.WORD, font=("Courier", 10))
        self.output_text.pack(fill=tk.BOTH, expand=True)
        
        # 绑定 Ctrl+Z 快捷键到输出区域
        self.output_text.bind('<Control-z>', self.on_ctrl_z)
        self.output_text.bind('<Control-Z>', self.on_ctrl_z)

        # 状态栏
        self.status_var = tk.StringVar()
        self.status_var.set("就绪")
        status_bar = ttk.Label(self, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def on_ctrl_z(self, event=None):
         """处理 Ctrl+Z 快捷键，终止当前正在执行的命令"""
         if self.current_thread and self.current_thread.is_alive():
             # 尝试终止当前命令
             if self.current_thread.terminate_current_command():
                 self.output_queue.put(("output", "^Z"))
                 self.output_queue.put(("output", "[正在终止命令...]"))
             else:
                 self.output_queue.put(("output", "[没有正在运行的命令]"))
         else:
             self.output_queue.put(("output", "[未连接到服务器]"))
         return 'break'  # 阻止默认行为

    def refresh_command_buttons(self):
        """刷新自定义命令按钮显示"""
        # 清除现有按钮
        for widget in self.cmd_frame.winfo_children():
            widget.destroy()
        self.command_buttons.clear()
        
        # 创建新按钮
        for i, cmd_info in enumerate(self.custom_commands):
            name = cmd_info.get("name", "未命名")
            command = cmd_info.get("command", "")
            need_password = cmd_info.get("need_password", False)
            
            # 创建按钮
            btn = ttk.Button(
                self.cmd_frame, 
                text=name,
                command=lambda c=command, p=need_password: self.execute_command_with_password(c, p)
            )
            
            # 布局：每行4个按钮
            row = i // 4
            col = i % 4
            btn.grid(row=row, column=col, padx=3, pady=3, sticky="ew")
            self.command_buttons.append(btn)
        
        # 配置列权重
        for col in range(4):
            self.cmd_frame.columnconfigure(col, weight=1)

    def execute_command_with_password(self, command, need_password):
        """执行命令，支持密码输入"""
        if not command.strip():
            return
        if not self.current_thread or not self.current_thread.is_alive():
            messagebox.showwarning("警告", "请先连接服务器")
            return
        
        password_input = ""
        if need_password:
            # 弹出密码输入对话框
            password_input = simpledialog.askstring(
                "输入密码", 
                f"命令 '{command}' 需要密码:\n请输入 sudo 密码:",
                show='*'
            )
            if password_input is None:  # 用户取消
                return
        
        # 发送命令到线程
        cmd_data = {
            "command": command,
            "need_password": need_password,
            "password_input": password_input
        }
        self.current_thread.command_queue.put(cmd_data)

    def add_custom_command(self):
        """添加自定义命令"""
        dialog = tk.Toplevel(self)
        dialog.title("添加自定义命令")
        dialog.geometry("400x200")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        ttk.Label(dialog, text="按钮名称:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        name_entry = ttk.Entry(dialog, width=35)
        name_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="命令内容:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        cmd_entry = ttk.Entry(dialog, width=35)
        cmd_entry.grid(row=1, column=1, padx=5, pady=5)

        need_password_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(dialog, text="执行时需要输入密码 (sudo)", variable=need_password_var).grid(
            row=2, column=0, columnspan=2, padx=5, pady=5
        )

        def save():
            name = name_entry.get().strip()
            command = cmd_entry.get().strip()
            need_password = need_password_var.get()
            
            if not name or not command:
                messagebox.showerror("错误", "按钮名称和命令内容必须填写")
                return
            
            # 添加到列表
            new_cmd = {
                "name": name,
                "command": command,
                "need_password": need_password
            }
            self.custom_commands.append(new_cmd)
            save_custom_commands(self.custom_commands)
            
            # 刷新按钮显示
            self.refresh_command_buttons()
            dialog.destroy()
            messagebox.showinfo("成功", "自定义命令添加成功")

        ttk.Button(dialog, text="保存", command=save).grid(row=3, column=0, columnspan=2, pady=15)

    def edit_custom_command(self):
        """编辑自定义命令"""
        if not self.custom_commands:
            messagebox.showwarning("警告", "没有可编辑的命令")
            return
        
        # 选择要编辑的命令
        cmd_names = [cmd["name"] for cmd in self.custom_commands]
        
        dialog = tk.Toplevel(self)
        dialog.title("编辑自定义命令")
        dialog.geometry("450x250")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        ttk.Label(dialog, text="选择命令:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        cmd_var = tk.StringVar()
        cmd_combo = ttk.Combobox(dialog, textvariable=cmd_var, values=cmd_names, width=30, state="readonly")
        cmd_combo.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(dialog, text="按钮名称:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        name_entry = ttk.Entry(dialog, width=35)
        name_entry.grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="命令内容:").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        cmd_entry = ttk.Entry(dialog, width=35)
        cmd_entry.grid(row=2, column=1, padx=5, pady=5)

        need_password_var = tk.BooleanVar(value=False)
        password_check = ttk.Checkbutton(dialog, text="执行时需要输入密码 (sudo)", variable=need_password_var)
        password_check.grid(row=3, column=0, columnspan=2, padx=5, pady=5)

        def on_select(event=None):
            """选择命令后填充表单"""
            selected_name = cmd_var.get()
            for cmd in self.custom_commands:
                if cmd["name"] == selected_name:
                    name_entry.delete(0, tk.END)
                    name_entry.insert(0, cmd["name"])
                    cmd_entry.delete(0, tk.END)
                    cmd_entry.insert(0, cmd["command"])
                    need_password_var.set(cmd.get("need_password", False))
                    break
        
        cmd_combo.bind('<<ComboboxSelected>>', on_select)
        
        # 默认选择第一个
        if cmd_names:
            cmd_combo.set(cmd_names[0])
            on_select()

        def save():
            selected_name = cmd_var.get()
            new_name = name_entry.get().strip()
            new_command = cmd_entry.get().strip()
            new_need_password = need_password_var.get()
            
            if not new_name or not new_command:
                messagebox.showerror("错误", "按钮名称和命令内容必须填写")
                return
            
            # 查找并更新
            for cmd in self.custom_commands:
                if cmd["name"] == selected_name:
                    cmd["name"] = new_name
                    cmd["command"] = new_command
                    cmd["need_password"] = new_need_password
                    break
            
            save_custom_commands(self.custom_commands)
            self.refresh_command_buttons()
            dialog.destroy()
            messagebox.showinfo("成功", "自定义命令更新成功")

        ttk.Button(dialog, text="保存", command=save).grid(row=4, column=0, columnspan=2, pady=15)

    def delete_custom_command(self):
        """删除自定义命令"""
        if not self.custom_commands:
            messagebox.showwarning("警告", "没有可删除的命令")
            return
        
        # 选择要删除的命令
        cmd_names = [cmd["name"] for cmd in self.custom_commands]
        
        dialog = tk.Toplevel(self)
        dialog.title("删除自定义命令")
        dialog.geometry("300x150")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        ttk.Label(dialog, text="选择要删除的命令:").pack(pady=10)
        cmd_var = tk.StringVar()
        cmd_combo = ttk.Combobox(dialog, textvariable=cmd_var, values=cmd_names, width=25, state="readonly")
        cmd_combo.pack(pady=5)
        if cmd_names:
            cmd_combo.set(cmd_names[0])

        def delete():
            selected_name = cmd_var.get()
            if not selected_name:
                return
            
            # 确认删除
            if not messagebox.askyesno("确认", f"确定要删除命令 '{selected_name}' 吗？"):
                return
            
            # 查找并删除
            for i, cmd in enumerate(self.custom_commands):
                if cmd["name"] == selected_name:
                    del self.custom_commands[i]
                    break
            
            save_custom_commands(self.custom_commands)
            self.refresh_command_buttons()
            dialog.destroy()
            messagebox.showinfo("成功", "自定义命令已删除")

        ttk.Button(dialog, text="删除", command=delete).pack(pady=15)

    def execute_custom_command(self):
        """执行自定义输入的命令"""
        command = self.custom_cmd_var.get().strip()
        need_password = self.need_password_var.get()
        self.execute_command_with_password(command, need_password)

    def on_server_selected(self, event=None):
        """选择服务器后自动填充密码？这里可以显示提示"""
        pass

    def add_server(self):
        """添加服务器配置（弹出对话框）"""
        dialog = tk.Toplevel(self)
        dialog.title("添加服务器")
        dialog.geometry("300x250")
        dialog.resizable(False, False)

        ttk.Label(dialog, text="名称:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        name_entry = ttk.Entry(dialog, width=25)
        name_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="主机:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        host_entry = ttk.Entry(dialog, width=25)
        host_entry.grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="端口:").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        port_entry = ttk.Entry(dialog, width=25)
        port_entry.insert(0, "22")
        port_entry.grid(row=2, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="用户名:").grid(row=3, column=0, padx=5, pady=5, sticky="e")
        user_entry = ttk.Entry(dialog, width=25)
        user_entry.grid(row=3, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="密码:").grid(row=4, column=0, padx=5, pady=5, sticky="e")
        pass_entry = ttk.Entry(dialog, width=25, show="*")
        pass_entry.grid(row=4, column=1, padx=5, pady=5)

        def save():
            name = name_entry.get().strip()
            host = host_entry.get().strip()
            port = port_entry.get().strip()
            user = user_entry.get().strip()
            password = pass_entry.get().strip()
            if not name or not host or not port or not user:
                messagebox.showerror("错误", "所有字段必须填写")
                return
            try:
                port = int(port)
            except:
                messagebox.showerror("错误", "端口必须是数字")
                return
            # 添加到列表
            new_server = {
                "name": name,
                "host": host,
                "port": port,
                "username": user,
                "password": password  # 明文存储，仅用于演示；生产环境建议加密或使用密钥
            }
            self.servers.append(new_server)
            save_servers(self.servers)
            # 更新下拉框
            self.server_combo['values'] = [f"{s['name']} ({s['host']}:{s['port']})" for s in self.servers]
            dialog.destroy()
            messagebox.showinfo("成功", "服务器添加成功")

        ttk.Button(dialog, text="保存", command=save).grid(row=5, column=0, columnspan=2, pady=10)

    def delete_server(self):
        """删除当前选中的服务器"""
        if not self.server_var.get():
            return
        # 获取选中项的名称
        selected = self.server_var.get()
        name = selected.split(" (")[0]
        # 查找并删除
        for i, s in enumerate(self.servers):
            if s['name'] == name:
                del self.servers[i]
                break
        save_servers(self.servers)
        self.server_combo['values'] = [f"{s['name']} ({s['host']}:{s['port']})" for s in self.servers]
        self.server_var.set("")
        self.disconnect_server()
        messagebox.showinfo("成功", "服务器已删除")

    def connect_server(self):
        """连接选中的服务器"""
        if not self.server_var.get():
            messagebox.showwarning("警告", "请先选择服务器")
            return
        if self.current_thread and self.current_thread.is_alive():
            messagebox.showwarning("警告", "已有连接，请先断开")
            return

        # 获取选中服务器信息
        selected = self.server_var.get()
        name = selected.split(" (")[0]
        server = next((s for s in self.servers if s['name'] == name), None)
        if not server:
            return

        # 清空输出区域
        self.output_text.delete(1.0, tk.END)

        # 启动 SSH 线程
        self.output_queue = queue.Queue()
        self.current_thread = SSHThread(
            host=server['host'],
            port=server['port'],
            username=server['username'],
            password=server['password'],
            output_queue=self.output_queue
        )
        self.current_thread.start()
        self.status_var.set("正在连接...")

    def disconnect_server(self):
        """断开当前连接"""
        if self.current_thread and self.current_thread.is_alive():
            self.current_thread.stop()
            self.current_thread = None
        else:
            self.status_var.set("未连接")

    def execute_command(self, command):
        """将命令放入线程队列执行（兼容旧接口）"""
        self.execute_command_with_password(command, False)

    def poll_output_queue(self):
        """定期检查输出队列，更新 GUI"""
        try:
            while True:
                msg_type, content = self.output_queue.get_nowait()
                if msg_type == "output":
                    self.output_text.insert(tk.END, content + "\n")
                    self.output_text.see(tk.END)
                elif msg_type == "status":
                    self.status_var.set(content)
                elif msg_type == "error":
                    self.output_text.insert(tk.END, f"❌ {content}\n")
                    self.output_text.see(tk.END)
                    self.status_var.set("错误")
        except queue.Empty:
            pass
        finally:
            self.after(100, self.poll_output_queue)

# ==================== 启动应用 ====================
if __name__ == "__main__":
    app = App()
    app.mainloop()
