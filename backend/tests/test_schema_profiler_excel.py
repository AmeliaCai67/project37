"""schema_profiler Excel 读取增强的单元测试"""
from pathlib import Path

import pandas as pd
import pytest

from tools.schema_profiler import read_csv_robust, read_excel_robust, load_tables


def _make_xlsx(tmp_path: Path, filename: str, data: dict, sheet_name: str = "Sheet1") -> Path:
    """辅助：生成一个 xlsx 文件"""
    p = tmp_path / filename
    with pd.ExcelWriter(p, engine="openpyxl") as writer:
        pd.DataFrame(data).to_excel(writer, sheet_name=sheet_name, index=False)
    return p


def _make_xls(tmp_path: Path, filename: str, data: dict, sheet_name: str = "Sheet1") -> Path:
    """辅助：生成一个老格式 xls 文件（需要 xlwt）"""
    xlwt = pytest.importorskip("xlwt")
    p = tmp_path / filename
    wb = xlwt.Workbook()
    ws = wb.add_sheet(sheet_name)
    cols = list(data.keys())
    for col_idx, col in enumerate(cols):
        ws.write(0, col_idx, col)
        for row_idx, val in enumerate(data[col], start=1):
            ws.write(row_idx, col_idx, val)
    wb.save(str(p))
    return p


def test_read_excel_xlsx(tmp_path):
    p = _make_xlsx(tmp_path, "test.xlsx", {"A": ["1", "2"], "B": ["x", "y"]})
    df = read_excel_robust(p)
    assert df is not None
    assert list(df.columns) == ["A", "B"]
    assert len(df) == 2


def test_read_excel_multisheet_uses_first_non_empty(tmp_path):
    p = tmp_path / "multi.xlsx"
    with pd.ExcelWriter(p, engine="openpyxl") as writer:
        pd.DataFrame().to_excel(writer, sheet_name="Empty", index=False)
        pd.DataFrame({"C": ["a", "b"]}).to_excel(writer, sheet_name="Data", index=False)
    df = read_excel_robust(p)
    assert df is not None
    assert list(df.columns) == ["C"]
    assert len(df) == 2


def test_read_csv_falls_back_to_excel_for_pseudo_csv(tmp_path):
    """扩展名是 .csv 但实际是 Excel 格式的文件应被正确读取"""
    p = tmp_path / "pseudo.csv"
    with pd.ExcelWriter(p, engine="openpyxl") as writer:
        pd.DataFrame({"X": ["1", "2"], "Y": ["foo", "bar"]}).to_excel(writer, index=False)
    df = read_csv_robust(p)
    assert df is not None
    assert set(df.columns) == {"X", "Y"}
    assert len(df) == 2


def test_load_tables_with_excel_only(tmp_path):
    _make_xlsx(tmp_path, "data.xlsx", {"name": ["Alice", "Bob"], "score": ["90", "80"]})
    tables = load_tables(tmp_path)
    assert "data" in tables
    assert len(tables["data"]) == 2


def test_read_excel_returns_none_for_invalid(tmp_path):
    p = tmp_path / "not_excel.xlsx"
    p.write_text("this is not excel")
    df = read_excel_robust(p)
    assert df is None


@pytest.mark.skipif(pd.__version__ < "1.3", reason="xlrd engine requires pandas>=1.3")
def test_read_excel_xls(tmp_path):
    xlrd = pytest.importorskip("xlrd")
    p = _make_xls(tmp_path, "legacy.xls", {"A": ["1", "2"], "B": ["x", "y"]})
    df = read_excel_robust(p)
    assert df is not None
    assert list(df.columns) == ["A", "B"]
    assert len(df) == 2
