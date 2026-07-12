"""
受限 Python 沙箱
基于 AST 静态检查 + 子进程隔离的安全执行环境
"""
import ast
import os
import re
import site
import subprocess
import sys
import sysconfig
import tempfile
from pathlib import Path
from typing import Dict, Any, Set


class CodeSecurityChecker(ast.NodeVisitor):
    """AST 安全 checker - 检查危险操作"""
    
    FORBIDDEN_MODULES = {
        'os', 'subprocess', 'socket', 'requests', 'urllib',
        'http', 'ftplib', 'telnetlib', 'pickle', 'marshal', 'ctypes',
        'multiprocessing', 'threading', 'asyncio'
    }

    FORBIDDEN_FUNCTIONS = {'eval', 'exec', 'compile', '__import__'}

    def __init__(self):
        self.errors = []
        self.allowed_modules = {'pandas', 'numpy', 'matplotlib', 'json', 're',
                                'datetime', 'math', 'random', 'statistics', 'itertools', 'collections',
                                'sys', 'pathlib', 'typing', 'functools'}
    
    def visit_Import(self, node: ast.Import):
        """检查 import xxx"""
        for alias in node.names:
            module_name = alias.name.split('.')[0]
            if module_name in self.FORBIDDEN_MODULES:
                self.errors.append(f"禁止导入模块: {module_name}")
            elif module_name not in self.allowed_modules and module_name not in sys.builtin_module_names:
                # 检查是否在允许列表中
                pass  # 允许其他标准库模块，但不允许第三方未知模块
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node: ast.ImportFrom):
        """检查 from xxx import ..."""
        if node.module:
            module_name = node.module.split('.')[0]
            if module_name in self.FORBIDDEN_MODULES:
                self.errors.append(f"禁止从模块导入: {module_name}")
            # 检查是否是 import *
            for alias in node.names:
                if alias.name == '*':
                    self.errors.append(f"禁止使用 'from {module_name} import *'")
        self.generic_visit(node)
    
    def visit_Call(self, node: ast.Call):
        """检查函数调用"""
        # 检查 eval/exec/compile
        if isinstance(node.func, ast.Name):
            if node.func.id in self.FORBIDDEN_FUNCTIONS:
                self.errors.append(f"禁止使用函数: {node.func.id}")
        
        # 检查 __import__
        if isinstance(node.func, ast.Attribute):
            if node.func.attr == '__import__':
                self.errors.append("禁止使用 __import__")
        
        self.generic_visit(node)
    
    def visit_Attribute(self, node: ast.Attribute):
        """检查属性访问 - 捕获 __xxx__ 访问"""
        if isinstance(node.attr, str) and node.attr.startswith('__') and node.attr.endswith('__'):
            # 允许一些安全的魔术方法
            safe_magic = {'__name__', '__file__', '__doc__', '__package__'}
            if node.attr not in safe_magic:
                if 'import' in node.attr or 'builtins' in node.attr:
                    self.errors.append(f"禁止访问: {node.attr}")
        self.generic_visit(node)


class RestrictedPythonSandbox:
    """受限 Python 执行环境"""
    
    ALLOWED_MODULES: Set[str] = {
        'pandas', 'numpy', 'matplotlib', 'json', 're', 'datetime',
        'math', 'random', 'statistics', 'itertools', 'collections',
        'functools', 'decimal', 'fractions', 'typing', 'string',
        'hashlib', 'base64', 'csv', 'io', 'warnings', 'sys', 'pathlib'
    }
    
    FORBIDDEN_MODULES: Set[str] = {
        'os', 'subprocess', 'socket', 'requests', 'urllib',
        'http', 'ftplib', 'telnetlib', 'pickle', 'marshal', 'ctypes',
        'multiprocessing', 'threading', 'asyncio', 'concurrent'
    }
    
    def __init__(self, user_id: int = 0, working_dir: Path = None, timeout: int = 30, output_dir: Path = None):
        if working_dir is None:
            raise ValueError("working_dir is required")
        self.user_id = user_id
        self.working_dir = Path(working_dir)
        self.output_dir = Path(output_dir) if output_dir else None
        self.timeout = timeout
    
    def _check_code_safety(self, code: str) -> tuple[bool, str]:
        """使用 AST 检查代码安全性"""
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return False, f"语法错误: {e}"
        
        checker = CodeSecurityChecker()
        checker.visit(tree)
        
        if checker.errors:
            return False, f"安全检查失败: {'; '.join(checker.errors)}"
        
        # 额外检查字符串中的危险模式
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                # 检查字符串中是否包含危险代码模式
                if '__import__' in node.value:
                    return False, "安全检查失败: 检测到 __import__"
        
        return True, ""
    
    def _get_site_packages_paths(self) -> list:
        """发现当前 Python 环境的 site-packages 路径"""
        paths = []
        try:
            paths.extend(site.getsitepackages())
        except Exception:
            pass
        try:
            user_site = site.getusersitepackages()
            if user_site and user_site not in paths:
                paths.append(user_site)
        except Exception:
            pass
        for key in ('platlib', 'purelib'):
            try:
                p = sysconfig.get_path(key)
                if p and p not in paths:
                    paths.append(p)
            except Exception:
                pass
        return paths

    def _create_sandbox_script(self, user_code: str) -> str:
        """创建带沙箱限制的 Python 脚本"""
        working_dir_str = str(self.working_dir.resolve())
        output_dir_str = str(self.output_dir.resolve()) if self.output_dir else None

        # 动态发现 site-packages 路径，让第三方包能正常读取自身资源文件
        site_pkg_paths = self._get_site_packages_paths()
        site_pkg_literal = ",\n        ".join(repr(p) for p in site_pkg_paths)

        output_dir_literal = repr(output_dir_str) if output_dir_str else "None"

        sandbox_wrapper = f'''
# 沙箱环境设置
import sys
import builtins
import os as _os
import io as _io
from pathlib import Path as _Path

# 保存原始 open
_original_open = open

# 动态收集 Python 标准库路径（排除脚本自身所在目录，避免临时目录被误加入允许列表）
_SCRIPT_DIR = _os.path.dirname(_os.path.realpath(__file__))
_PYTHON_LIB_PATHS = []
for _p in sys.path:
    if _p and _os.path.isdir(_p):
        _rp = _os.path.realpath(_p)
        if _rp != _SCRIPT_DIR:
            _PYTHON_LIB_PATHS.append(_rp)

# 工作目录与输出目录
_WORKING_DIR = {repr(working_dir_str)}
_OUTPUT_DIR = {output_dir_literal}

# 允许的系统路径（主要用于 pandas/numpy/matplotlib 等库的正常运行）
_ALLOWED_SYSTEM_PATHS = [
    '/usr/share',    # 时区信息 / mime 数据库 / 系统共享数据
    '/System/Library',  # macOS 系统库
    '/usr/lib',      # Unix 系统库
    '/Library',      # macOS CLI Tools + Frameworks（含 Python.framework）
    '/opt',          # 可选软件包
    {site_pkg_literal},  # Python site-packages（第三方包资源文件）
] + _PYTHON_LIB_PATHS

def _is_allowed_path(path_str: str) -> bool:
    """检查路径是否允许读取"""
    # 空路径检查
    if not path_str:
        return False

    # 转换为绝对路径
    try:
        resolved = _os.path.normpath(_os.path.abspath(path_str))
    except Exception:
        return False

    def _is_under(base: str, target: str) -> bool:
        """严格判断 target 是否位于 base 目录下（避免前缀误判）"""
        if not base:
            return False
        try:
            return _os.path.commonpath([target, base]) == base
        except ValueError:
            return False

    # 检查是否在工作目录内
    if _is_under(_WORKING_DIR, resolved):
        return True

    # 检查是否在输出目录内（允许读取自己写入的结果）
    if _OUTPUT_DIR and _is_under(_OUTPUT_DIR, resolved):
        return True

    # 检查是否在允许的系统路径内
    for allowed in _ALLOWED_SYSTEM_PATHS:
        if _is_under(allowed, resolved):
            return True

    return False

def _safe_open(path, mode='r', *args, **kwargs):
    """限制文件访问：写操作只能在 output_dir，读操作限制在 working_dir / output_dir / 系统路径"""
    # 处理文件描述符
    if isinstance(path, int):
        return _original_open(path, mode, *args, **kwargs)

    p = _Path(path)

    # 写/追加/创建模式必须位于 output_dir
    if any(m in mode for m in 'wax+'):
        if _OUTPUT_DIR is None:
            raise PermissionError("Write operations are not allowed in this sandbox")

        out = _Path(_OUTPUT_DIR).resolve()

        # 将虚拟的 /sandbox_output 前缀映射到实际输出目录
        # 使用 /sandbox_output 而非 /output，避免与用户本地 /output 目录冲突
        path_str = str(p)
        if p.is_absolute() and (path_str == '/sandbox_output' or path_str.startswith('/sandbox_output/')):
            relative = path_str[len('/sandbox_output'):]
            if relative.startswith('/'):
                relative = relative[1:]
            p = out / relative

        resolved = p.resolve()
        if not resolved.is_relative_to(out):
            raise PermissionError(f"Cannot write outside output directory: {{path}}")
        return _original_open(resolved, mode, *args, **kwargs)

    # 读模式：相对路径基于工作目录解析
    path_str = str(path)
    if not _os.path.isabs(path_str):
        path_str = _os.path.join(_WORKING_DIR, path_str)

    resolved_str = _os.path.normpath(_os.path.abspath(path_str))
    if not _is_allowed_path(resolved_str):
        raise PermissionError(f"权限错误：无法访问工作目录外的文件")

    return _original_open(resolved_str, mode, *args, **kwargs)

# 替换 open 函数（pathlib / pandas 等通过 io.open 访问文件）
builtins.open = _safe_open
_io.open = _safe_open

# 重定向标准输入
class _RestrictedInput:
    def __call__(self, prompt=''):
        raise PermissionError("input() 函数被禁用")

builtins.input = _RestrictedInput()

# --- /sandbox_output 虚拟目录补丁 ---
# pandas/matplotlib 使用 pathlib.Path.is_dir() / exists() 检查路径，而非 os.path 函数。
# ba patch pathlib.Path 的方法，使 /sandbox_output 透明映射到实际 _OUTPUT_DIR。
if _OUTPUT_DIR:
    _os.makedirs(_OUTPUT_DIR, exist_ok=True)
    _OrigPath = _Path

    def _sandbox_path_is_dir(self):
        _raw = str(self)
        if _raw == '/sandbox_output':
            return True
        if _raw.startswith('/sandbox_output/'):
            _rel = _raw[len('/sandbox_output/'):]
            _real = _OrigPath(_OUTPUT_DIR) / _rel
            return _real.is_dir()
        return _OrigPath.is_dir(self)

    def _sandbox_path_exists(self):
        _raw = str(self)
        if _raw == '/sandbox_output' or _raw.startswith('/sandbox_output/'):
            _rel = _raw[len('/sandbox_output'):].lstrip('/')
            _real = _OrigPath(_OUTPUT_DIR) / _rel if _rel else _OrigPath(_OUTPUT_DIR)
            return _real.exists()
        return _OrigPath.exists(self)

    def _sandbox_path_mkdir(self, mode=0o777, parents=False, exist_ok=False):
        _raw = str(self)
        if _raw == '/sandbox_output' or _raw.startswith('/sandbox_output/'):
            return  # 虚拟目录，跳过
        return _OrigPath.mkdir(self, mode, parents, exist_ok)

    _Path.is_dir = _sandbox_path_is_dir
    _Path.exists = _sandbox_path_exists
    _Path.mkdir = _sandbox_path_mkdir

# 执行用户代码
{user_code}
'''
        return sandbox_wrapper
    
    def execute(self, code: str) -> Dict[str, Any]:
        """执行代码"""
        # 1. AST 安全检查
        is_safe, error_msg = self._check_code_safety(code)
        if not is_safe:
            return {
                "success": False,
                "error": error_msg,
                "error_type": "security",
                "code": code,
            }

        # 2. 创建沙箱脚本
        sandbox_code = self._create_sandbox_script(code)

        # 3. 在临时文件中执行
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(sandbox_code)
            temp_script = f.name

        try:
            # 使用 subprocess 执行，设置超时和资源限制
            env = os.environ.copy()
            # 保留 PYTHONPATH 以确保虚拟环境中的包可用

            result = subprocess.run(
                [sys.executable, temp_script],
                cwd=str(self.working_dir),
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env=env
            )

            output = result.stdout
            error = result.stderr

            # 过滤掉常见的警告信息
            filtered_error = self._filter_warnings(error)

            if result.returncode != 0:
                # 构建详细错误信息，包含代码和完整 stderr
                base_response = {
                    "success": False,
                    "code": code,
                    "stdout": output,
                    "stderr": error,
                }

                if "SyntaxError" in error:
                    return {**base_response,
                        "error_type": "syntax_error",
                        "error": f"语法错误:\n{error.strip()}"}
                elif "ZeroDivisionError" in error:
                    return {**base_response,
                        "error_type": "runtime_error",
                        "error": f"ZeroDivisionError: 除零错误\n{error.strip()}"}
                elif "FileNotFoundError" in error or "No such file" in error:
                    return {**base_response,
                        "error_type": "file_error",
                        "error": f"FileNotFoundError: {error.strip()}"}
                elif "PermissionError" in error or "权限" in error:
                    return {**base_response,
                        "error_type": "permission_error",
                        "error": f"权限错误：无法访问工作目录外的文件\n{error.strip()}"}
                elif "ModuleNotFoundError" in error:
                    match = re.search(r"No module named '([^']+)'", error)
                    module_name = match.group(1) if match else "未知模块"
                    return {**base_response,
                        "error_type": "module_not_found",
                        "error": f"ImportError: ModuleNotFoundError: 未找到模块 '{module_name}'，请先安装（如 pip install {module_name}）\n{error.strip()}"}
                elif "ImportError" in error:
                    match = re.search(r"No module named '([^']+)'", error)
                    module_name = match.group(1) if match else "未知模块"
                    return {**base_response,
                        "error_type": "import_error",
                        "error": f"ImportError: 导入模块 '{module_name}' 失败，请检查模块是否正确安装\n{error.strip()}"}
                else:
                    return {**base_response,
                        "error_type": "execution_error",
                        "error": filtered_error.strip() or error.strip() or "执行失败"}

            return {
                "success": True,
                "output": output,
                "code": code,
                "stderr": filtered_error if filtered_error else "",
            }
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "执行超时"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
        finally:
            # 清理临时文件
            try:
                os.unlink(temp_script)
            except:
                pass
    
    def _filter_warnings(self, stderr: str) -> str:
        """过滤警告信息，保留实际错误"""
        if not stderr:
            return ""
        
        lines = stderr.split('\n')
        filtered = []
        
        for line in lines:
            # 过滤常见的警告
            if any(w in line for w in [
                'DeprecationWarning', 'UserWarning', 'FutureWarning',
                'RuntimeWarning', 'warnings.warn', 'importlib'
            ]):
                continue
            filtered.append(line)
        
        return '\n'.join(filtered)
