"""
导茫犬平台核心功能测试套件。

覆盖模块：
    - 用户注册与登录
    - 迷茫检测与关键词提取
    - 信息库分类查询与搜索
    - 论坛帖子发布、评论、点赞、删除
    - 用户反馈提交
    - 首页统计与个性化推荐

测试约定：
    - 使用 Flask test_client 模拟 HTTP 请求，不启动真实服务器。
    - 每个测试在独立的 test_daomangquan.db 上运行（由根目录 conftest.py 重置）。
    - 业务错误统一以 JSON ``{"code": 4xx, "msg": ...}`` 返回，HTTP 状态码仍为 200，
      因此断言以 ``resp.get_json()['code']`` 为准。

运行方式：
    pytest tests/ -v
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest  # noqa: E402

from app import create_app  # noqa: E402
from app.models import get_db  # noqa: E402


def _seed_infos(app):
    """向测试库插入 5 条信息库种子数据，覆盖 4 个分类。

    分布：
        - 生活常识 (cate_id=1)：1 条
        - 升学就业 (cate_id=2)：2 条
        - 法律知识 (cate_id=3)：1 条
        - 创业资讯 (cate_id=4)：1 条
    """
    with app.app_context():
        with get_db() as db:
            db.execute(
                "INSERT INTO infos (cate_id, title, content) VALUES (?,?,?)",
                (1, "大学生医保参保指南", "介绍大学生医保参保流程与报销范围。")
            )
            db.execute(
                "INSERT INTO infos (cate_id, title, content) VALUES (?,?,?)",
                (2, "考研时间节点与备考规划", "考研报名、初试、复试时间安排。")
            )
            db.execute(
                "INSERT INTO infos (cate_id, title, content) VALUES (?,?,?)",
                (2, "考公备考建议", "公务员考试科目与备考资料。")
            )
            db.execute(
                "INSERT INTO infos (cate_id, title, content) VALUES (?,?,?)",
                (3, "试用期劳动权益保护", "试用期内的劳动法保护与维权途径。")
            )
            db.execute(
                "INSERT INTO infos (cate_id, title, content) VALUES (?,?,?)",
                (4, "大学生创业扶持政策", "大学生创业可申请的补贴与孵化资源。")
            )
            db.commit()


@pytest.fixture
def app():
    """创建测试用 Flask 应用实例：每个测试一个全新空库 + 种子数据。"""
    app = create_app()
    app.config['TESTING'] = True
    _seed_infos(app)
    yield app


@pytest.fixture
def client(app):
    """创建未登录的测试客户端。"""
    return app.test_client()


@pytest.fixture
def auth_client(app):
    """创建已注册并登录的测试客户端（用户名 testuser）。

    注册后不退出直接登录，session 中保留 user_id / username，
    适用于所有需要登录态的接口测试。
    """
    client = app.test_client()
    client.post('/register', data={
        'username': 'testuser',
        'password': 'test123456',
        'student_id': '2024001',
        'college': '测试学院',
        'major': '测试专业'
    })
    client.post('/login', data={
        'username': 'testuser',
        'password': 'test123456'
    })
    return client


# ============================================================
# 1. 用户注册
# ============================================================

def test_register_success(client):
    """正常注册：合法用户名 + 合法密码应返回 code=200。"""
    resp = client.post('/register', data={
        'username': 'newuser1',
        'password': 'pass123456',
        'student_id': '2024999',
        'college': '计算机学院',
        'major': '软件工程'
    })
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['code'] == 200
    assert body['msg'] == '注册成功'


def test_register_duplicate(client):
    """重复用户名注册：第二次应返回 code=400 且提示已存在。"""
    client.post('/register', data={
        'username': 'dupuser',
        'password': 'pass123456'
    })
    resp = client.post('/register', data={
        'username': 'dupuser',
        'password': 'pass123456'
    })
    body = resp.get_json()
    assert body['code'] == 400
    assert '已存在' in body['msg']


def test_register_short_username(client):
    """用户名长度不足 3 应被拒：返回 code=400。"""
    resp = client.post('/register', data={
        'username': 'ab',  # 仅 2 个字符，低于 USERNAME_MIN_LEN=3
        'password': 'pass123456'
    })
    assert resp.get_json()['code'] == 400


def test_register_short_password(client):
    """密码长度不足 6 应被拒：返回 code=400。"""
    resp = client.post('/register', data={
        'username': 'shortpw',
        'password': '12345'  # 仅 5 个字符，低于 PASSWORD_MIN_LEN=6
    })
    assert resp.get_json()['code'] == 400


# ============================================================
# 2. 用户登录
# ============================================================

def test_login_success(client):
    """正常登录：已注册用户应返回 code=200 '登录成功'。"""
    client.post('/register', data={
        'username': 'loginuser',
        'password': 'pass123456'
    })
    resp = client.post('/login', data={
        'username': 'loginuser',
        'password': 'pass123456'
    })
    body = resp.get_json()
    assert body['code'] == 200
    assert body['msg'] == '登录成功'


def test_login_wrong_password(client):
    """密码错误：应返回 code=400 '账号或密码错误'。"""
    client.post('/register', data={
        'username': 'loginuser',
        'password': 'pass123456'
    })
    resp = client.post('/login', data={
        'username': 'loginuser',
        'password': 'wrongpassword'
    })
    body = resp.get_json()
    assert body['code'] == 400
    assert '账号或密码错误' in body['msg']


def test_login_nonexistent(client):
    """登录不存在的用户：应返回 code=400。"""
    resp = client.post('/login', data={
        'username': 'nosuchuser999',
        'password': 'pass123456'
    })
    body = resp.get_json()
    assert body['code'] == 400


# ============================================================
# 3. 迷茫检测
# ============================================================

def test_maze_requires_login(client):
    """未登录提交迷茫检测：应返回 code=401。"""
    resp = client.post('/api/maze', data={'content': '我考研压力很大'})
    assert resp.get_json()['code'] == 401


def test_maze_with_keywords(auth_client):
    """提交含关键词文本：应返回 keywords、mood 与命中的分类推荐。"""
    resp = auth_client.post('/api/maze', data={
        'content': '最近在准备考研，租房也很贵，让我很焦虑'
    })
    body = resp.get_json()
    assert body['code'] == 200
    data = body['data']
    # 关键词命中
    assert '考研' in data['keywords']
    assert '租房' in data['keywords']
    # 情绪词命中
    assert '焦虑' in data['mood']
    # 推荐中应包含命中的两个分类
    rec_cats = [r['category'] for r in data['recommendations']]
    assert '升学就业' in rec_cats
    assert '生活常识' in rec_cats


def test_maze_empty_content(auth_client):
    """空内容应被拒：返回 code=400。"""
    resp = auth_client.post('/api/maze', data={'content': ''})
    body = resp.get_json()
    assert body['code'] == 400


def test_maze_no_keywords(auth_client):
    """无关键词命中：应返回 code=200 + 默认推荐。"""
    resp = auth_client.post('/api/maze', data={
        'content': '今天天气真不错，心情很好。'
    })
    body = resp.get_json()
    assert body['code'] == 200
    assert body['data']['keywords'] == []
    # build_recommendations 在无命中时返回前 4 条作为默认推荐
    assert isinstance(body['data']['recommendations'], list)
    assert len(body['data']['recommendations']) >= 1


# ============================================================
# 4. 信息库
# ============================================================

def test_info_list(client):
    """获取全部信息：应返回 5 条种子数据。"""
    resp = client.get('/api/info')
    body = resp.get_json()
    assert body['code'] == 200
    assert len(body['data']) == 5


def test_info_by_category(client):
    """按分类筛选：升学就业应返回 2 条且分类名一致。"""
    resp = client.get('/api/info?category=升学就业')
    body = resp.get_json()
    assert body['code'] == 200
    assert len(body['data']) == 2
    for item in body['data']:
        assert item['category'] == '升学就业'


def test_info_search(client):
    """关键词搜索：'考研' 应命中相关条目。"""
    resp = client.get('/api/info?q=考研')
    body = resp.get_json()
    assert body['code'] == 200
    assert len(body['data']) >= 1
    for item in body['data']:
        assert '考研' in item['title'] or '考研' in item['content']


def test_info_search_no_results(client):
    """搜索无结果：应返回空 data 列表。"""
    resp = client.get('/api/info?q=完全不存在的随机字符串XYZ123')
    body = resp.get_json()
    assert body['code'] == 200
    assert body['data'] == []


# ============================================================
# 5. 论坛帖子
# ============================================================

def test_post_requires_login(client):
    """未登录发帖：应返回 code=401。"""
    resp = client.post('/api/post', data={'title': '标题', 'content': '内容'})
    assert resp.get_json()['code'] == 401


def test_post_create_and_list(auth_client):
    """发帖后列表中应出现该帖。"""
    resp = auth_client.post('/api/post', data={
        'title': '测试标题',
        'content': '测试内容'
    })
    assert resp.get_json()['code'] == 200
    # 拉取列表验证
    resp = auth_client.get('/api/posts')
    body = resp.get_json()
    assert body['code'] == 200
    assert any(p['title'] == '测试标题' for p in body['data'])


def test_post_detail(auth_client):
    """帖子详情页：应返回 200 且页面包含标题。"""
    auth_client.post('/api/post', data={
        'title': '详情测试',
        'content': '正文内容'
    })
    posts = auth_client.get('/api/posts').get_json()['data']
    post_id = posts[0]['id']
    resp = auth_client.get(f'/post/{post_id}')
    assert resp.status_code == 200
    assert '详情测试' in resp.data.decode('utf-8')


def test_post_pagination(auth_client):
    """分页参数：limit=2 时应只返回 2 条且 total=3 / total_pages=2。"""
    # 创建 3 条帖子
    for i in range(3):
        auth_client.post('/api/post', data={
            'title': f'分页标题{i}',
            'content': '内容'
        })
    resp = auth_client.get('/api/posts?page=1&limit=2')
    body = resp.get_json()
    assert body['code'] == 200
    assert body['limit'] == 2
    assert len(body['data']) == 2
    assert body['total'] == 3
    assert body['total_pages'] == 2


# ============================================================
# 6. 评论
# ============================================================

def test_comment_requires_login(client):
    """未登录发评论：应返回 code=401。"""
    resp = client.post('/api/posts/1/comments', data={'content': '评论内容'})
    assert resp.get_json()['code'] == 401


def test_comment_create_and_list(auth_client):
    """发评论后列表中应出现该评论。"""
    # 先发帖，再评论
    auth_client.post('/api/post', data={
        'title': '有评论的帖',
        'content': '内容'
    })
    post_id = auth_client.get('/api/posts').get_json()['data'][0]['id']
    # 发评论
    resp = auth_client.post(f'/api/posts/{post_id}/comments', data={
        'content': '我的评论内容'
    })
    assert resp.get_json()['code'] == 200
    # 拉取评论列表
    resp = auth_client.get(f'/api/posts/{post_id}/comments')
    body = resp.get_json()
    assert body['code'] == 200
    assert any(c['content'] == '我的评论内容' for c in body['data'])


# ============================================================
# 7. 点赞
# ============================================================

def test_like_requires_login(client):
    """未登录点赞：应返回 code=401（先于帖子存在性检查）。"""
    resp = client.post('/api/posts/1/like')
    assert resp.get_json()['code'] == 401


def test_like_toggle(auth_client):
    """点赞 toggle：第一次 liked=True，第二次 liked=False。"""
    auth_client.post('/api/post', data={
        'title': '点赞测试',
        'content': '内容'
    })
    post_id = auth_client.get('/api/posts').get_json()['data'][0]['id']
    # 第一次点赞
    resp = auth_client.post(f'/api/posts/{post_id}/like')
    body = resp.get_json()
    assert body['code'] == 200
    assert body['liked'] is True
    # 第二次取消
    resp = auth_client.post(f'/api/posts/{post_id}/like')
    body = resp.get_json()
    assert body['code'] == 200
    assert body['liked'] is False


# ============================================================
# 8. 删除帖子
# ============================================================

def test_delete_requires_owner(client):
    """非作者删除帖子：应返回 code=403。"""
    # 用户 A 注册、登录、发帖
    client.post('/register', data={'username': 'userA', 'password': 'pass123456'})
    client.post('/login', data={'username': 'userA', 'password': 'pass123456'})
    client.post('/api/post', data={'title': 'A的帖子', 'content': '内容'})
    post_id = client.get('/api/posts').get_json()['data'][0]['id']
    # 退出 A
    client.get('/logout')
    # 用户 B 注册、登录
    client.post('/register', data={'username': 'userB', 'password': 'pass123456'})
    client.post('/login', data={'username': 'userB', 'password': 'pass123456'})
    # B 尝试删除 A 的帖子
    resp = client.post(f'/api/posts/{post_id}/delete')
    body = resp.get_json()
    assert body['code'] == 403


def test_delete_post(auth_client):
    """作者删除自己的帖子：应返回 code=200 且列表中不再出现。"""
    auth_client.post('/api/post', data={
        'title': '待删除帖子',
        'content': '内容'
    })
    post_id = auth_client.get('/api/posts').get_json()['data'][0]['id']
    resp = auth_client.post(f'/api/posts/{post_id}/delete')
    assert resp.get_json()['code'] == 200
    # 验证已删除
    posts = auth_client.get('/api/posts').get_json()['data']
    assert not any(p['id'] == post_id for p in posts)


# ============================================================
# 9. 首页
# ============================================================

def test_index_loads(client):
    """首页：应返回 HTTP 200 且包含品牌名 '导茫犬'。"""
    resp = client.get('/')
    assert resp.status_code == 200
    assert '导茫犬' in resp.data.decode('utf-8')


def test_index_stats(client):
    """首页统计：HTML 中应包含 4 个统计标签文字。"""
    resp = client.get('/')
    html = resp.data.decode('utf-8')
    assert '注册用户' in html
    assert '信息库条目' in html
    assert '论坛帖子' in html
    assert '评论互动' in html


# ============================================================
# 10. 用户反馈
# ============================================================

def test_feedback_requires_login(client):
    """未登录提交反馈：应返回 code=401。"""
    resp = client.post('/api/feedback', data={'content': '反馈内容'})
    assert resp.get_json()['code'] == 401


def test_feedback_submit(auth_client):
    """提交反馈：应返回 code=200 且出现在我的反馈历史中。"""
    resp = auth_client.post('/api/feedback', data={
        'content': '我的反馈意见内容',
        'contact': 'test@example.com'
    })
    assert resp.get_json()['code'] == 200
    # 验证反馈已记录
    resp = auth_client.get('/api/feedback/mine')
    body = resp.get_json()
    assert body['code'] == 200
    assert any('反馈意见' in f['content'] for f in body['data'])


# ============================================================
# 11. 个人中心与会话
# ============================================================

def test_profile_requires_login(client):
    """未登录访问个人中心：应重定向到 /login（HTTP 302）。"""
    resp = client.get('/profile')
    assert resp.status_code == 302
    assert '/login' in resp.headers.get('Location', '')


def test_profile_loads(auth_client):
    """已登录访问个人中心：应返回 200 且页面包含用户名。"""
    resp = auth_client.get('/profile')
    assert resp.status_code == 200
    assert 'testuser' in resp.data.decode('utf-8')


def test_logout_clears_session(auth_client):
    """退出后 session 被清空，再发帖应返回 401。"""
    auth_client.get('/logout')
    resp = auth_client.post('/api/post', data={
        'title': '退出后发帖',
        'content': '不应成功'
    })
    assert resp.get_json()['code'] == 401


def test_maze_persists_in_profile(auth_client):
    """提交迷茫检测后，个人中心应展示检测历史。"""
    auth_client.post('/api/maze', data={
        'content': '考研压力大，租房也贵，让我焦虑'
    })
    resp = auth_client.get('/profile')
    html = resp.data.decode('utf-8')
    # 检测原文应出现在历史列表中
    assert '考研' in html


# ============================================================
# 12. 边界情况与错误处理
# ============================================================

def test_info_by_cate_id(client):
    """按 cate_id 筛选：cate_id=2 应返回 2 条升学就业条目。"""
    resp = client.get('/api/info?cate_id=2')
    body = resp.get_json()
    assert body['code'] == 200
    assert len(body['data']) == 2
    for item in body['data']:
        assert item['cate_id'] == 2


def test_post_detail_not_found(client):
    """访问不存在的帖子详情页：应返回错误提示。"""
    resp = client.get('/post/99999')
    assert resp.status_code == 200
    assert '不存在' in resp.data.decode('utf-8')


def test_comment_on_nonexistent_post(auth_client):
    """对不存在的帖子发评论：应返回 code=404。"""
    resp = auth_client.post('/api/posts/99999/comments', data={
        'content': '评论内容'
    })
    body = resp.get_json()
    assert body['code'] == 404


def test_like_nonexistent_post(auth_client):
    """对不存在的帖子点赞：应返回 code=404。"""
    resp = auth_client.post('/api/posts/99999/like')
    body = resp.get_json()
    assert body['code'] == 404


def test_delete_nonexistent_post(auth_client):
    """删除不存在的帖子：应返回 code=404。"""
    resp = auth_client.post('/api/posts/99999/delete')
    body = resp.get_json()
    assert body['code'] == 404


def test_feedback_too_long_contact(auth_client):
    """反馈联系方式超过 100 字：应返回 code=400。"""
    resp = auth_client.post('/api/feedback', data={
        'content': '正常的反馈内容',
        'contact': 'x' * 101  # 101 个字符，超过 100 上限
    })
    body = resp.get_json()
    assert body['code'] == 400
    assert '100' in body['msg']


def test_register_invalid_username_chars(client):
    """用户名含非法字符（@）：应返回 code=400。"""
    resp = client.post('/register', data={
        'username': 'bad@name',  # @ 不在允许字符集
        'password': 'pass123456'
    })
    assert resp.get_json()['code'] == 400


def test_post_empty_title(auth_client):
    """发帖标题为空：应返回 code=400。"""
    resp = auth_client.post('/api/post', data={
        'title': '',
        'content': '只有内容没有标题'
    })
    assert resp.get_json()['code'] == 400


def test_post_empty_content(auth_client):
    """发帖正文为空：应返回 code=400。"""
    resp = auth_client.post('/api/post', data={
        'title': '只有标题',
        'content': ''
    })
    assert resp.get_json()['code'] == 400


def test_comment_empty_content(auth_client):
    """发评论内容为空：应返回 code=400。"""
    auth_client.post('/api/post', data={
        'title': '用于评论的帖',
        'content': '内容'
    })
    post_id = auth_client.get('/api/posts').get_json()['data'][0]['id']
    resp = auth_client.post(f'/api/posts/{post_id}/comments', data={'content': ''})
    assert resp.get_json()['code'] == 400


def test_info_combined_filter(client):
    """分类 + 关键词组合筛选：升学就业 + '考公' 应只返回 1 条。"""
    resp = client.get('/api/info?category=升学就业&q=考公')
    body = resp.get_json()
    assert body['code'] == 200
    assert len(body['data']) == 1
    assert '考公' in body['data'][0]['title']


def test_feedback_history_empty(auth_client):
    """新登录用户无反馈时：feedback/mine 应返回空列表。"""
    resp = auth_client.get('/api/feedback/mine')
    body = resp.get_json()
    assert body['code'] == 200
    assert body['data'] == []


def test_posts_default_pagination(client):
    """无分页参数时：默认 page=1 / limit=10。"""
    resp = client.get('/api/posts')
    body = resp.get_json()
    assert body['code'] == 200
    assert body['page'] == 1
    assert body['limit'] == 10
