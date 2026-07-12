"""
工具系统测试用例
测试 glob, read, grep, stat, exec 五大工具
"""
import pytest
import tempfile
import os
import sys
from pathlib import Path

# 添加项目路径，避免导入冲突
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.tools import GlobTool, ReadTool, GrepTool, StatTool, ExecTool


class TestGlobTool:
    """测试 glob 工具 - 文件发现"""
    
    def test_glob_all_csv_files(self, tmp_path):
        """
        场景: 用户目录下有多个 CSV 文件
        预期: glob("*.csv") 返回所有 CSV 文件名
        """
        # 准备测试数据
        (tmp_path / "sales.csv").write_text("data")
        (tmp_path / "products.csv").write_text("data")
        (tmp_path / "report.xlsx").write_text("data")  # 非 CSV
        
        # 执行
        tool = GlobTool(working_dir=tmp_path)
        result = tool.execute(pattern="*.csv")
        
        # 验证
        assert result["success"] is True
        assert "sales.csv" in result["files"]
        assert "products.csv" in result["files"]
        assert "report.xlsx" not in result["files"]
    
    def test_glob_with_prefix(self, tmp_path):
        """
        场景: 按文件名前缀筛选
        预期: glob("2024*.csv") 只返回 2024 开头的文件
        """
        (tmp_path / "2024_sales.csv").write_text("data")
        (tmp_path / "2023_sales.csv").write_text("data")
        (tmp_path / "2024_products.csv").write_text("data")
        
        tool = GlobTool(working_dir=tmp_path)
        result = tool.execute(pattern="2024*.csv")
        
        assert "2024_sales.csv" in result["files"]
        assert "2024_products.csv" in result["files"]
        assert "2023_sales.csv" not in result["files"]
    
    def test_glob_empty_directory(self, tmp_path):
        """
        场景: 空目录
        预期: 返回空列表
        """
        tool = GlobTool(working_dir=tmp_path)
        result = tool.execute(pattern="*")
        
        assert result["success"] is True
        assert result["files"] == []


class TestReadTool:
    """测试 read 工具 - 文件读取"""
    
    def test_read_csv_with_pagination(self, tmp_path):
        """
        场景: 读取大 CSV 文件的部分内容
        预期: 支持 offset 和 limit 分页
        """
        # 准备 100 行数据
        content = "date,amount\n" + "\n".join([f"2024-01-{i:02d},{i*100}" for i in range(1, 101)])
        (tmp_path / "data.csv").write_text(content)
        
        tool = ReadTool(working_dir=tmp_path)
        result = tool.execute(path="data.csv", offset=0, limit=10)
        
        assert result["success"] is True
        assert result["total_lines"] == 101  # 含表头
        assert len(result["lines"]) == 10
        assert "date,amount" in result["lines"][0]  # 表头
        assert result["has_more"] is True
    
    def test_read_excel_structure(self, tmp_path):
        """
        场景: 读取 Excel 文件
        预期: 转换为文本表格返回
        """
        # 假设有一个测试 Excel 文件
        excel_path = tmp_path / "data.xlsx"
        # 使用 openpyxl 创建测试文件...
        
        tool = ReadTool(working_dir=tmp_path)
        result = tool.execute(path="data.xlsx", limit=50)
        
        assert result["success"] is True
        assert "sheets" in result  # 工作表信息
        assert result["format"] == "excel"
    
    def test_read_file_not_found(self, tmp_path):
        """
        场景: 文件不存在
        预期: 返回错误信息
        """
        tool = ReadTool(working_dir=tmp_path)
        result = tool.execute(path="nonexistent.csv")
        
        assert result["success"] is False
        assert "不存在" in result["error"]
    
    def test_read_outside_working_dir(self, tmp_path):
        """
        场景: 尝试读取工作目录外的文件（安全测试）
        预期: 拒绝访问
        """
        tool = ReadTool(working_dir=tmp_path)
        result = tool.execute(path="../../../etc/passwd")
        
        assert result["success"] is False
        assert "权限" in result["error"] or "越权" in result["error"]


class TestGrepTool:
    """测试 grep 工具 - 内容搜索"""
    
    def test_grep_keyword_in_csv(self, tmp_path):
        """
        场景: 在 CSV 中搜索关键词
        预期: 返回匹配行及上下文
        """
        content = """date,product,amount
2024-01-01,Apple,100
2024-01-02,Banana,200
2024-01-03,Apple,150
"""
        (tmp_path / "sales.csv").write_text(content)
        
        tool = GrepTool(working_dir=tmp_path)
        result = tool.execute(pattern="Apple", path="sales.csv", context=1)
        
        assert result["success"] is True
        assert len(result["matches"]) == 2  # 两行包含 Apple
        assert "Apple,100" in result["matches"][0]["line"]
    
    def test_grep_regex_pattern(self, tmp_path):
        """
        场景: 使用正则表达式搜索
        预期: 支持正则匹配
        """
        content = """2024-01-01,100
2024-02-01,200
2024-03-01,300
"""
        (tmp_path / "data.csv").write_text(content)
        
        tool = GrepTool(working_dir=tmp_path)
        result = tool.execute(pattern=r"2024-0[12]-", path="data.csv")
        
        assert result["success"] is True
        assert len(result["matches"]) == 2  # 01 和 02 月
    
    def test_grep_no_matches(self, tmp_path):
        """
        场景: 搜索不到内容
        预期: 返回空结果
        """
        (tmp_path / "data.csv").write_text("col1,col2\n1,2\n3,4")
        
        tool = GrepTool(working_dir=tmp_path)
        result = tool.execute(pattern="nonexistent", path="data.csv")
        
        assert result["success"] is True
        assert result["matches"] == []


class TestStatTool:
    """测试 stat 工具 - 文件信息"""
    
    def test_stat_csv_file(self, tmp_path):
        """
        场景: 获取 CSV 文件统计信息
        预期: 返回行数、列数、大小等
        """
        content = "date,amount,quantity\n" + "\n".join(["2024-01-01,100,5"] * 100)
        csv_path = tmp_path / "data.csv"
        csv_path.write_text(content)
        
        tool = StatTool(working_dir=tmp_path)
        result = tool.execute(path="data.csv")
        
        assert result["success"] is True
        assert result["line_count"] == 101  # 含表头
        assert result["column_count"] == 3
        assert result["size_bytes"] > 0
        assert result["columns"] == ["date", "amount", "quantity"]
    
    def test_stat_excel_file(self, tmp_path):
        """
        场景: 获取 Excel 文件信息
        预期: 返回工作表列表、行列数
        """
        tool = StatTool(working_dir=tmp_path)
        result = tool.execute(path="data.xlsx")
        
        assert result["success"] is True
        assert "sheets" in result
        assert result["format"] == "excel"


class TestExecTool:
    """测试 exec 工具 - 代码执行（需配合 Sandbox）"""
    
    def test_exec_pandas_analysis(self, tmp_path):
        """
        场景: 执行 Pandas 数据分析脚本
        预期: 返回分析结果
        """
        # 准备数据文件
        content = "month,amount\nJan,100\nFeb,200\nMar,150"
        (tmp_path / "sales.csv").write_text(content)
        
        code = """
import pandas as pd
df = pd.read_csv('sales.csv')
total = df['amount'].sum()
print(f"总销售额: {total}")
print(df.describe())
"""
        
        tool = ExecTool(working_dir=tmp_path)
        result = tool.execute(command=code, type="python")
        
        assert result["success"] is True
        assert "总销售额: 450" in result["output"]
        assert "mean" in result["output"]  # describe() 输出
    
    def test_exec_forbidden_import(self, tmp_path):
        """
        场景: 尝试导入危险模块（安全测试）
        预期: 执行被拒绝
        """
        code = """
import os
os.system('ls -la')
"""
        
        tool = ExecTool(working_dir=tmp_path)
        result = tool.execute(command=code, type="python")
        
        assert result["success"] is False
        assert "禁止" in result["error"] or "不允许" in result["error"]
    
    def test_exec_timeout(self, tmp_path):
        """
        场景: 执行超时代码
        预期: 返回超时错误
        """
        code = """
import time
time.sleep(60)  # 超过默认超时
"""
        
        tool = ExecTool(working_dir=tmp_path, timeout=5)
        result = tool.execute(command=code, type="python")
        
        assert result["success"] is False
        assert "超时" in result["error"] or "timeout" in result["error"].lower()
    
    def test_exec_file_access_outside_working_dir(self, tmp_path):
        """
        场景: 代码尝试访问工作目录外文件
        预期: 被拒绝
        """
        code = """
with open('/etc/passwd', 'r') as f:
    print(f.read())
"""
        
        tool = ExecTool(working_dir=tmp_path)
        result = tool.execute(command=code, type="python")
        
        assert result["success"] is False
        assert "权限" in result["error"]
