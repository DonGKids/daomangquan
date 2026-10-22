"""
导茫犬平台数据库访问与初始化模块。

本模块封装 SQLite 数据库的连接管理与应用启动时的建表/迁移逻辑：

- ``get_db()``: 上下文管理器，提供自动开关的数据库连接，统一设置 row_factory。
- ``init_database()``: 应用启动时调用，幂等创建所有表并写入默认分类数据，
  对老库执行列级迁移补齐缺失字段。

涉及的数据表：
    users          用户基本信息（用户名、密码哈希、学号、学院、专业、是否管理员）
    maze_detect    迷茫检测记录（原文、命中的关键词/分类）
    categories     信息库分类（4 个默认分类）
    infos          信息库条目（标题、内容、所属分类）
    posts          论坛帖子（标题、内容、作者、时间）
    comments       帖子评论（所属帖子、作者、内容、时间）
    feedback       用户反馈（内容、联系方式、状态）
    post_likes     帖子点赞（帖子、用户，唯一约束防重复）
"""
import sqlite3
import logging
from contextlib import contextmanager
from werkzeug.security import generate_password_hash
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@contextmanager
def get_db():
    """数据库连接上下文管理器。

    每次进入时打开一个新的 SQLite 连接，配置 ``row_factory = sqlite3.Row``
    使查询结果支持按列名访问；离开时自动关闭连接。发生 ``sqlite3.Error``
    时记录日志并向上抛出，便于调用方感知数据库异常。

    Yields:
        sqlite3.Connection: 已配置好 row_factory 的数据库连接。

    Raises:
        sqlite3.Error: 连接或执行过程中出现的底层 SQLite 异常。
    """
    db = None
    try:
        db = sqlite3.connect(Config.DATABASE, check_same_thread=False)
        db.row_factory = sqlite3.Row
        yield db
    except sqlite3.Error as e:
        logger.error(f"数据库连接错误: {e}")
        raise
    finally:
        if db:
            db.close()


def init_database():
    """初始化数据库：幂等建表 + 老库迁移 + 写入默认分类。

    执行流程：
        1. 使用 ``CREATE TABLE IF NOT EXISTS`` 创建全部 8 张表（已存在则跳过）。
        2. 通过 ``PRAGMA table_info`` 检测老表缺失的列，使用 ``ALTER TABLE``
           进行列级迁移（users.created_at、maze_detect.keywords / categories）。
        3. 写入 4 个默认分类（生活常识 / 升学就业 / 法律知识 / 创业资讯），
           已存在的分类跳过，保证可重复执行。
        4. 提交事务并写日志。

    Raises:
        Exception: 任何建表/迁移/插入过程出现的异常都会向上抛出，
            调用方（通常是 ``create_app``）需保证此函数在应用启动早期执行。
    """
    try:
        with get_db() as db:
            # users 表：用户基本信息，username 全局唯一，password 存哈希值
            # is_admin 标记管理员（0 普通 / 1 管理员），首个注册用户自动设为 1
            db.execute('''CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                student_id TEXT,
                college TEXT,
                major TEXT,
                is_admin INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

            # 老库迁移：给已存在的 users 表补 created_at / is_admin 列
            ucols = {row['name'] for row in db.execute("PRAGMA table_info(users)").fetchall()}
            if 'created_at' not in ucols:
                db.execute("ALTER TABLE users ADD COLUMN created_at TIMESTAMP")
            if 'is_admin' not in ucols:
                db.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")

            # maze_detect 表：用户提交的迷茫检测记录，keywords/categories 以 JSON 字符串存储
            db.execute('''CREATE TABLE IF NOT EXISTS maze_detect (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                keywords TEXT,
                categories TEXT,
                create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )''')

            # 老库迁移：给已存在的 maze_detect 表补 keywords / categories 列
            cols = {row['name'] for row in db.execute("PRAGMA table_info(maze_detect)").fetchall()}
            if 'keywords' not in cols:
                db.execute("ALTER TABLE maze_detect ADD COLUMN keywords TEXT")
            if 'categories' not in cols:
                db.execute("ALTER TABLE maze_detect ADD COLUMN categories TEXT")

            # categories 表：信息库分类定义，name 唯一
            db.execute('''CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT
            )''')

            # infos 表：信息库条目，外键 cate_id 指向 categories.id
            db.execute('''CREATE TABLE IF NOT EXISTS infos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cate_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                FOREIGN KEY (cate_id) REFERENCES categories(id)
            )''')

            # posts 表：论坛帖子，外键 user_id 指向 users.id
            db.execute('''CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )''')

            # comments 表：帖子评论，外键指向 posts 与 users
            db.execute('''CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (post_id) REFERENCES posts(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )''')

            # feedback 表：用户反馈，status 默认 pending 表示待处理
            db.execute('''CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                contact TEXT,
                status TEXT DEFAULT 'pending',
                create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )''')

            # post_likes 表：帖子点赞，UNIQUE(post_id, user_id) 防止同一用户重复点赞
            db.execute('''CREATE TABLE IF NOT EXISTS post_likes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(post_id, user_id),
                FOREIGN KEY (post_id) REFERENCES posts(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )''')

            # 默认 4 个分类：与 MAZE_KEYWORDS 中的分类名一一对应
            default_cates = [
                (1, "生活常识", "医保、出行、安全、日常科普"),
                (2, "升学就业", "考研、考公、实习、就业"),
                (3, "法律知识", "劳动权益、兼职安全、合同保护"),
                (4, "创业资讯", "大学生创业政策、项目资源")
            ]

            for c in default_cates:
                if not db.execute("SELECT id FROM categories WHERE id=?", (c[0],)).fetchone():
                    db.execute("INSERT INTO categories VALUES (?,?,?)", c)

            db.commit()
            logger.info("数据库初始化成功")
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        raise
