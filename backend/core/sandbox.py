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


def _is_frozen() -> bool:
    """是否运行在 PyInstaller 打包环境（单独抽出来便于测试 patch）。"""
    return getattr(sys, "frozen", False)


def _sandbox_child_entry(conn, working_dir: str, sandbox_code: str) -> None:
    """multiprocessing spawn 子进程入口：在受限环境下执行沙箱脚本并回传结果。

    必须是模块级函数（spawn 通过 pickle 按引用序列化，子进程按
    `core.sandbox._sandbox_child_entry` 导入它）。
    """
    import contextlib
    import io
    import os
    import tempfile
    import traceback

    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    returncode = 0
    temp_script = None
    try:
        os.chdir(working_dir)
        # 沙箱是无头环境：强制 matplotlib 使用 Agg 后端，并把配置/字体缓存
        # 指到工作目录下的固定位置（避免尝试创建 ~/.matplotlib，且字体缓存可复用）。
        # 注意必须直接赋值：PyInstaller 的 matplotlib runtime hook 会把 MPLCONFIGDIR
        # 指向一次性临时目录（每次启动重建字体缓存，且写操作会被 _safe_open 拦截），
        # setdefault 无法覆盖它。
        os.environ["MPLBACKEND"] = "Agg"
        _mpl_config = os.path.join(working_dir, ".mplconfig")
        os.makedirs(_mpl_config, exist_ok=True)
        os.environ["MPLCONFIGDIR"] = _mpl_config
        # 写到临时文件，让 traceback 与 __file__ 指向真实路径（与 subprocess 模式行为一致）
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(sandbox_code)
            temp_script = f.name
        with open(temp_script, encoding="utf-8") as f:
            source = f.read()
        globals_dict = {"__name__": "__main__", "__file__": temp_script}
        with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
            try:
                exec(compile(source, temp_script, "exec"), globals_dict)
            except SystemExit:
                pass
            except BaseException:  # noqa: BLE001 - 沙箱必须捕获用户代码的一切异常
                returncode = 1
                traceback.print_exc()
    except BaseException:  # noqa: BLE001
        returncode = 1
        stderr_buf.write(traceback.format_exc())
    finally:
        if temp_script:
            try:
                os.unlink(temp_script)
            except OSError:
                pass
        try:
            conn.send({
                "returncode": returncode,
                "stdout": stdout_buf.getvalue(),
                "stderr": stderr_buf.getvalue(),
            })
        except Exception:
            pass
        conn.close()


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

    def _get_python_executable(self) -> str:
        """获取用于执行沙箱代码的 Python 解释器。

        PyInstaller onedir 模式下，sys.executable 是外层 bootloader，
        需要定位 _MEIPASS 内的 Python 解释器才能用脚本参数启动。
        """
        if not getattr(sys, "frozen", False):
            return sys.executable

        meipass = Path(getattr(sys, "_MEIPASS"))
        if sys.platform == "win32":
            candidates = [
                meipass / "python.exe",
                meipass / "python3.exe",
            ]
        else:
            candidates = [
                meipass / "python",
                meipass / "python3",
                meipass / "Python",
            ]
        for c in candidates:
            if c.exists():
                return str(c)
        # 兜底：使用当前可执行文件（可能不支持 -c，但适用于部分 PyInstaller onefile 场景）
        return sys.executable

    def _create_sandbox_script(self, user_code: str) -> str:
        """创建带沙箱限制的 Python 脚本"""
        working_dir_str = str(self.working_dir.resolve())
        output_dir_str = str(self.output_dir.resolve()) if self.output_dir else None

        # 动态发现 site-packages 路径，让第三方包能正常读取自身资源文件
        site_pkg_paths = self._get_site_packages_paths()
        site_pkg_literal = ",\n        ".join(repr(p) for p in site_pkg_paths)

        output_dir_literal = repr(output_dir_str) if output_dir_str else "None"

        # 仅在用户代码用到 matplotlib 时注入中文字体设置，避免白白付出 import 开销
        if "matplotlib" in user_code:
            cjk_font_setup = (
                "try:\n"
                "    import matplotlib as _mpl\n"
                "    from matplotlib import font_manager as _fm\n"
                "    _CJK_CANDIDATES = [\n"
                "        'PingFang SC', 'Hiragino Sans GB', 'Arial Unicode MS',\n"
                "        'Microsoft YaHei', 'SimHei', 'Noto Sans CJK SC',\n"
                "    ]\n"
                "    _available = {f.name for f in _fm.fontManager.ttflist}\n"
                "    _cjk = [n for n in _CJK_CANDIDATES if n in _available]\n"
                "    if _cjk:\n"
                "        _mpl.rcParams['font.sans-serif'] = _cjk + ['DejaVu Sans']\n"
                "        # 兜底：用户代码硬编码不存在的中文字体（如 SimHei）时，\n"
                "        # 把可用的 CJK 字体放到字体链首位，避免中文回退成 DejaVu 方块。\n"
                "        # patch _find_fonts_by_props（文本渲染实际走的解析入口）。\n"
                "        _orig_find_fonts = _fm.FontManager._find_fonts_by_props\n"
                "        def _cjk_find_fonts(self, prop, *args, **kwargs):\n"
                "            paths = _orig_find_fonts(self, prop, *args, **kwargs)\n"
                "            try:\n"
                "                first = self.findfont(_cjk[0], fallback_to_default=False)\n"
                "                first_path = str(getattr(first, 'path', first))\n"
                "                rest = [p for p in paths\n"
                "                        if str(getattr(p, 'path', p)) != first_path]\n"
                "                return [first] + rest\n"
                "            except Exception:\n"
                "                return paths\n"
                "        _fm.FontManager._find_fonts_by_props = _cjk_find_fonts\n"
                "    _mpl.rcParams['axes.unicode_minus'] = False\n"
                "except Exception:\n"
                "    pass"
            )
        else:
            cjk_font_setup = "pass  # 未使用 matplotlib"

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
# matplotlib 配置/字体缓存目录，写入放行
_MPL_CONFIG_DIR = _os.path.join(_WORKING_DIR, '.mplconfig')
# 沙箱是无头环境：强制 Agg 后端；配置/字体缓存指到工作目录下，避免触碰 ~/.matplotlib
_os.makedirs(_MPL_CONFIG_DIR, exist_ok=True)
# 直接赋值：覆盖 PyInstaller matplotlib runtime hook 设置的一次性临时目录
_os.environ['MPLBACKEND'] = 'Agg'
_os.environ['MPLCONFIGDIR'] = _MPL_CONFIG_DIR

# 允许的系统路径（主要用于 pandas/numpy/matplotlib 等库的正常运行）
_ALLOWED_SYSTEM_PATHS = [
    '/usr/share',    # 时区信息 / mime 数据库 / 系统共享数据
    '/System/Library',  # macOS 系统库
    '/usr/lib',      # Unix 系统库
    '/Library',      # macOS CLI Tools + Frameworks（含 Python.framework）
    '/opt',          # 可选软件包
    '/etc/apache2',  # openpyxl 初始化 mimetypes 需要读取 /etc/apache2/mime.types
    {site_pkg_literal},  # Python site-packages（第三方包资源文件）
] + _PYTHON_LIB_PATHS

# matplotlib 可能选用用户字体目录下的字体（如 ~/Library/Fonts 的 CJK 字体），放行只读
for _fonts_dir in (
    _os.path.expanduser('~/Library/Fonts'),     # macOS 用户字体
    _os.path.expanduser('~/.fonts'),            # Linux 用户字体
    _os.path.expanduser('~/.local/share/fonts'),
    '/usr/local/share/fonts',
):
    if _os.path.isdir(_fonts_dir):
        _ALLOWED_SYSTEM_PATHS.append(_os.path.realpath(_fonts_dir))

# PyInstaller 冻结环境：PYZ 归档内嵌在可执行文件中，冻结导入器会 open
# sys.executable / _MEIPASS 下的文件，需要放行只读访问（写仍被限制在 output_dir）
if getattr(sys, 'frozen', False):
    _app_bin_dir = _os.path.dirname(_os.path.realpath(sys.executable))
    _ALLOWED_SYSTEM_PATHS.append(_app_bin_dir)
    # macOS .app：matplotlib 字体等 data 文件在 Contents/Resources 下，
    # 与可执行文件（Contents/MacOS）、_MEIPASS（Contents/Frameworks）不同级，
    # 放行整个 Contents 目录的只读访问（均为应用自身只读资源）
    _app_contents_dir = _os.path.realpath(_os.path.join(_app_bin_dir, '..'))
    if _os.path.basename(_app_contents_dir) == 'Contents':
        _ALLOWED_SYSTEM_PATHS.append(_app_contents_dir)
    _meipass = getattr(sys, '_MEIPASS', None)
    if _meipass and _os.path.isdir(_meipass):
        _ALLOWED_SYSTEM_PATHS.append(_os.path.realpath(_meipass))

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
        if resolved.is_relative_to(out) or resolved.is_relative_to(_Path(_MPL_CONFIG_DIR)):
            return _original_open(resolved, mode, *args, **kwargs)
        raise PermissionError(
            f"Cannot write outside output directory: {{path}}. "
            "禁止写入工作目录或相对路径；所有输出文件（图表/CSV/报告）必须保存到 "
            "/sandbox_output/ 前缀下，例如 savefig('/sandbox_output/chart.png')。"
        )

    # 读模式：相对路径基于工作目录解析
    path_str = str(path)
    if not _os.path.isabs(path_str):
        path_str = _os.path.join(_WORKING_DIR, path_str)

    resolved_str = _os.path.normpath(_os.path.abspath(path_str))
    if not _is_allowed_path(resolved_str):
        raise PermissionError(f"权限错误：无法访问工作目录外的文件: {{path}}")

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
    # 必须在补丁之前捕获原始方法，否则 _OrigPath.mkdir 指向补丁函数自身导致无限递归
    _orig_is_dir = _Path.is_dir
    _orig_exists = _Path.exists
    _orig_mkdir = _Path.mkdir

    def _sandbox_path_is_dir(self):
        _raw = str(self)
        if _raw == '/sandbox_output':
            return True
        if _raw.startswith('/sandbox_output/'):
            _rel = _raw[len('/sandbox_output/'):]
            _real = _OrigPath(_OUTPUT_DIR) / _rel
            return _orig_is_dir(_real)
        return _orig_is_dir(self)

    def _sandbox_path_exists(self):
        _raw = str(self)
        if _raw == '/sandbox_output' or _raw.startswith('/sandbox_output/'):
            _rel = _raw[len('/sandbox_output'):].lstrip('/')
            _real = _OrigPath(_OUTPUT_DIR) / _rel if _rel else _OrigPath(_OUTPUT_DIR)
            return _orig_exists(_real)
        return _orig_exists(self)

    def _sandbox_path_mkdir(self, mode=0o777, parents=False, exist_ok=False):
        _raw = str(self)
        if _raw == '/sandbox_output' or _raw.startswith('/sandbox_output/'):
            return  # 虚拟目录，跳过
        return _orig_mkdir(self, mode, parents, exist_ok)

    _Path.is_dir = _sandbox_path_is_dir
    _Path.exists = _sandbox_path_exists
    _Path.mkdir = _sandbox_path_mkdir

# matplotlib 中文字体：打包环境默认 DejaVu Sans 无 CJK 字形，中文标题会渲染成方块。
# 优先使用系统中文字体（macOS PingFang / 冬青黑体，Windows SimHei 等），找不到则静默回退。
{cjk_font_setup}

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

        # 3. 执行：PyInstaller 冻结环境下包内没有独立 Python 解释器，
        # subprocess 调 sys.executable 会把整个应用再启动一遍，
        # 必须改用 multiprocessing spawn 子进程（能复用打包内的 pandas/matplotlib）。
        if _is_frozen():
            return self._execute_frozen(code, sandbox_code)
        return self._execute_subprocess(code, sandbox_code)

    def _execute_subprocess(self, code: str, sandbox_code: str) -> Dict[str, Any]:
        """开发环境：独立 Python 解释器 + 临时脚本执行。"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(sandbox_code)
            temp_script = f.name

        try:
            env = os.environ.copy()
            # 保留 PYTHONPATH 以确保虚拟环境中的包可用

            python_exe = self._get_python_executable()
            result = subprocess.run(
                [python_exe, temp_script],
                cwd=str(self.working_dir),
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env=env
            )
            return self._build_result(code, result.returncode, result.stdout, result.stderr)

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

    def _execute_frozen(self, code: str, sandbox_code: str) -> Dict[str, Any]:
        """打包环境：multiprocessing spawn 子进程内执行沙箱脚本。

        子进程继承打包内的全部依赖（pandas/numpy/matplotlib），
        受限 open / 输入禁用等沙箱约束由脚本自身在子进程内生效。
        """
        import multiprocessing as mp

        ctx = mp.get_context("spawn")
        parent_conn, child_conn = ctx.Pipe(duplex=False)
        proc = ctx.Process(
            target=_sandbox_child_entry,
            args=(child_conn, str(self.working_dir), sandbox_code),
            daemon=True,
        )
        try:
            proc.start()
            proc.join(self.timeout)
            if proc.is_alive():
                proc.terminate()
                proc.join(5)
                return {
                    "success": False,
                    "error": "执行超时"
                }
            if parent_conn.poll():
                payload = parent_conn.recv()
            else:
                payload = {
                    "returncode": 1,
                    "stdout": "",
                    "stderr": f"沙箱子进程异常退出（exitcode={proc.exitcode}）",
                }
            return self._build_result(
                code, payload["returncode"], payload["stdout"], payload["stderr"]
            )
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
        finally:
            try:
                parent_conn.close()
            except Exception:
                pass

    def _build_result(self, code: str, returncode: int, output: str, error: str) -> Dict[str, Any]:
        """把子进程（subprocess / multiprocessing）的退出码与输出转换为统一结果。"""
        # 过滤掉常见的警告信息
        filtered_error = self._filter_warnings(error)

        if returncode != 0:
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
