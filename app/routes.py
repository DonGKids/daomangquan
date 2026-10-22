"""
导茫犬平台视图与 API 路由模块。

本模块定义了应用的所有 URL 路由，覆盖：
    - 用户注册 / 登录 / 退出 / 个人中心
    - 迷茫检测与关键词提取
    - 信息库分类查询与搜索
    - 论坛帖子发布、评论、点赞、删除
    - 用户反馈提交与历史查询
    - 管理员后台（帖子/信息/用户/反馈管理）

所有路由注册在 `main` 蓝图上，由 `app.create_app()` 装载。
"""
from flask import Blueprint, render_template, request, jsonify, redirect, session
from app.models import get_db
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
import json
import logging
import math
import re

bp = Blueprint('main', __name__)
logger = logging.getLogger(__name__)


def require_admin(func):
    """装饰器：要求当前登录用户为管理员。

    判断规则：
        1. session 中必须存在 ``user_id``，否则返回 401 JSON。
        2. 查询 users 表确认 ``is_admin=1``；session 中的 ``is_admin`` 仅作模板渲染优化，
           不直接信任，必须以数据库为准。
        3. 校验通过则进入被装饰函数；否则返回 403 JSON。

    用于保护所有 ``/admin`` 与 ``/api/admin/*`` 路由。
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify(code=401, msg='请先登录'), 401
        try:
            with get_db() as db:
                row = db.execute(
                    'SELECT is_admin FROM users WHERE id=?',
                    (session['user_id'],)
                ).fetchone()
            is_admin = bool(row and row['is_admin'])
        except Exception as e:
            logger.error(f"管理员鉴权失败: {e}")
            return jsonify(code=500, msg='服务器错误'), 500
        if not is_admin:
            return jsonify(code=403, msg='无权限，仅管理员可访问'), 403
        # 同步到 session，便于后续渲染/日志使用
        session['is_admin'] = True
        return func(*args, **kwargs)
    return wrapper

# 输入验证规则：用户名 / 密码 / 内容的最小最大长度限制
USERNAME_MIN_LEN = 3
USERNAME_MAX_LEN = 20
PASSWORD_MIN_LEN = 6
CONTENT_MAX_LEN = 1000

# 迷茫关键词库：分类名 -> 关键词列表（对应 categories 表的 4 个默认分类）
MAZE_KEYWORDS = {
    "生活常识": ["医保", "社保", "租房", "出行", "银行卡", "电话卡", "户籍", "宿舍", "安全", "生活费", "搬家"],
    "升学就业": ["考研", "考公", "保研", "读研", "研究生", "出国", "留学", "雅思", "托福",
                "实习", "兼职", "工作", "求职", "招聘", "简历", "面试", "入职", "就业", "毕业", "选调", "秋招", "春招"],
    "法律知识": ["合同", "劳动法", "维权", "纠纷", "法律", "权益", "签约", "仲裁", "诉讼", "试用期", "三方协议"],
    "创业资讯": ["创业", "创新", "项目", "融资", "风投", "合伙人", "startup", "创业团队", "孵化"],
}

# 心理/情绪关键词（不映射到分类，仅用于检测报告呈现）
MOOD_KEYWORDS = ["焦虑", "迷茫", "压力", "抑郁", "孤独", "想家", "自卑", "内卷", "失眠", "烦躁"]


def extract_keywords(text):
    """从用户输入文本提取命中的迷茫关键词与情绪词。

    遍历 MAZE_KEYWORDS 中每个分类下的关键词，命中则记录关键词与对应分类名；
    再扫描 MOOD_KEYWORDS 提取情绪词，用于检测报告呈现。

    Args:
        text (str): 用户输入的原始文本，例如迷茫描述。

    Returns:
        tuple[list[str], list[str], list[str]]: 三元组
            - matched_words: 命中的关键词列表（去重保序）
            - matched_categories: 命中的分类名列表（去重）
            - mood_words: 命中的情绪词列表（去重）
    """
    matched_words, matched_categories, mood_words = [], [], []
    for cat_name, words in MAZE_KEYWORDS.items():
        for w in words:
            if w in text and w not in matched_words:
                matched_words.append(w)
                if cat_name not in matched_categories:
                    matched_categories.append(cat_name)
    for w in MOOD_KEYWORDS:
        if w in text and w not in mood_words:
            mood_words.append(w)
    return matched_words, matched_categories, mood_words


def build_recommendations(db, keywords, cat_names, limit_per_cat=3):
    """根据命中分类从 infos 表生成结构化推荐内容。

    推荐逻辑：
        1. 若有命中分类，则在这些分类下查询 infos；否则查询全库前 4 条作为默认推荐。
        2. 同分类下的条目按 "标题命中 > 正文命中" 排序，靠前者优先展示。
        3. 每个分类最多保留 limit_per_cat 条，并附带推荐理由（命中关键词或默认推荐）。

    Args:
        db: 已打开的 SQLite 数据库连接（sqlite3.Connection）。
        keywords (list[str]): 命中的关键词列表，用于排序与理由生成。
        cat_names (list[str]): 命中的分类名列表；为空时走默认推荐分支。
        limit_per_cat (int, optional): 每个分类返回的最大条目数，默认 3。

    Returns:
        list[dict]: 推荐结果列表，每项形如
            ``{"category": str, "reason": str, "items": list[dict]}``。
    """
    if cat_names:
        placeholders = ",".join("?" * len(cat_names))
        rows = db.execute(
            f"SELECT i.id, i.title, i.content, c.name AS category "
            f"FROM infos i JOIN categories c ON i.cate_id = c.id "
            f"WHERE c.name IN ({placeholders})",
            cat_names
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT i.id, i.title, i.content, c.name AS category "
            "FROM infos i JOIN categories c ON i.cate_id = c.id "
            "ORDER BY c.id, i.id LIMIT 4"
        ).fetchall()

    grouped = {}
    for r in rows:
        cat = r['category']
        grouped.setdefault(cat, [])
        item = dict(r)
        item['match_in_title'] = any(k in r['title'] for k in keywords)
        item['match_in_content'] = any(k in r['content'] for k in keywords)
        grouped[cat].append(item)

    result = []
    for cat, items in grouped.items():
        items.sort(key=lambda x: (x['match_in_title'], x['match_in_content']), reverse=True)
        cat_kws = [k for k in keywords if any(k in (i['title'] + i['content']) for i in items)]
        result.append({
            "category": cat,
            "reason": f"命中关键词：{', '.join(cat_kws)}" if cat_kws else "默认推荐",
            "items": items[:limit_per_cat]
        })
    return result


def validate_username(username):
    """校验用户名是否符合格式与长度要求。

    规则：非空、长度在 USERNAME_MIN_LEN~USERNAME_MAX_LEN 之间、
    仅允许中文、英文、数字和下划线。

    Args:
        username (str): 待校验的用户名原文。

    Returns:
        tuple[bool, str]: (是否通过, 错误描述)；通过时错误描述为空字符串。
    """
    if not username:
        return False, "用户名不能为空"
    if len(username) < USERNAME_MIN_LEN or len(username) > USERNAME_MAX_LEN:
        return False, f"用户名长度必须在{USERNAME_MIN_LEN}-{USERNAME_MAX_LEN}个字符之间"
    if not re.match(r'^[\u4e00-\u9fa5a-zA-Z0-9_]+$', username):
        return False, "用户名只能包含中文、英文、数字和下划线"
    return True, ""


def validate_password(password):
    """校验密码强度是否满足最低要求。

    规则：非空、长度不小于 PASSWORD_MIN_LEN。

    Args:
        password (str): 待校验的密码原文。

    Returns:
        tuple[bool, str]: (是否通过, 错误描述)；通过时错误描述为空字符串。
    """
    if not password:
        return False, "密码不能为空"
    if len(password) < PASSWORD_MIN_LEN:
        return False, f"密码长度至少{PASSWORD_MIN_LEN}个字符"
    return True, ""


def validate_content(content, max_len=CONTENT_MAX_LEN):
    """校验文本内容是否非空且未超过最大长度。

    Args:
        content (str): 待校验的文本内容。
        max_len (int, optional): 允许的最大字符数，默认 CONTENT_MAX_LEN。

    Returns:
        tuple[bool, str]: (是否通过, 错误描述)；通过时错误描述为空字符串。
    """
    if not content or not content.strip():
        return False, "内容不能为空"
    if len(content) > max_len:
        return False, f"内容长度不能超过{max_len}个字符"
    return True, ""


# 首页
@bp.route('/')
def index():
    """首页：聚合平台统计、信息库分类、最新讨论与个性化推荐。

    数据来源：
        - stats: users / infos / posts / comments 四张表的总数
        - categories: categories 表的 4 大默认分类
        - latest_posts: posts 表按时间倒序前 5 条（带作者与评论数）
        - recommendations: 已登录用户最近一次检测命中的关键词/分类
          转交 build_recommendations 生成；未登录或无检测记录时为 None。

    Returns:
        str: 渲染后的 index.html。加载失败时返回带错误提示的首页。
    """
    try:
        with get_db() as db:
            # 平台统计：用户数 / 信息库条目 / 帖子数 / 评论数
            stats = {
                'users': db.execute('SELECT COUNT(*) FROM users').fetchone()[0],
                'infos': db.execute('SELECT COUNT(*) FROM infos').fetchone()[0],
                'posts': db.execute('SELECT COUNT(*) FROM posts').fetchone()[0],
                'comments': db.execute('SELECT COUNT(*) FROM comments').fetchone()[0],
            }

            # 信息库 4 大分类
            categories = db.execute(
                'SELECT id, name, description FROM categories ORDER BY id'
            ).fetchall()

            # 最新讨论（5 条，带作者和评论数）
            latest_posts = db.execute(
                'SELECT p.id, p.title, p.content, u.username AS author, '
                'p.create_time, '
                '(SELECT COUNT(*) FROM comments WHERE post_id=p.id) AS reply_count '
                'FROM posts p JOIN users u ON p.user_id = u.id '
                'ORDER BY p.create_time DESC LIMIT 5'
            ).fetchall()

            # 个性化推荐：已登录 + 有检测记录 → 基于最近一次检测的关键词/分类推荐
            recommendations = None
            has_detection = False
            if 'user_id' in session:
                last_detect = db.execute(
                    'SELECT keywords, categories FROM maze_detect '
                    'WHERE user_id=? ORDER BY id DESC LIMIT 1',
                    (session['user_id'],)
                ).fetchone()
                if last_detect:
                    has_detection = True
                    try:
                        kws = json.loads(last_detect['keywords'] or '[]')
                        cats = json.loads(last_detect['categories'] or '[]')
                    except Exception:
                        kws, cats = [], []
                    recommendations = build_recommendations(db, kws, cats, limit_per_cat=2)

            return render_template(
                'index.html',
                stats=stats,
                categories=[dict(c) for c in categories],
                latest_posts=[dict(p) for p in latest_posts],
                recommendations=recommendations,
                has_detection=has_detection,
                is_logged_in='user_id' in session,
            )
    except Exception as e:
        logger.error(f"首页加载错误: {e}")
        return render_template('index.html', error='加载失败，请稍后重试')


@bp.route('/login', methods=['GET', 'POST'])
def login():
    """用户登录。

    GET 渲染登录页面；POST 校验用户名/密码格式后查询 users 表，
    使用 ``check_password_hash`` 比对密码，通过则写入 session 并返回 200，
    否则返回 400/500 错误 JSON。

    Returns:
        str | Response: GET 返回 login.html；POST 返回 JSON
            ``{"code": int, "msg": str}``。
    """
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        is_valid, msg = validate_username(username)
        if not is_valid:
            return jsonify(code=400, msg=msg)

        is_valid, msg = validate_password(password)
        if not is_valid:
            return jsonify(code=400, msg=msg)

        try:
            with get_db() as db:
                user = db.execute(
                    'SELECT * FROM users WHERE username=?',
                    (username,)
                ).fetchone()

                if user and check_password_hash(user['password'], password):
                    session.permanent = True
                    session['user_id'] = user['id']
                    session['username'] = user['username']
                    # 同步 is_admin 到 session，供模板（base.html）与 admin 路由直接读取
                    session['is_admin'] = bool(user['is_admin']) if 'is_admin' in user.keys() else False
                    logger.info(f"用户 {username} 登录成功")
                    return jsonify(code=200, msg='登录成功')
                else:
                    logger.warning(f"用户 {username} 登录失败 - 账号或密码错误")
                    return jsonify(code=400, msg='账号或密码错误')
        except Exception as e:
            logger.error(f"登录错误: {e}")
            return jsonify(code=500, msg='服务器错误，请稍后重试')

    return render_template('login.html')


@bp.route('/register', methods=['GET', 'POST'])
def register():
    """用户注册。

    GET 渲染注册页面；POST 校验用户名/密码格式，检查用户名是否已存在，
    通过后使用 ``generate_password_hash`` 加密密码写入 users 表。

    Returns:
        str | Response: GET 返回 register.html；POST 返回 JSON
            ``{"code": int, "msg": str}``。
    """
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        student_id = request.form.get('student_id', '').strip()
        college = request.form.get('college', '').strip()
        major = request.form.get('major', '').strip()

        is_valid, msg = validate_username(username)
        if not is_valid:
            return jsonify(code=400, msg=msg)

        is_valid, msg = validate_password(password)
        if not is_valid:
            return jsonify(code=400, msg=msg)

        try:
            with get_db() as db:
                existing_user = db.execute(
                    'SELECT id FROM users WHERE username=?',
                    (username,)
                ).fetchone()

                if existing_user:
                    logger.warning(f"注册失败 - 用户名已存在: {username}")
                    return jsonify(code=400, msg='用户名已存在')

                hashed_password = generate_password_hash(password)
                # 首个注册用户自动设为管理员（is_admin=1）
                user_count = db.execute('SELECT COUNT(*) FROM users').fetchone()[0]
                is_admin = 1 if user_count == 0 else 0
                db.execute(
                    'INSERT INTO users (username, password, student_id, college, major, is_admin) '
                    'VALUES (?,?,?,?,?,?)',
                    (username, hashed_password, student_id, college, major, is_admin)
                )
                db.commit()
                logger.info(f"用户 {username} 注册成功 (is_admin={is_admin})")
                return jsonify(code=200, msg='注册成功')
        except Exception as e:
            logger.error(f"注册错误: {e}")
            return jsonify(code=500, msg='注册失败，请稍后重试')

    return render_template('register.html')


@bp.route('/logout')
def logout():
    """退出登录。

    若 session 中不存在 user_id，直接重定向到首页；
    否则清空 session 并写日志后重定向到首页。

    Returns:
        Response: 重定向到 ``/``。
    """
    if 'user_id' not in session:
        return redirect('/')
    username = session.get('username', 'Unknown')
    session.clear()
    logger.info(f"用户 {username} 已退出登录")
    return redirect('/')


@bp.route('/maze')
def maze():
    """迷茫检测页面：未登录跳转登录，已登录渲染 maze.html。"""
    if 'user_id' not in session:
        return redirect('/login')
    return render_template('maze.html')


@bp.route('/info')
def info():
    """信息库页面：渲染 info.html，数据由 /api/info 异步加载。"""
    return render_template('info.html')


@bp.route('/forum')
def forum():
    """论坛页面：渲染 forum.html，帖子列表由 /api/posts 异步加载。"""
    return render_template('forum.html')


@bp.route('/profile')
def profile():
    """个人中心：展示用户基本信息、统计、检测历史、发帖历史、反馈历史。

    数据来源：
        - user: users 表的 username / student_id / college / major / created_at
        - detect_count / post_count: maze_detect / posts 的总数
        - detections: maze_detect 最近 5 条
        - my_posts: posts 最近 5 条
        - my_feedback + feedback_count: feedback 最近 5 条 + 总数

    Returns:
        str: 渲染后的 profile.html。未登录时重定向到 /login。
    """
    if 'user_id' not in session:
        return redirect('/login')

    try:
        with get_db() as db:
            uid = session['user_id']

            # 用户基本信息
            user = db.execute(
                'SELECT username, student_id, college, major, created_at '
                'FROM users WHERE id=?', (uid,)
            ).fetchone()

            # 统计：检测次数、发帖数
            detect_count = db.execute(
                'SELECT COUNT(*) FROM maze_detect WHERE user_id=?', (uid,)
            ).fetchone()[0]
            post_count = db.execute(
                'SELECT COUNT(*) FROM posts WHERE user_id=?', (uid,)
            ).fetchone()[0]

            # 检测历史（最近 5 条）
            detections = db.execute(
                'SELECT id, content, keywords, categories, create_time '
                'FROM maze_detect WHERE user_id=? ORDER BY id DESC LIMIT 5',
                (uid,)
            ).fetchall()

            # 发帖历史（最近 5 条）
            my_posts = db.execute(
                'SELECT id, title, content, create_time '
                'FROM posts WHERE user_id=? ORDER BY id DESC LIMIT 5',
                (uid,)
            ).fetchall()

            # 反馈历史（最近 5 条）
            my_feedback = db.execute(
                'SELECT id, content, contact, status, create_time '
                'FROM feedback WHERE user_id=? ORDER BY id DESC LIMIT 5',
                (uid,)
            ).fetchall()
            feedback_count = db.execute(
                'SELECT COUNT(*) FROM feedback WHERE user_id=?', (uid,)
            ).fetchone()[0]

            return render_template(
                'profile.html',
                user=user,
                detect_count=detect_count,
                post_count=post_count,
                detections=[dict(d) for d in detections],
                my_posts=[dict(p) for p in my_posts],
                my_feedback=[dict(f) for f in my_feedback],
                feedback_count=feedback_count,
            )
    except Exception as e:
        logger.error(f"个人中心加载错误: {e}")
        return render_template('profile.html', error='加载失败，请稍后重试')


@bp.route('/api/maze', methods=['POST'])
def api_maze():
    """迷茫检测 API：提取关键词 → 查推荐 → 落库检测记录 → 返回结构化结果。

    流程：
        1. 校验登录与内容合法性。
        2. 调用 ``extract_keywords`` 提取命中关键词、分类、情绪词。
        3. 调用 ``build_recommendations`` 生成推荐内容。
        4. 将本次检测写入 maze_detect 表。
        5. 返回 keywords / mood / recommendations，并提示命中数量。

    Returns:
        Response: JSON ``{"code": int, "msg": str, "data": dict}``，
            未登录返回 401，内容不合法返回 400，服务器错误返回 500。
    """
    if 'user_id' not in session:
        return jsonify(code=401, msg='请先登录')

    content = request.form.get('content', '').strip()
    is_valid, msg = validate_content(content)
    if not is_valid:
        return jsonify(code=400, msg=msg)

    try:
        keywords, cat_names, mood_words = extract_keywords(content)
        with get_db() as db:
            recommendations = build_recommendations(db, keywords, cat_names)

            db.execute(
                'INSERT INTO maze_detect (user_id, content, keywords, categories) VALUES (?,?,?,?)',
                (session['user_id'], content,
                 json.dumps(keywords, ensure_ascii=False),
                 json.dumps(cat_names, ensure_ascii=False))
            )
            db.commit()

            logger.info(
                f"用户 {session['username']} 提交迷茫检测，"
                f"关键词={keywords}, 分类={cat_names}, 情绪={mood_words}"
            )

            if keywords:
                msg = f"检测完成！识别到 {len(keywords)} 个关键词，匹配 {len(cat_names)} 个方向"
            else:
                msg = "未识别到明确方向关键词，已为您展示通用推荐，可尝试更具体描述困惑"

            return jsonify(
                code=200,
                msg=msg,
                data={
                    "keywords": keywords,
                    "mood": mood_words,
                    "recommendations": recommendations
                }
            )
    except Exception as e:
        logger.error(f"迷茫检测错误: {e}")
        return jsonify(code=500, msg='提交失败，请稍后重试')


@bp.route('/api/info')
def api_info():
    """获取信息库内容。

    支持的查询参数（可叠加）：
        - 无参数：返回全部信息（带分类名）。
        - ?category=升学就业：按分类名筛选。
        - ?cate_id=2：按分类 id 筛选（优先于 category）。
        - ?q=考研：按关键词模糊搜索 title 和 content。

    Returns:
        Response: JSON ``{"code": int, "data": list[dict]}``，
            每条记录含 id / title / content / cate_id / category。
    """
    category = request.args.get('category', '').strip()
    cate_id = request.args.get('cate_id', '').strip()
    q = request.args.get('q', '').strip()
    try:
        with get_db() as db:
            sql = (
                'SELECT i.id, i.title, i.content, i.cate_id, '
                'c.name AS category '
                'FROM infos i '
                'JOIN categories c ON i.cate_id = c.id'
            )
            params = []
            conditions = []
            if cate_id:
                conditions.append('i.cate_id=?')
                params.append(int(cate_id))
            elif category:
                conditions.append('c.name=?')
                params.append(category)
            if q:
                conditions.append('(i.title LIKE ? OR i.content LIKE ?)')
                kw = f'%{q}%'
                params.extend([kw, kw])
            if conditions:
                sql += ' WHERE ' + ' AND '.join(conditions)
            sql += ' ORDER BY i.id DESC'
            data = db.execute(sql, params).fetchall()
            return jsonify(code=200, data=[dict(d) for d in data])
    except Exception as e:
        logger.error(f"获取信息库错误: {e}")
        return jsonify(code=500, data=[])


@bp.route('/api/post', methods=['POST'])
def api_post():
    """发布帖子 API。

    校验登录状态、标题（最长 100）与正文（最长 CONTENT_MAX_LEN）后
    写入 posts 表，并写日志记录发布者与标题。

    Returns:
        Response: JSON ``{"code": int, "msg": str}``，
            未登录返回 401，校验失败返回 400，服务器错误返回 500。
    """
    if 'user_id' not in session:
        return jsonify(code=401, msg='请先登录')

    title = request.form.get('title', '').strip()
    content = request.form.get('content', '').strip()

    is_valid, msg = validate_content(title, 100)
    if not is_valid:
        return jsonify(code=400, msg=f"标题{msg}")

    is_valid, msg = validate_content(content)
    if not is_valid:
        return jsonify(code=400, msg=f"内容{msg}")

    try:
        with get_db() as db:
            db.execute(
                'INSERT INTO posts (user_id, title, content) VALUES (?,?,?)',
                (session['user_id'], title, content)
            )
            db.commit()
            logger.info(f"用户 {session['username']} 发布帖子: {title}")
            return jsonify(code=200, msg='发布成功')
    except Exception as e:
        logger.error(f"发布帖子错误: {e}")
        return jsonify(code=500, msg='发布失败，请稍后重试')


@bp.route('/api/posts')
def api_posts():
    """获取帖子列表（分页）。

    查询参数：
        - ?page=1：页码，默认 1，小于 1 自动取 1。
        - ?limit=10：每页条数，默认 10，限制在 1~50 之间。

    返回结构包含分页元信息（total / page / limit / total_pages），
    每条记录附作者、评论数、点赞数与当前用户是否已点赞标记。

    Returns:
        Response: JSON ``{"code": int, "data": list[dict],
            "total": int, "page": int, "limit": int, "total_pages": int}``。
    """
    try:
        page = max(int(request.args.get('page', 1)), 1)
        limit = min(max(int(request.args.get('limit', 10)), 1), 50)  # 1~50 之间
        offset = (page - 1) * limit
        with get_db() as db:
            uid = session.get('user_id', -1)
            # 总数
            total = db.execute('SELECT COUNT(*) FROM posts').fetchone()[0]
            # 分页查询
            posts = db.execute(
                'SELECT p.id, p.user_id, u.username AS author, '
                'p.title, p.content, p.create_time, '
                '(SELECT COUNT(*) FROM comments WHERE post_id=p.id) AS reply_count, '
                '(SELECT COUNT(*) FROM post_likes WHERE post_id=p.id) AS like_count, '
                'EXISTS(SELECT 1 FROM post_likes WHERE post_id=p.id AND user_id=?) AS is_liked '
                'FROM posts p '
                'JOIN users u ON p.user_id = u.id '
                'ORDER BY p.create_time DESC '
                'LIMIT ? OFFSET ?',
                (uid, limit, offset)
            ).fetchall()
            total_pages = math.ceil(total / limit) if total > 0 else 1
            return jsonify(
                code=200,
                data=[dict(p) for p in posts],
                total=total,
                page=page,
                limit=limit,
                total_pages=total_pages,
            )
    except Exception as e:
        logger.error(f"获取帖子列表错误: {e}")
        return jsonify(code=500, data=[], total=0, page=1, total_pages=1)


@bp.route('/post/<int:post_id>')
def post_detail(post_id):
    """帖子详情页：展示原帖内容 + 评论列表 + 评论输入框。

    Args:
        post_id (int): 帖子 ID，由 URL 路径传入。

    Returns:
        str: 渲染后的 post_detail.html。帖子不存在时返回带错误提示的页面。
    """
    try:
        with get_db() as db:
            uid = session.get('user_id', -1)
            post = db.execute(
                'SELECT p.id, p.user_id, u.username AS author, '
                'p.title, p.content, p.create_time, '
                '(SELECT COUNT(*) FROM comments WHERE post_id=p.id) AS reply_count, '
                '(SELECT COUNT(*) FROM post_likes WHERE post_id=p.id) AS like_count, '
                'EXISTS(SELECT 1 FROM post_likes WHERE post_id=p.id AND user_id=?) AS is_liked '
                'FROM posts p '
                'JOIN users u ON p.user_id = u.id '
                'WHERE p.id=?', (uid, post_id)
            ).fetchone()
            if post is None:
                return render_template('post_detail.html', error='帖子不存在或已删除')
            return render_template('post_detail.html', post=dict(post))
    except Exception as e:
        logger.error(f"帖子详情加载错误: {e}")
        return render_template('post_detail.html', error='加载失败，请稍后重试')


@bp.route('/api/posts/<int:post_id>/like', methods=['POST'])
def api_toggle_like(post_id):
    """点赞 / 取消点赞（toggle）。

    已点赞则删除 post_likes 记录（取消），未点赞则插入新记录。
    操作前会校验帖子是否存在。

    Args:
        post_id (int): 帖子 ID。

    Returns:
        Response: JSON ``{"code": int, "msg": str, "liked": bool}``，
            未登录返回 401，帖子不存在返回 404。
    """
    if 'user_id' not in session:
        return jsonify(code=401, msg='请先登录')
    try:
        with get_db() as db:
            # 校验帖子存在
            exists = db.execute('SELECT 1 FROM posts WHERE id=?', (post_id,)).fetchone()
            if exists is None:
                return jsonify(code=404, msg='帖子不存在')
            uid = session['user_id']
            # 检查是否已点赞
            liked = db.execute(
                'SELECT 1 FROM post_likes WHERE post_id=? AND user_id=?',
                (post_id, uid)
            ).fetchone()
            if liked:
                db.execute('DELETE FROM post_likes WHERE post_id=? AND user_id=?', (post_id, uid))
                db.commit()
                return jsonify(code=200, msg='已取消点赞', liked=False)
            else:
                db.execute('INSERT INTO post_likes (post_id, user_id) VALUES (?,?)', (post_id, uid))
                db.commit()
                logger.info(f"用户 {session['username']} 点赞帖子 {post_id}")
                return jsonify(code=200, msg='点赞成功', liked=True)
    except Exception as e:
        logger.error(f"点赞操作错误: {e}")
        return jsonify(code=500, msg='操作失败，请稍后重试')


@bp.route('/api/posts/<int:post_id>/delete', methods=['POST'])
def api_delete_post(post_id):
    """删除帖子。仅作者本人可删。

    删除前校验帖子存在且属于当前登录用户；
    通过后级联删除关联的 comments 与 post_likes 记录，
    最后删除 posts 记录并提交事务。

    Args:
        post_id (int): 帖子 ID。

    Returns:
        Response: JSON ``{"code": int, "msg": str}``，
            未登录 401 / 帖子不存在 404 / 非作者 403 / 成功 200。
    """
    if 'user_id' not in session:
        return jsonify(code=401, msg='请先登录')
    try:
        with get_db() as db:
            # 校验帖子存在且属于当前用户
            post = db.execute(
                'SELECT user_id FROM posts WHERE id=?', (post_id,)
            ).fetchone()
            if post is None:
                return jsonify(code=404, msg='帖子不存在')
            if post['user_id'] != session['user_id']:
                return jsonify(code=403, msg='只能删除自己的帖子')
            # 级联删除：评论 → 点赞 → 帖子
            db.execute('DELETE FROM comments WHERE post_id=?', (post_id,))
            db.execute('DELETE FROM post_likes WHERE post_id=?', (post_id,))
            db.execute('DELETE FROM posts WHERE id=?', (post_id,))
            db.commit()
            logger.info(f"用户 {session['username']} 删除帖子 {post_id}")
            return jsonify(code=200, msg='删除成功')
    except Exception as e:
        logger.error(f"删除帖子错误: {e}")
        return jsonify(code=500, msg='删除失败，请稍后重试')


@bp.route('/api/posts/<int:post_id>/comments')
def api_comments(post_id):
    """获取某帖子的评论列表（按时间正序）。

    Args:
        post_id (int): 帖子 ID。

    Returns:
        Response: JSON ``{"code": int, "data": list[dict]}``，
            每条记录含 id / user_id / author / content / create_time。
    """
    try:
        with get_db() as db:
            rows = db.execute(
                'SELECT c.id, c.user_id, u.username AS author, '
                'c.content, c.create_time '
                'FROM comments c '
                'JOIN users u ON c.user_id = u.id '
                'WHERE c.post_id=? '
                'ORDER BY c.create_time ASC',
                (post_id,)
            ).fetchall()
            return jsonify(code=200, data=[dict(r) for r in rows])
    except Exception as e:
        logger.error(f"获取评论错误: {e}")
        return jsonify(code=500, data=[])


@bp.route('/api/posts/<int:post_id>/comments', methods=['POST'])
def api_add_comment(post_id):
    """发表评论。需登录。

    校验登录状态与评论内容（最长 500 字），校验帖子存在后写入 comments 表。

    Args:
        post_id (int): 帖子 ID。

    Returns:
        Response: JSON ``{"code": int, "msg": str}``，
            未登录 401 / 校验失败 400 / 帖子不存在 404 / 成功 200。
    """
    if 'user_id' not in session:
        return jsonify(code=401, msg='请先登录')

    content = request.form.get('content', '').strip()
    is_valid, msg = validate_content(content, 500)
    if not is_valid:
        return jsonify(code=400, msg=f"评论{msg}")

    try:
        with get_db() as db:
            # 校验帖子存在
            exists = db.execute('SELECT 1 FROM posts WHERE id=?', (post_id,)).fetchone()
            if exists is None:
                return jsonify(code=404, msg='帖子不存在')

            db.execute(
                'INSERT INTO comments (post_id, user_id, content) VALUES (?,?,?)',
                (post_id, session['user_id'], content)
            )
            db.commit()
            logger.info(f"用户 {session['username']} 评论帖子 {post_id}")
            return jsonify(code=200, msg='评论成功')
    except Exception as e:
        logger.error(f"发表评论错误: {e}")
        return jsonify(code=500, msg='评论失败，请稍后重试')


@bp.route('/api/feedback', methods=['POST'])
def api_add_feedback():
    """提交用户反馈。需登录。

    校验 content（必填，最长 500 字）与 contact（选填，最长 100 字），
    通过后写入 feedback 表，初始状态为 ``pending``。

    Returns:
        Response: JSON ``{"code": int, "msg": str}``，
            未登录 401 / 校验失败 400 / 成功 200 / 服务器错误 500。
    """
    if 'user_id' not in session:
        return jsonify(code=401, msg='请先登录')

    content = request.form.get('content', '').strip()
    contact = request.form.get('contact', '').strip()

    is_valid, msg = validate_content(content, 500)
    if not is_valid:
        return jsonify(code=400, msg=f"反馈{msg}")

    if len(contact) > 100:
        return jsonify(code=400, msg='联系方式不能超过100字')

    try:
        with get_db() as db:
            db.execute(
                'INSERT INTO feedback (user_id, content, contact) VALUES (?,?,?)',
                (session['user_id'], content, contact)
            )
            db.commit()
            logger.info(f"用户 {session['username']} 提交反馈")
            return jsonify(code=200, msg='反馈已提交，感谢您的建议！')
    except Exception as e:
        logger.error(f"提交反馈错误: {e}")
        return jsonify(code=500, msg='提交失败，请稍后重试')


@bp.route('/api/feedback/mine')
def api_my_feedback():
    """查看当前用户的反馈历史。

    返回 feedback 表中属于当前登录用户的最近 20 条记录，按时间倒序排列。

    Returns:
        Response: JSON ``{"code": int, "data": list[dict]}``，
            每条记录含 id / content / contact / status / create_time。
            未登录返回 401。
    """
    if 'user_id' not in session:
        return jsonify(code=401, msg='请先登录')

    try:
        with get_db() as db:
            rows = db.execute(
                'SELECT id, content, contact, status, create_time '
                'FROM feedback WHERE user_id=? ORDER BY id DESC LIMIT 20',
                (session['user_id'],)
            ).fetchall()
            return jsonify(code=200, data=[dict(r) for r in rows])
    except Exception as e:
        logger.error(f"获取反馈历史错误: {e}")
        return jsonify(code=500, data=[])


# ──────────────────────────────────────────────────────────────
# 管理员后台：页面 + API
# ──────────────────────────────────────────────────────────────

@bp.route('/admin')
def admin_page():
    """管理后台页面。

    未登录用户重定向到 /login；已登录但非管理员用户重定向到 /。
    管理员渲染 admin.html，由前端 admin.js 调用各 /api/admin/* 接口。
    """
    if 'user_id' not in session:
        return redirect('/login')
    if not session.get('is_admin'):
        # session 中可能存有旧的 is_admin=False，但保险起见查一次数据库
        try:
            with get_db() as db:
                row = db.execute(
                    'SELECT is_admin FROM users WHERE id=?',
                    (session['user_id'],)
                ).fetchone()
            if not (row and row['is_admin']):
                return redirect('/')
            session['is_admin'] = True
        except Exception as e:
            logger.error(f"管理后台鉴权失败: {e}")
            return redirect('/')
    return render_template('admin.html')


@bp.route('/api/admin/posts')
@require_admin
def admin_list_posts():
    """管理员：获取所有帖子（带作者、评论数、点赞数），支持分页。

    查询参数：
        - ?page=1：页码，默认 1。
        - ?limit=10：每页条数，默认 10，限制在 1~50。

    Returns:
        Response: JSON ``{"code": int, "data": list[dict],
            "total": int, "page": int, "limit": int, "total_pages": int}``。
    """
    try:
        page = max(int(request.args.get('page', 1)), 1)
        limit = min(max(int(request.args.get('limit', 10)), 1), 50)
        offset = (page - 1) * limit
        with get_db() as db:
            total = db.execute('SELECT COUNT(*) FROM posts').fetchone()[0]
            rows = db.execute(
                'SELECT p.id, p.user_id, u.username AS author, p.title, p.content, '
                'p.create_time, '
                '(SELECT COUNT(*) FROM comments WHERE post_id=p.id) AS reply_count, '
                '(SELECT COUNT(*) FROM post_likes WHERE post_id=p.id) AS like_count '
                'FROM posts p JOIN users u ON p.user_id = u.id '
                'ORDER BY p.create_time DESC '
                'LIMIT ? OFFSET ?',
                (limit, offset)
            ).fetchall()
            total_pages = math.ceil(total / limit) if total > 0 else 1
            return jsonify(
                code=200,
                data=[dict(r) for r in rows],
                total=total,
                page=page,
                limit=limit,
                total_pages=total_pages,
            )
    except Exception as e:
        logger.error(f"管理员获取帖子列表错误: {e}")
        return jsonify(code=500, data=[], total=0, page=1, total_pages=1)


@bp.route('/api/admin/posts/<int:post_id>/delete', methods=['POST'])
@require_admin
def admin_delete_post(post_id):
    """管理员：删除任何用户的帖子。

    复用级联删除逻辑：先删 comments，再删 post_likes，最后删 posts。

    Args:
        post_id (int): 帖子 ID。

    Returns:
        Response: JSON ``{"code": int, "msg": str}``，
            帖子不存在 404 / 成功 200。
    """
    try:
        with get_db() as db:
            exists = db.execute('SELECT 1 FROM posts WHERE id=?', (post_id,)).fetchone()
            if exists is None:
                return jsonify(code=404, msg='帖子不存在')
            db.execute('DELETE FROM comments WHERE post_id=?', (post_id,))
            db.execute('DELETE FROM post_likes WHERE post_id=?', (post_id,))
            db.execute('DELETE FROM posts WHERE id=?', (post_id,))
            db.commit()
            logger.info(
                f"管理员 {session.get('username')} 删除帖子 {post_id}"
            )
            return jsonify(code=200, msg='删除成功')
    except Exception as e:
        logger.error(f"管理员删除帖子错误: {e}")
        return jsonify(code=500, msg='删除失败，请稍后重试')


@bp.route('/api/admin/infos')
@require_admin
def admin_list_infos():
    """管理员：获取所有信息条目（带分类名）。

    Returns:
        Response: JSON ``{"code": int, "data": list[dict]}``，
            每条含 id / title / content / cate_id / category。
    """
    try:
        with get_db() as db:
            rows = db.execute(
                'SELECT i.id, i.title, i.content, i.cate_id, '
                'c.name AS category '
                'FROM infos i JOIN categories c ON i.cate_id = c.id '
                'ORDER BY i.id DESC'
            ).fetchall()
            return jsonify(code=200, data=[dict(r) for r in rows])
    except Exception as e:
        logger.error(f"管理员获取信息列表错误: {e}")
        return jsonify(code=500, data=[])


@bp.route('/api/admin/infos', methods=['POST'])
@require_admin
def admin_add_info():
    """管理员：新增信息条目。

    表单参数：
        - title: 标题（必填，最长 200）。
        - content: 内容（必填，最长 5000）。
        - cate_id: 分类 ID（必填，必须存在于 categories 表）。

    Returns:
        Response: JSON ``{"code": int, "msg": str}``，
            校验失败 400 / 分类不存在 400 / 成功 200。
    """
    title = request.form.get('title', '').strip()
    content = request.form.get('content', '').strip()
    cate_id_raw = request.form.get('cate_id', '').strip()

    is_valid, msg = validate_content(title, 200)
    if not is_valid:
        return jsonify(code=400, msg=f"标题{msg}")
    is_valid, msg = validate_content(content, 5000)
    if not is_valid:
        return jsonify(code=400, msg=f"内容{msg}")
    if not cate_id_raw:
        return jsonify(code=400, msg='请选择分类')
    try:
        cate_id = int(cate_id_raw)
    except (TypeError, ValueError):
        return jsonify(code=400, msg='分类参数错误')

    try:
        with get_db() as db:
            cate = db.execute(
                'SELECT id FROM categories WHERE id=?', (cate_id,)
            ).fetchone()
            if cate is None:
                return jsonify(code=400, msg='分类不存在')
            db.execute(
                'INSERT INTO infos (cate_id, title, content) VALUES (?,?,?)',
                (cate_id, title, content)
            )
            db.commit()
            logger.info(
                f"管理员 {session.get('username')} 新增信息条目: {title}"
            )
            return jsonify(code=200, msg='新增成功')
    except Exception as e:
        logger.error(f"管理员新增信息错误: {e}")
        return jsonify(code=500, msg='新增失败，请稍后重试')


@bp.route('/api/admin/infos/<int:info_id>/update', methods=['POST'])
@require_admin
def admin_update_info(info_id):
    """管理员：编辑信息条目。

    Args:
        info_id (int): 信息条目 ID。

    表单参数同 ``admin_add_info``。
    """
    title = request.form.get('title', '').strip()
    content = request.form.get('content', '').strip()
    cate_id_raw = request.form.get('cate_id', '').strip()

    is_valid, msg = validate_content(title, 200)
    if not is_valid:
        return jsonify(code=400, msg=f"标题{msg}")
    is_valid, msg = validate_content(content, 5000)
    if not is_valid:
        return jsonify(code=400, msg=f"内容{msg}")
    if not cate_id_raw:
        return jsonify(code=400, msg='请选择分类')
    try:
        cate_id = int(cate_id_raw)
    except (TypeError, ValueError):
        return jsonify(code=400, msg='分类参数错误')

    try:
        with get_db() as db:
            exists = db.execute(
                'SELECT id FROM infos WHERE id=?', (info_id,)
            ).fetchone()
            if exists is None:
                return jsonify(code=404, msg='信息条目不存在')
            cate = db.execute(
                'SELECT id FROM categories WHERE id=?', (cate_id,)
            ).fetchone()
            if cate is None:
                return jsonify(code=400, msg='分类不存在')
            db.execute(
                'UPDATE infos SET cate_id=?, title=?, content=? WHERE id=?',
                (cate_id, title, content, info_id)
            )
            db.commit()
            logger.info(
                f"管理员 {session.get('username')} 更新信息条目 {info_id}"
            )
            return jsonify(code=200, msg='更新成功')
    except Exception as e:
        logger.error(f"管理员更新信息错误: {e}")
        return jsonify(code=500, msg='更新失败，请稍后重试')


@bp.route('/api/admin/infos/<int:info_id>/delete', methods=['POST'])
@require_admin
def admin_delete_info(info_id):
    """管理员：删除信息条目。

    Args:
        info_id (int): 信息条目 ID。

    Returns:
        Response: JSON ``{"code": int, "msg": str}``，
            不存在 404 / 成功 200。
    """
    try:
        with get_db() as db:
            exists = db.execute(
                'SELECT id FROM infos WHERE id=?', (info_id,)
            ).fetchone()
            if exists is None:
                return jsonify(code=404, msg='信息条目不存在')
            db.execute('DELETE FROM infos WHERE id=?', (info_id,))
            db.commit()
            logger.info(
                f"管理员 {session.get('username')} 删除信息条目 {info_id}"
            )
            return jsonify(code=200, msg='删除成功')
    except Exception as e:
        logger.error(f"管理员删除信息错误: {e}")
        return jsonify(code=500, msg='删除失败，请稍后重试')


@bp.route('/api/admin/users')
@require_admin
def admin_list_users():
    """管理员：获取用户列表（不含密码），含发帖数、检测数。

    Returns:
        Response: JSON ``{"code": int, "data": list[dict]}``，
            每条含 id / username / student_id / college / major /
            is_admin / created_at / post_count / detect_count。
    """
    try:
        with get_db() as db:
            rows = db.execute(
                'SELECT u.id, u.username, u.student_id, u.college, u.major, '
                'u.is_admin, u.created_at, '
                '(SELECT COUNT(*) FROM posts WHERE user_id=u.id) AS post_count, '
                '(SELECT COUNT(*) FROM maze_detect WHERE user_id=u.id) AS detect_count '
                'FROM users u '
                'ORDER BY u.id ASC'
            ).fetchall()
            return jsonify(code=200, data=[dict(r) for r in rows])
    except Exception as e:
        logger.error(f"管理员获取用户列表错误: {e}")
        return jsonify(code=500, data=[])


@bp.route('/api/admin/feedbacks')
@require_admin
def admin_list_feedbacks():
    """管理员：获取所有用户反馈（带用户名）。

    Returns:
        Response: JSON ``{"code": int, "data": list[dict]}``，
            每条含 id / username / content / contact / status / create_time。
    """
    try:
        with get_db() as db:
            rows = db.execute(
                'SELECT f.id, u.username, f.content, f.contact, '
                'f.status, f.create_time '
                'FROM feedback f JOIN users u ON f.user_id = u.id '
                'ORDER BY f.id DESC'
            ).fetchall()
            return jsonify(code=200, data=[dict(r) for r in rows])
    except Exception as e:
        logger.error(f"管理员获取反馈列表错误: {e}")
        return jsonify(code=500, data=[])


@bp.route('/api/admin/feedbacks/<int:fb_id>/resolve', methods=['POST'])
@require_admin
def admin_resolve_feedback(fb_id):
    """管理员：标记反馈为已处理（status='resolved'）。

    Args:
        fb_id (int): 反馈 ID。

    Returns:
        Response: JSON ``{"code": int, "msg": str}``，
            不存在 404 / 成功 200。
    """
    try:
        with get_db() as db:
            exists = db.execute(
                'SELECT id FROM feedback WHERE id=?', (fb_id,)
            ).fetchone()
            if exists is None:
                return jsonify(code=404, msg='反馈不存在')
            db.execute(
                "UPDATE feedback SET status='resolved' WHERE id=?",
                (fb_id,)
            )
            db.commit()
            logger.info(
                f"管理员 {session.get('username')} 标记反馈 {fb_id} 已处理"
            )
            return jsonify(code=200, msg='已标记为已处理')
    except Exception as e:
        logger.error(f"管理员标记反馈错误: {e}")
        return jsonify(code=500, msg='操作失败，请稍后重试')