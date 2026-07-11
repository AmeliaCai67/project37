"""
Pytest 配置文件
"""
import pytest
import tempfile
from pathlib import Path
import sys

# 添加项目根目录到 path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture(scope="function")
def db_session():
    """创建使用内存 SQLite 数据库的会话，函数结束后销毁"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from models.base import Base

    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=engine
    )
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def tmp_working_dir():
    """创建临时工作目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_csv_file(tmp_working_dir):
    """创建示例 CSV 文件"""
    content = """date,product,amount,quantity
2024-01-01,Apple,1000,10
2024-02-01,Apple,1200,12
2024-03-01,Apple,1500,15
2024-01-01,Banana,800,8
2024-02-01,Banana,900,9
2024-03-01,Banana,1100,11
"""
    file_path = tmp_working_dir / "sales.csv"
    file_path.write_text(content)
    return file_path


@pytest.fixture
def mock_user():
    """Mock 用户对象"""
    class MockUser:
        def __init__(self, user_id=1, role="admin"):
            self.id = user_id
            self.role = role
            self.username = f"user_{user_id}"
    return MockUser


@pytest.fixture
def mock_db_session():
    """Mock 数据库会话"""
    from unittest.mock import Mock
    return Mock()


# ============ 从 test_end_to_end 移过来的 Fixtures ============

@pytest.fixture
def client():
    """创建测试客户端"""
    from fastapi.testclient import TestClient
    from main import app
    return TestClient(app)


@pytest.fixture
def auth_headers_user():
    """普通用户的认证头"""
    return {"Authorization": "Bearer user_token"}


@pytest.fixture
def auth_headers_admin():
    """管理员的认证头"""
    return {"Authorization": "Bearer admin_token"}
