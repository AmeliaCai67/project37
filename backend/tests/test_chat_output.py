"""ChatService 输出处理测试：/sandbox_output 路径替换 + 回答 Markdown 落盘"""
from services.chat_service import ChatService


class TestReplaceSandboxPaths:
    def test_replaces_virtual_prefix_with_real_path(self):
        text = "图表已保存至 /sandbox_output/chart.png，请查看。"
        out = ChatService._replace_sandbox_paths(text, "/Users/u/37-output/2026-07-21")
        assert "/sandbox_output" not in out
        assert "/Users/u/37-output/2026-07-21/chart.png" in out

    def test_bare_prefix_without_trailing_slash(self):
        out = ChatService._replace_sandbox_paths("保存在 /sandbox_output 下", "/out/dir")
        assert out == "保存在 /out/dir 下"

    def test_no_prefix_unchanged(self):
        assert ChatService._replace_sandbox_paths("没有路径", "/out") == "没有路径"

    def test_empty_text(self):
        assert ChatService._replace_sandbox_paths("", "/out") == ""
        assert ChatService._replace_sandbox_paths(None, "/out") == ""


class TestSaveAnswerMarkdown:
    def test_saves_qa_and_artifact_list(self, tmp_path):
        (tmp_path / "chart.png").write_bytes(b"png")
        (tmp_path / ".hidden").write_text("x")

        md = ChatService._save_answer_markdown(
            str(tmp_path), "销售额前5名？", "答案是 A、B、C。"
        )

        assert md is not None and md.exists()
        assert md.name.startswith("回答_") and md.suffix == ".md"
        content = md.read_text(encoding="utf-8")
        assert "销售额前5名？" in content
        assert "答案是 A、B、C。" in content
        assert "chart.png" in content          # 产物清单
        assert ".hidden" not in content        # 隐藏文件不进清单

    def test_excludes_previous_answer_md_from_artifacts(self, tmp_path):
        (tmp_path / "回答_20260720_010000.md").write_text("旧回答")

        md = ChatService._save_answer_markdown(str(tmp_path), "Q", "A")

        content = md.read_text(encoding="utf-8")
        assert "产物清单" not in content  # 只有旧的回答 md，不应当作产物

    def test_creates_output_dir_if_missing(self, tmp_path):
        target = tmp_path / "sub" / "dir"
        md = ChatService._save_answer_markdown(str(target), "Q", "A")
        assert md is not None and md.exists()

    def test_empty_answer_placeholder(self, tmp_path):
        md = ChatService._save_answer_markdown(str(tmp_path), "Q", "")
        assert "（未生成回答）" in md.read_text(encoding="utf-8")
