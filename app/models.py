import sqlite3
import logging
from contextlib import contextmanager
from werkzeug.security import generate_password_hash
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@contextmanager
def get_db():
    """数据库连接上下文管理器，自动管理连接的打开和关闭"""
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
    """初始化数据库，创建必要的表结构"""
    try:
        with get_db() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                student_id TEXT,
                college TEXT,
                major TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

            # 老库迁移：给已存在的 users 表补 created_at 列
            ucols = {row['name'] for row in db.execute("PRAGMA table_info(users)").fetchall()}
            if 'created_at' not in ucols:
                db.execute("ALTER TABLE users ADD COLUMN created_at TIMESTAMP")

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

            db.execute('''CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT
            )''')

            db.execute('''CREATE TABLE IF NOT EXISTS infos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cate_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                FOREIGN KEY (cate_id) REFERENCES categories(id)
            )''')

            db.execute('''CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )''')

            db.execute('''CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (post_id) REFERENCES posts(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )''')

            db.execute('''CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                contact TEXT,
                status TEXT DEFAULT 'pending',
                create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )''')

            db.execute('''CREATE TABLE IF NOT EXISTS post_likes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(post_id, user_id),
                FOREIGN KEY (post_id) REFERENCES posts(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )''')

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