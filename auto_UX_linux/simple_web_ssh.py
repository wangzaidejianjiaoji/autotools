#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
简单的 Web SSH 工具
让同事可以通过浏览器访问操作 SSH 命令
"""

import json
import threading
import queue
import time
import paramiko
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import os
from datetime import timedelta

# 配置文件路径
SERVERS_CONFIG_FILE = "servers.json"
COMMANDS_CONFIG_FILE = "commands.json"

# 加载配置
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

# SSH 线程类
class SSHThread(threading.Thread):
    def __init__(self, host, port, username, password, socketio, session_id):
        super().__init__()
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.socketio = socketio
        self.session_id = session_id
        self.command_queue = queue.Queue()
        self.client = None
        self.running = True
        self.current_channel = None
        self.current_command = None

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
            self.socketio.emit('ssh_status', {
                'status': 'connected',
                'message': f"✅ 已连接到 {self.username}@{self.host}:{self.port}"
            }, room=self.session_id)

            # 循环等待执行命令
            while self.running:
                try:
                    cmd_data = self.command_queue.get(timeout=1)
                except queue.Empty:
                    continue
                if cmd_data == "__EXIT__":
                    break
                if cmd_data == "__TERMINATE__":
                    if self.current_channel and not self.current_channel.exit_status_ready():
                        self.current_channel.close()
                        self.socketio.emit('ssh_output', {
                            'type': 'output',
                            'content': "^Z\n[命令已终止]"
                        }, room=self.session_id)
                    self.current_channel = None
                    self.current_command = None
                    continue
                
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
                    self.socketio.emit('ssh_output', {
                        'type': 'output',
                        'content': f"$ {cmd}"
                    }, room=self.session_id)
                    
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
                    output_lines = []
                    error_lines = []
                    command_terminated = False
                    
                    # 设置通道为非阻塞模式
                    stdout.channel.setblocking(False)
                    stderr.channel.setblocking(False)
                    
                    # 立即检查初始输出
                    if stdout.channel.recv_ready():
                        data = stdout.channel.recv(1024).decode('utf-8', errors='ignore')
                        if data:
                            output_lines.append(data)
                            self.socketio.emit('ssh_output', {
                                'type': 'output',
                                'content': data
                            }, room=self.session_id)
                    
                    if stderr.channel.recv_stderr_ready():
                        data = stderr.channel.recv_stderr(1024).decode('utf-8', errors='ignore')
                        if data:
                            error_lines.append(data)
                            self.socketio.emit('ssh_output', {
                                'type': 'output',
                                'content': data
                            }, room=self.session_id)
                    
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
                                self.socketio.emit('ssh_output', {
                                    'type': 'output',
                                    'content': "^Z\n[命令已终止]"
                                }, room=self.session_id)
                                break
                            else:
                                # 放回队列
                                self.command_queue.put(check_cmd)
                        except queue.Empty:
                            pass
                        
                        # 检查是否超时
                        if time.time() - start_time > 30:
                            self.socketio.emit('ssh_output', {
                                'type': 'output',
                                'content': "[命令执行超时，已终止]"
                            }, room=self.session_id)
                            stdout.channel.close()
                            break
                        
                        # 读取可用输出
                        if stdout.channel.recv_ready():
                            data = stdout.channel.recv(1024).decode('utf-8', errors='ignore')
                            if data:
                                output_lines.append(data)
                                self.socketio.emit('ssh_output', {
                                    'type': 'output',
                                    'content': data
                                }, room=self.session_id)
                        
                        if stderr.channel.recv_stderr_ready():
                            data = stderr.channel.recv_stderr(1024).decode('utf-8', errors='ignore')
                            if data:
                                error_lines.append(data)
                                self.socketio.emit('ssh_output', {
                                    'type': 'output',
                                    'content': data
                                }, room=self.session_id)
                        
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
                        self.socketio.emit('ssh_output', {
                            'type': 'output',
                            'content': remaining_out
                        }, room=self.session_id)
                    if remaining_err:
                        self.socketio.emit('ssh_output', {
                            'type': 'output',
                            'content': f"(stderr) {remaining_err}"
                        }, room=self.session_id)
                    
                except Exception as e:
                    self.socketio.emit('ssh_output', {
                        'type': 'error',
                        'content': f"命令执行失败: {str(e)}"
                    }, room=self.session_id)
        except Exception as e:
            self.socketio.emit('ssh_status', {
                'status': 'error',
                'message': f"连接失败: {str(e)}"
            }, room=self.session_id)
        finally:
            if self.client:
                self.client.close()
            self.socketio.emit('ssh_status', {
                'status': 'disconnected',
                'message': "🔌 已断开连接"
            }, room=self.session_id)

    def stop(self):
        """停止线程"""
        self.running = False
        self.command_queue.put("__EXIT__")

    def execute_command(self, cmd_data):
        """执行命令"""
        self.command_queue.put(cmd_data)

    def terminate_current_command(self):
        """终止当前正在执行的命令"""
        if self.current_channel and not self.current_channel.exit_status_ready():
            self.command_queue.put("__TERMINATE__")
            return True
        return False

# 创建 Flask 应用
app = Flask(__name__)
app.config['SECRET_KEY'] = 'ssh_tool_secret_key_12345'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
socketio = SocketIO(app, cors_allowed_origins="*")

# 全局变量：保存 SSH 线程
ssh_threads = {}

# 加载配置
servers = load_servers()
custom_commands = load_custom_commands()

@app.route('/')
def index():
    """主页"""
    return render_template('simple_index.html', 
                         servers=servers, 
                         custom_commands=custom_commands)

@app.route('/api/servers', methods=['GET'])
def get_servers():
    """获取服务器列表"""
    return jsonify(servers)

@app.route('/api/commands', methods=['GET'])
def get_commands():
    """获取自定义命令列表"""
    return jsonify(custom_commands)

@app.route('/api/servers', methods=['POST'])
def add_server():
    """添加服务器"""
    data = request.json
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    new_server = {
        "name": data.get("name"),
        "host": data.get("host"),
        "port": data.get("port"),
        "username": data.get("username"),
        "password": data.get("password")
    }
    
    if not all(new_server.values()):
        return jsonify({'error': 'All fields are required'}), 400
    
    servers.append(new_server)
    save_servers(servers)
    return jsonify({'success': True, 'server': new_server})

@app.route('/api/servers/<name>', methods=['DELETE'])
def delete_server(name):
    """删除服务器"""
    global servers
    servers = [s for s in servers if s['name'] != name]
    save_servers(servers)
    return jsonify({'success': True})

@app.route('/api/commands', methods=['POST'])
def add_command():
    """添加自定义命令"""
    data = request.json
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    new_cmd = {
        "name": data.get("name"),
        "command": data.get("command"),
        "need_password": data.get("need_password", False)
    }
    
    if not new_cmd['name'] or not new_cmd['command']:
        return jsonify({'error': 'Name and command are required'}), 400
    
    custom_commands.append(new_cmd)
    save_custom_commands(custom_commands)
    return jsonify({'success': True, 'command': new_cmd})

@app.route('/api/commands/<name>', methods=['DELETE'])
def delete_command(name):
    """删除自定义命令"""
    global custom_commands
    custom_commands = [c for c in custom_commands if c['name'] != name]
    save_custom_commands(custom_commands)
    return jsonify({'success': True})

@socketio.on('connect')
def handle_connect():
    """处理 WebSocket 连接"""
    session_id = request.sid
    print(f"客户端连接: {session_id}")

@socketio.on('disconnect')
def handle_disconnect():
    """处理 WebSocket 断开连接"""
    session_id = request.sid
    if session_id in ssh_threads:
        ssh_threads[session_id].stop()
        del ssh_threads[session_id]
    print(f"客户端断开: {session_id}")

@socketio.on('ssh_connect')
def handle_ssh_connect(data):
    """处理 SSH 连接请求"""
    session_id = request.sid
    
    # 断开现有连接
    if session_id in ssh_threads:
        ssh_threads[session_id].stop()
        del ssh_threads[session_id]
    
    # 获取服务器信息
    server_name = data.get('server')
    server = next((s for s in servers if s['name'] == server_name), None)
    if not server:
        emit('ssh_status', {
            'status': 'error',
            'message': '服务器不存在'
        })
        return
    
    # 创建并启动 SSH 线程
    ssh_thread = SSHThread(
        host=server['host'],
        port=server['port'],
        username=server['username'],
        password=server['password'],
        socketio=socketio,
        session_id=session_id
    )
    ssh_threads[session_id] = ssh_thread
    ssh_thread.start()

@socketio.on('ssh_disconnect')
def handle_ssh_disconnect():
    """处理 SSH 断开连接请求"""
    session_id = request.sid
    if session_id in ssh_threads:
        ssh_threads[session_id].stop()
        del ssh_threads[session_id]

@socketio.on('ssh_command')
def handle_ssh_command(data):
    """处理 SSH 命令执行请求"""
    session_id = request.sid
    if session_id not in ssh_threads:
        emit('ssh_status', {
            'status': 'error',
            'message': '未连接到服务器'
        })
        return
    
    ssh_threads[session_id].execute_command(data)

@socketio.on('ssh_terminate')
def handle_ssh_terminate():
    """处理 SSH 命令终止请求（Ctrl+Z）"""
    session_id = request.sid
    if session_id in ssh_threads:
        ssh_threads[session_id].terminate_current_command()

# 创建模板目录和文件
if not os.path.exists('templates'):
    os.makedirs('templates')

# 创建 simple_index.html 模板
with open('templates/simple_index.html', 'w', encoding='utf-8') as f:
    f.write('''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Web SSH 工具</title>
    <script src="https://cdn.jsdelivr.net/npm/jquery@3.6.0/dist/jquery.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/socket.io@4.5.0/dist/socket.io.min.js"></script>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <style>
        body {
            font-family: Arial, sans-serif;
            padding: 20px;
            background-color: #f8f9fa;
        }
        .container {
            max-width: 1200px;
        }
        .output-area {
            height: 400px;
            overflow-y: auto;
            background-color: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 4px;
            padding: 10px;
            font-family: 'Courier New', Courier, monospace;
            white-space: pre-wrap;
        }
        .command-buttons {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-bottom: 20px;
        }
        .server-card {
            margin-bottom: 20px;
        }
        .status-bar {
            margin-top: 10px;
            padding: 10px;
            border-radius: 4px;
        }
        .status-connected {
            background-color: #d4edda;
            border: 1px solid #c3e6cb;
            color: #155724;
        }
        .status-disconnected {
            background-color: #f8d7da;
            border: 1px solid #f5c6cb;
            color: #721c24;
        }
        .modal-body {
            max-height: 400px;
            overflow-y: auto;
        }
        .btn-primary {
            cursor: pointer;
        }
    </style>
</head>
<body>
    <div class="container mt-4">
        <h1 class="text-center mb-4">Web SSH 工具</h1>
        
        <!-- 服务器管理 -->
        <div class="card mb-4">
            <div class="card-header">
                <div class="d-flex justify-content-between align-items-center">
                    <h5>服务器管理</h5>
                    <button class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#addServerModal">
                        ➕ 添加服务器
                    </button>
                </div>
            </div>
            <div class="card-body">
                <div id="serverList" class="row">
                    <!-- 服务器卡片将通过 JavaScript 动态生成 -->
                </div>
            </div>
        </div>
        
        <!-- 自定义命令 -->
        <div class="card mb-4">
            <div class="card-header">
                <div class="d-flex justify-content-between align-items-center">
                    <h5>自定义命令</h5>
                    <div>
                        <button class="btn btn-primary btn-sm me-2" data-bs-toggle="modal" data-bs-target="#addCommandModal">
                            ➕ 添加命令
                        </button>
                    </div>
                </div>
            </div>
            <div class="card-body">
                <div id="commandButtons" class="command-buttons">
                    <!-- 命令按钮将通过 JavaScript 动态生成 -->
                </div>
            </div>
        </div>
        
        <!-- SSH 连接区域 -->
        <div class="card mb-4">
            <div class="card-header">
                <h5>SSH 终端</h5>
            </div>
            <div class="card-body">
                <!-- 状态条 -->
                <div id="statusBar" class="status-bar status-disconnected mb-3">
                    未连接到服务器
                </div>
                
                <!-- 输出区域 -->
                <div id="outputArea" class="output-area mb-3"></div>
                
                <!-- 命令输入 -->
                <div class="input-group">
                    <input type="text" id="commandInput" class="form-control" placeholder="输入命令...">
                    <div class="input-group-text">
                        <input type="checkbox" id="needPassword" aria-label="需要密码">
                    </div>
                    <button id="executeBtn" class="btn btn-primary">执行</button>
                    <button id="terminateBtn" class="btn btn-danger">终止 (Ctrl+Z)</button>
                </div>
            </div>
        </div>
    </div>
    
    <!-- 添加服务器模态框 -->
    <div class="modal fade" id="addServerModal" tabindex="-1" aria-labelledby="addServerModalLabel" aria-hidden="true">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title" id="addServerModalLabel">添加服务器</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                    <form id="addServerForm">
                        <div class="mb-3">
                            <label for="serverName" class="form-label">服务器名称</label>
                            <input type="text" class="form-control" id="serverName" required>
                        </div>
                        <div class="mb-3">
                            <label for="serverHost" class="form-label">主机地址</label>
                            <input type="text" class="form-control" id="serverHost" required>
                        </div>
                        <div class="mb-3">
                            <label for="serverPort" class="form-label">端口</label>
                            <input type="number" class="form-control" id="serverPort" value="22" required>
                        </div>
                        <div class="mb-3">
                            <label for="serverUser" class="form-label">用户名</label>
                            <input type="text" class="form-control" id="serverUser" required>
                        </div>
                        <div class="mb-3">
                            <label for="serverPassword" class="form-label">密码</label>
                            <input type="password" class="form-control" id="serverPassword" required>
                        </div>
                    </form>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                    <button type="button" class="btn btn-primary" id="saveServerBtn">保存</button>
                </div>
            </div>
        </div>
    </div>
    
    <!-- 添加命令模态框 -->
    <div class="modal fade" id="addCommandModal" tabindex="-1" aria-labelledby="addCommandModalLabel" aria-hidden="true">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title" id="addCommandModalLabel">添加自定义命令</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                    <form id="addCommandForm">
                        <div class="mb-3">
                            <label for="commandName" class="form-label">按钮名称</label>
                            <input type="text" class="form-control" id="commandName" required>
                        </div>
                        <div class="mb-3">
                            <label for="commandContent" class="form-label">命令内容</label>
                            <input type="text" class="form-control" id="commandContent" required>
                        </div>
                        <div class="mb-3 form-check">
                            <input type="checkbox" class="form-check-input" id="commandNeedPassword">
                            <label class="form-check-label" for="commandNeedPassword">需要密码 (sudo)</label>
                        </div>
                    </form>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                    <button type="button" class="btn btn-primary" id="saveCommandBtn">保存</button>
                </div>
            </div>
        </div>
    </div>
    
    <!-- 密码输入模态框 -->
    <div class="modal fade" id="passwordModal" tabindex="-1" aria-labelledby="passwordModalLabel" aria-hidden="true">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title" id="passwordModalLabel">输入密码</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                    <p id="passwordPrompt">命令需要密码</p>
                    <input type="password" id="passwordInput" class="form-control" required>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                    <button type="button" class="btn btn-primary" id="submitPasswordBtn">确定</button>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        // WebSocket 连接
        const socket = io();
        
        // 当前命令信息
        let currentCommand = null;
        let currentCommandNeedPassword = false;
        
        // 加载服务器列表
        function loadServers() {
            fetch('/api/servers')
                .then(response => response.json())
                .then(data => {
                    const serverList = document.getElementById('serverList');
                    serverList.innerHTML = '';
                    
                    data.forEach(server => {
                        const serverCard = document.createElement('div');
                        serverCard.className = 'col-md-4 mb-3';
                        serverCard.innerHTML = `
                            <div class="card server-card">
                                <div class="card-body">
                                    <h5 class="card-title">${server.name}</h5>
                                    <p class="card-text">
                                        <strong>主机:</strong> ${server.host}<br>
                                        <strong>端口:</strong> ${server.port}<br>
                                        <strong>用户名:</strong> ${server.username}
                                    </p>
                                    <div class="d-flex gap-2">
                                        <button class="btn btn-primary btn-sm connect-btn" data-server="${server.name}">
                                            连接
                                        </button>
                                        <button class="btn btn-danger btn-sm delete-server-btn" data-server="${server.name}">
                                            删除
                                        </button>
                                    </div>
                                </div>
                            </div>
                        `;
                        serverList.appendChild(serverCard);
                    });
                    
                    // 绑定连接按钮事件
                    document.querySelectorAll('.connect-btn').forEach(btn => {
                        btn.addEventListener('click', function() {
                            const server = this.getAttribute('data-server');
                            connectToServer(server);
                        });
                    });
                    
                    // 绑定删除按钮事件
                    document.querySelectorAll('.delete-server-btn').forEach(btn => {
                        btn.addEventListener('click', function() {
                            const server = this.getAttribute('data-server');
                            if (confirm(`确定要删除服务器 ${server} 吗？`)) {
                                deleteServer(server);
                            }
                        });
                    });
                });
        }
        
        // 加载自定义命令
        function loadCommands() {
            fetch('/api/commands')
                .then(response => response.json())
                .then(data => {
                    const commandButtons = document.getElementById('commandButtons');
                    commandButtons.innerHTML = '';
                    
                    data.forEach(cmd => {
                        const btn = document.createElement('button');
                        btn.className = 'btn btn-outline-secondary';
                        btn.textContent = cmd.name;
                        btn.addEventListener('click', function() {
                            executeCommand(cmd.command, cmd.need_password);
                        });
                        commandButtons.appendChild(btn);
                    });
                });
        }
        
        // 连接到服务器
        function connectToServer(server) {
            socket.emit('ssh_connect', { server: server });
        }
        
        // 断开连接
        function disconnectFromServer() {
            socket.emit('ssh_disconnect');
        }
        
        // 执行命令
        function executeCommand(command, needPassword = false) {
            if (needPassword) {
                // 保存命令信息
                currentCommand = command;
                currentCommandNeedPassword = needPassword;
                
                // 显示密码输入框
                document.getElementById('passwordPrompt').textContent = `命令 "${command}" 需要密码`;
                const passwordModal = new bootstrap.Modal(document.getElementById('passwordModal'));
                passwordModal.show();
            } else {
                socket.emit('ssh_command', {
                    command: command,
                    need_password: needPassword
                });
            }
        }
        
        // 终止命令
        function terminateCommand() {
            socket.emit('ssh_terminate');
        }
        
        // 删除服务器
        function deleteServer(server) {
            fetch(`/api/servers/${server}`, {
                method: 'DELETE'
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    loadServers();
                }
            });
        }
        
        // 删除命令
        function deleteCommand(name) {
            fetch(`/api/commands/${name}`, {
                method: 'DELETE'
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    loadCommands();
                }
            });
        }
        
        // WebSocket 事件处理
        socket.on('ssh_status', function(data) {
            const statusBar = document.getElementById('statusBar');
            statusBar.textContent = data.message;
            
            if (data.status === 'connected') {
                statusBar.className = 'status-bar status-connected mb-3';
            } else {
                statusBar.className = 'status-bar status-disconnected mb-3';
            }
        });
        
        socket.on('ssh_output', function(data) {
            const outputArea = document.getElementById('outputArea');
            outputArea.innerHTML += data.content + '\n';
            outputArea.scrollTop = outputArea.scrollHeight;
        });
        
        // 绑定事件
        window.onload = function() {
            console.log('页面加载完成');
            
            // 加载服务器和命令
            loadServers();
            loadCommands();
            
            // 保存服务器按钮
            const saveServerBtn = document.getElementById('saveServerBtn');
            console.log('保存服务器按钮:', saveServerBtn);
            
            if (saveServerBtn) {
                saveServerBtn.addEventListener('click', function() {
                    console.log('保存服务器按钮被点击');
                    const name = document.getElementById('serverName').value;
                    const host = document.getElementById('serverHost').value;
                    const port = document.getElementById('serverPort').value;
                    const username = document.getElementById('serverUser').value;
                    const password = document.getElementById('serverPassword').value;
                    
                    if (name && host && port && username && password) {
                        console.log('发送请求添加服务器');
                        fetch('/api/servers', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json'
                            },
                            body: JSON.stringify({
                                name: name,
                                host: host,
                                port: parseInt(port),
                                username: username,
                                password: password
                            })
                        })
                        .then(response => response.json())
                        .then(data => {
                            console.log('响应数据:', data);
                            if (data.success) {
                                loadServers();
                                // 关闭模态框
                                const addServerModal = document.getElementById('addServerModal');
                                const modal = bootstrap.Modal.getInstance(addServerModal) || new bootstrap.Modal(addServerModal);
                                modal.hide();
                                // 清空表单
                                document.getElementById('addServerForm').reset();
                                alert('服务器添加成功！');
                            } else {
                                alert('添加失败: ' + (data.error || '未知错误'));
                            }
                        })
                        .catch(error => {
                            console.error('添加服务器失败:', error);
                            alert('添加服务器失败，请检查控制台');
                        });
                    } else {
                        alert('请填写所有必填字段');
                    }
                });
            }
            
            // 保存命令按钮
            const saveCommandBtn = document.getElementById('saveCommandBtn');
            console.log('保存命令按钮:', saveCommandBtn);
            
            if (saveCommandBtn) {
                saveCommandBtn.addEventListener('click', function() {
                    console.log('保存命令按钮被点击');
                    const name = document.getElementById('commandName').value;
                    const content = document.getElementById('commandContent').value;
                    const needPassword = document.getElementById('commandNeedPassword').checked;
                    
                    if (name && content) {
                        console.log('发送请求添加命令');
                        fetch('/api/commands', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json'
                            },
                            body: JSON.stringify({
                                name: name,
                                command: content,
                                need_password: needPassword
                            })
                        })
                        .then(response => response.json())
                        .then(data => {
                            console.log('响应数据:', data);
                            if (data.success) {
                                loadCommands();
                                // 关闭模态框
                                const addCommandModal = document.getElementById('addCommandModal');
                                const modal = bootstrap.Modal.getInstance(addCommandModal) || new bootstrap.Modal(addCommandModal);
                                modal.hide();
                                // 清空表单
                                document.getElementById('addCommandForm').reset();
                                alert('命令添加成功！');
                            } else {
                                alert('添加失败: ' + (data.error || '未知错误'));
                            }
                        })
                        .catch(error => {
                            console.error('添加命令失败:', error);
                            alert('添加命令失败，请检查控制台');
                        });
                    } else {
                        alert('请填写所有必填字段');
                    }
                });
            }
            
            // 执行按钮
            const executeBtn = document.getElementById('executeBtn');
            if (executeBtn) {
                executeBtn.addEventListener('click', function() {
                    const command = document.getElementById('commandInput').value;
                    const needPassword = document.getElementById('needPassword').checked;
                    if (command) {
                        executeCommand(command, needPassword);
                        document.getElementById('commandInput').value = '';
                    }
                });
            }
            
            // 终止按钮
            const terminateBtn = document.getElementById('terminateBtn');
            if (terminateBtn) {
                terminateBtn.addEventListener('click', terminateCommand);
            }
            
            // 命令输入框回车
            const commandInput = document.getElementById('commandInput');
            if (commandInput) {
                commandInput.addEventListener('keypress', function(e) {
                    if (e.key === 'Enter') {
                        executeBtn.click();
                    }
                });
            }
            
            // Ctrl+Z 终止命令
            document.addEventListener('keydown', function(e) {
                if (e.ctrlKey && (e.key === 'z' || e.key === 'Z')) {
                    e.preventDefault();
                    terminateCommand();
                }
            });
            
            // 提交密码
            const submitPasswordBtn = document.getElementById('submitPasswordBtn');
            if (submitPasswordBtn) {
                submitPasswordBtn.addEventListener('click', function() {
                    const password = document.getElementById('passwordInput').value;
                    if (password) {
                        socket.emit('ssh_command', {
                            command: currentCommand,
                            need_password: currentCommandNeedPassword,
                            password_input: password
                        });
                        
                        // 关闭模态框
                        const passwordModal = document.getElementById('passwordModal');
                        const modal = bootstrap.Modal.getInstance(passwordModal) || new bootstrap.Modal(passwordModal);
                        modal.hide();
                        
                        // 清空密码输入
                        document.getElementById('passwordInput').value = '';
                        
                        // 重置当前命令
                        currentCommand = null;
                        currentCommandNeedPassword = false;
                    }
                });
            }
            
            // 密码输入框回车
            const passwordInput = document.getElementById('passwordInput');
            if (passwordInput) {
                passwordInput.addEventListener('keypress', function(e) {
                    if (e.key === 'Enter') {
                        submitPasswordBtn.click();
                    }
                });
            }
        };
    </script>
</body>
</html>
''')

# 启动应用
if __name__ == '__main__':
    print("Web SSH 工具启动中...")
    print("请安装必要的依赖:")
    print("pip install flask flask-socketio eventlet")
    print("\n启动命令:")
    print("python simple_web_ssh.py")
    print("\n访问地址:")
    print("http://localhost:5000")
    print("\n如果要让同事访问，请使用您的 IP 地址:")
    print("例如: http://192.168.1.100:5000")
    
    # 启动服务器
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
