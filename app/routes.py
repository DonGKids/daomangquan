from flask import Blueprint, render_template, request, jsonify, redirect, session
from app.models import get_db
from werkzeug.security import check_password_hash, generate_password_hash
import json
import logging
import re

bp = Blueprint('main', __name__)
logger = logging.getLogger(__name__)

# 输入验证规则
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
    """从用户输入文本提取命中的迷茫关键词。
    Returns:
        matched_words: list[str] 命中的关键词（去重保序）
        matched_categories: list[str] 命中的分类名（去重）
        mood_words: list[str] 命中的情绪词
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
    """根据命中分类从 infos 表生成推荐内容。
    若无任何命中，返回每个分类各 1 条作为通用推荐。
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
    """验证用户名格式"""
    if not username:
        return False, "用户名不能为空"
    if len(username) < USERNAME_MIN_LEN or len(username) > USERNAME_MAX_LEN:
        return False, f"用户名长度必须在{USERNAME_MIN_LEN}-{USERNAME_MAX_LEN}个字符之间"
    if not re.match(r'^[\u4e00-\u9fa5a-zA-Z0-9_]+$', username):
        return False, "用户名只能包含中文、英文、数字和下划线"
    return True, ""


def validate_password(password):
    """验证密码强度"""
    if not password:
        return False, "密码不能为空"
    if len(password) < PASSWORD_MIN_LEN:
        return False, f"密码长度至少{PASSWORD_MIN_LEN}个字符"
    return True, ""


def validate_content(content, max_len=CONTENT_MAX_LEN):
    """验证内容"""
    if not content or not content.strip():
        return False, "内容不能为空"
    if len(content) > max_len:
        return False, f"内容长度不能超过{max_len}个字符"
    return True, ""


# 首页
@bp.route('/')
def index():
    """首页：展示 Hero + 平台统计 + 核心功能入口 + 个性化推荐 + 信息库分类 + 最新讨论。"""
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
                    import json
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
                db.execute(
                    'INSERT INTO users (username, password, student_id, college, major) VALUES (?,?,?,?,?)',
                    (username, hashed_password, student_id, college, major)
                )
                db.commit()
                logger.info(f"用户 {username} 注册成功")
                return jsonify(code=200, msg='注册成功')
        except Exception as e:
            logger.error(f"注册错误: {e}")
            return jsonify(code=500, msg='注册失败，请稍后重试')
    
    return render_template('register.html')


@bp.route('/logout')
def logout():
    if 'user_id' not in session:
        return redirect('/')
    username = session.get('username', 'Unknown')
    session.clear()
    logger.info(f"用户 {username} 已退出登录")
    return redirect('/')


@bp.route('/maze')
def maze():
    if 'user_id' not in session:
        return redirect('/login')
    return render_template('maze.html')


@bp.route('/info')
def info():
    return render_template('info.html')


@bp.route('/forum')
def forum():
    return render_template('forum.html')


@bp.route('/profile')
def profile():
    """个人中心：展示用户信息、统计、检测历史、发帖历史。"""
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
    无参数：返回全部信息（带分类名）。
    ?category=升学就业：按分类名筛选。
    ?cate_id=2：按分类 id 筛选。
    ?q=考研：按关键词模糊搜索 title 和 content（可与分类叠加）。
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
    ?page=1&limit=10：分页参数，默认第 1 页每页 10 条。
    返回 {code, data, total, page, limit, total_pages}
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
            import math
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
    """帖子详情页：展示原帖内容 + 评论列表 + 评论输入框。"""
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
    """点赞 / 取消点赞（toggle）。需登录。"""
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
    """删除帖子。仅作者本人可删。级联删除评论和点赞。"""
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
    """获取某帖子的评论列表（按时间正序）。"""
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
    """发表评论。需登录。"""
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
    """提交反馈。需登录。content 必填（最多 500 字），contact 选填（最多 100 字）。"""
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
    """查看我的反馈历史（最近 20 条，按时间倒序）。"""
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