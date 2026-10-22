"""
项目级 pytest 配置：将测试数据库重定向到独立文件，避免污染生产库。

本文件在 pytest 收集任何测试之前被加载，因此在导入 ``app`` 包之前
就把 ``Config.DATABASE`` 指向 ``test_daomangquan.db``，保证所有
``get_db()`` 调用都使用测试库。每个测试开始前还会删除遗留的测试库
文件，确保从空库起步。
"""
import os
import sys

# 把项目根加入 sys.path，使 `from app import create_app` 在 tests/ 下也可用
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config  # noqa: E402

# 测试专用数据库路径：与生产库 daomangquan.db 分离
TEST_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_daomangquan.db')

# 在导入 app 包之前覆盖 DATABASE 配置，确保 get_db() 走测试库
Config.DATABASE = TEST_DB

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_test_db():
    """每个测试开始前删除遗留的测试库文件，保证从空库起步。

    该 fixture autouse，无需在测试中显式声明；执行顺序在普通 fixture 之前，
    因此 ``app`` fixture 调用 ``create_app()`` 时会自动新建表结构。
    """
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    yield
