"""
受限 Python 沙箱测试用例
测试代码执行安全性
"""
import pytest
import tempfile
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.sandbox import RestrictedPythonSandbox


class TestSandboxBasic:
    """基础功能测试"""
    
    def test_execute_simple_math(self, tmp_path):
        """
        场景: 执行简单数学计算
        预期: 正常返回结果
        """
        sandbox = RestrictedPythonSandbox(user_id=999, working_dir=tmp_path)
        
        code = """
result = 2 + 2 * 10
print(f"计算结果: {result}")
"""
        result = sandbox.execute(code)
        
        assert result["success"] is True
        assert "计算结果: 22" in result["output"]
    
    def test_execute_pandas_analysis(self, tmp_path):
        """
        场景: 使用 pandas 分析 CSV
        预期: 正常执行并返回结果
        """
        # 创建测试 CSV
        csv_content = "name,age,score\nAlice,25,85\nBob,30,90\nCharlie,35,78"
        (tmp_path / "data.csv").write_text(csv_content)
        
        sandbox = RestrictedPythonSandbox(user_id=999, working_dir=tmp_path)
        
        code = """
import pandas as pd

df = pd.read_csv('data.csv')
print("数据概览:")
print(df.head())
print(f"\\n平均分: {df['score'].mean()}")
print(f"最高分: {df['score'].max()}")
"""
        result = sandbox.execute(code)
        
        assert result["success"] is True
        assert "平均分: 84.333" in result["output"] or "84.3" in result["output"]
        assert "Alice" in result["output"]
    
    def test_execute_numpy_operations(self, tmp_path):
        """
        场景: 使用 numpy 进行数值计算
        预期: 正常执行
        """
        sandbox = RestrictedPythonSandbox(user_id=999, working_dir=tmp_path)
        
        code = """
import numpy as np

arr = np.array([1, 2, 3, 4, 5])
print(f"数组: {arr}")
print(f"平均值: {np.mean(arr)}")
print(f"标准差: {np.std(arr)}")
"""
        result = sandbox.execute(code)
        
        assert result["success"] is True
        assert "平均值: 3.0" in result["output"]


class TestSandboxSecurity:
    """安全性测试 - 核心！"""
    
    def test_forbid_os_system(self, tmp_path):
        """
        场景: 尝试执行系统命令
        预期: 被拒绝
        """
        sandbox = RestrictedPythonSandbox(user_id=999, working_dir=tmp_path)
        
        dangerous_code = """
import os
os.system('ls -la /')
"""
        result = sandbox.execute(dangerous_code)
        
        assert result["success"] is False
        assert "禁止" in result["error"] or "不允许" in result["error"] or "Permission" in result["error"]
    
    def test_forbid_subprocess(self, tmp_path):
        """
        场景: 尝试使用 subprocess
        预期: 被拒绝
        """
        sandbox = RestrictedPythonSandbox(user_id=999, working_dir=tmp_path)
        
        code = """
import subprocess
subprocess.run(['ls', '-la'])
"""
        result = sandbox.execute(code)
        
        assert result["success"] is False
    
    def test_forbid_file_deletion(self, tmp_path):
        """
        场景: 尝试删除文件
        预期: 根据策略可能允许删除用户目录内文件，但禁止 rm -rf /
        """
        sandbox = RestrictedPythonSandbox(user_id=999, working_dir=tmp_path)
        
        # 测试删除系统文件
        code = """
import os
os.remove('/etc/passwd')
"""
        result = sandbox.execute(code)
        assert result["success"] is False
    
    def test_forbid_network_requests(self, tmp_path):
        """
        场景: 尝试网络请求
        预期: 被拒绝
        """
        sandbox = RestrictedPythonSandbox(user_id=999, working_dir=tmp_path)
        
        code = """
import requests
response = requests.get('https://example.com')
print(response.text)
"""
        result = sandbox.execute(code)
        
        assert result["success"] is False
    
    def test_forbid_urllib(self, tmp_path):
        """
        场景: 尝试使用 urllib
        预期: 被拒绝
        """
        sandbox = RestrictedPythonSandbox(user_id=999, working_dir=tmp_path)
        
        code = """
from urllib.request import urlopen
urlopen('https://example.com')
"""
        result = sandbox.execute(code)
        
        assert result["success"] is False
    
    def test_forbid_socket(self, tmp_path):
        """
        场景: 尝试使用 socket
        预期: 被拒绝
        """
        sandbox = RestrictedPythonSandbox(user_id=999, working_dir=tmp_path)
        
        code = """
import socket
s = socket.socket()
"""
        result = sandbox.execute(code)
        
        assert result["success"] is False
    
    def test_forbid_eval_exec(self, tmp_path):
        """
        场景: 尝试使用 eval/exec 动态执行
        预期: 被拒绝
        """
        sandbox = RestrictedPythonSandbox(user_id=999, working_dir=tmp_path)
        
        code = """
eval("__import__('os').system('ls')")
"""
        result = sandbox.execute(code)
        
        assert result["success"] is False
    
    def test_forbid_compile(self, tmp_path):
        """
        场景: 尝试使用 compile 动态编译
        预期: 被拒绝
        """
        sandbox = RestrictedPythonSandbox(user_id=999, working_dir=tmp_path)
        
        code = """
code = compile("import os; os.system('ls')", "<string>", "exec")
exec(code)
"""
        result = sandbox.execute(code)
        
        assert result["success"] is False
    
    def test_forbid_double_underscore(self, tmp_path):
        """
        场景: 尝试访问 __import__ 等魔术方法
        预期: 被拒绝
        """
        sandbox = RestrictedPythonSandbox(user_id=999, working_dir=tmp_path)
        
        code = """
__import__('os').system('ls')
"""
        result = sandbox.execute(code)
        
        assert result["success"] is False
    
    def test_file_access_outside_working_dir(self, tmp_path):
        """
        场景: 尝试读取工作目录外的文件
        预期: 被拒绝
        """
        sandbox = RestrictedPythonSandbox(user_id=999, working_dir=tmp_path)
        
        code = """
with open('/etc/passwd', 'r') as f:
    print(f.read())
"""
        result = sandbox.execute(code)
        
        assert result["success"] is False
        assert "权限" in result["error"] or "越权" in result["error"] or "Permission" in result["error"]
    
    def test_file_access_traversal(self, tmp_path):
        """
        场景: 尝试路径穿越攻击 ../../etc/passwd
        预期: 被拒绝
        """
        sandbox = RestrictedPythonSandbox(user_id=999, working_dir=tmp_path)
        
        # 先创建一个文件
        (tmp_path / "data.txt").write_text("test")
        
        code = """
with open('../../../etc/passwd', 'r') as f:
    print(f.read())
"""
        result = sandbox.execute(code)
        
        assert result["success"] is False
    
    def test_forbid_import_star(self, tmp_path):
        """
        场景: 尝试使用 from os import *
        预期: 被拒绝
        """
        sandbox = RestrictedPythonSandbox(user_id=999, working_dir=tmp_path)
        
        code = """
from os import *
system('ls')
"""
        result = sandbox.execute(code)
        
        assert result["success"] is False


class TestSandboxResourceLimits:
    """资源限制测试"""
    
    def test_timeout_infinite_loop(self, tmp_path):
        """
        场景: 死循环代码
        预期: 超时后被终止
        """
        sandbox = RestrictedPythonSandbox(user_id=999, working_dir=tmp_path, timeout=2)
        
        code = """
while True:
    pass
"""
        result = sandbox.execute(code)
        
        assert result["success"] is False
        assert "超时" in result["error"] or "timeout" in result["error"].lower()
    
    def test_timeout_long_computation(self, tmp_path):
        """
        场景: 耗时计算
        预期: 超时后被终止
        """
        sandbox = RestrictedPythonSandbox(user_id=999, working_dir=tmp_path, timeout=2)
        
        code = """
import time
time.sleep(10)
"""
        result = sandbox.execute(code)
        
        assert result["success"] is False
        assert "超时" in result["error"]
    
    def test_memory_limit(self, tmp_path):
        """
        场景: 创建超大列表耗尽内存
        预期: 被限制（如果实现了内存限制）
        
        注意：内存限制比较复杂，可能需要 ulimit 或容器实现
        这里先做基础测试
        """
        sandbox = RestrictedPythonSandbox(user_id=999, working_dir=tmp_path)
        
        code = """
# 尝试创建 1GB 列表
huge_list = [0] * (1024 * 1024 * 1024 // 8)
"""
        # 这个测试可能通过也可能失败，取决于实现
        result = sandbox.execute(code)
        # 不强制断言，记录即可
        print(f"内存限制测试结果: {result}")


class TestSandboxWorkspace:
    """工作目录测试"""
    
    def test_write_file_to_workspace(self, tmp_path):
        """
        场景: 在 workspace 中写入结果文件
        预期: 允许
        """
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        
        sandbox = RestrictedPythonSandbox(
            user_id=999,
            working_dir=workspace,
            output_dir=workspace
        )
        
        code = """
with open('result.txt', 'w') as f:
    f.write('分析完成')
print('文件写入成功')
"""
        result = sandbox.execute(code)
        
        assert result["success"] is True
        assert (workspace / "result.txt").exists()
        assert (workspace / "result.txt").read_text() == "分析完成"
    
    def test_read_own_file(self, tmp_path):
        """
        场景: 读取用户自己的文件
        预期: 允许
        """
        (tmp_path / "mydata.csv").write_text("a,b,c\n1,2,3")
        
        sandbox = RestrictedPythonSandbox(user_id=999, working_dir=tmp_path)
        
        code = """
with open('mydata.csv', 'r') as f:
    content = f.read()
print(content)
"""
        result = sandbox.execute(code)
        
        assert result["success"] is True
        assert "a,b,c" in result["output"]


class TestSandboxErrorHandling:
    """错误处理测试"""
    
    def test_syntax_error(self, tmp_path):
        """
        场景: 代码语法错误
        预期: 返回清晰的错误信息
        """
        sandbox = RestrictedPythonSandbox(user_id=999, working_dir=tmp_path)
        
        code = """
if True
    print("missing colon")
"""
        result = sandbox.execute(code)
        
        assert result["success"] is False
        assert "语法" in result["error"] or "SyntaxError" in result["error"]
    
    def test_runtime_error(self, tmp_path):
        """
        场景: 运行时错误（如除以零）
        预期: 返回错误信息
        """
        sandbox = RestrictedPythonSandbox(user_id=999, working_dir=tmp_path)
        
        code = """
result = 1 / 0
"""
        result = sandbox.execute(code)
        
        assert result["success"] is False
        assert "ZeroDivisionError" in result["error"]
    
    def test_missing_file_error(self, tmp_path):
        """
        场景: 读取不存在的文件
        预期: 返回 FileNotFoundError
        """
        sandbox = RestrictedPythonSandbox(user_id=999, working_dir=tmp_path)
        
        code = """
with open('nonexistent.csv', 'r') as f:
    print(f.read())
"""
        result = sandbox.execute(code)
        
        assert result["success"] is False
        assert "FileNotFoundError" in result["error"] or "No such file" in result["error"]
    
    def test_import_error(self, tmp_path):
        """
        场景: 尝试导入不允许的模块
        预期: 返回 ImportError
        """
        sandbox = RestrictedPythonSandbox(user_id=999, working_dir=tmp_path)
        
        code = """
import tensorflow as tf
"""
        result = sandbox.execute(code)
        
        assert result["success"] is False
        assert "ImportError" in result["error"] or "不允许" in result["error"]
