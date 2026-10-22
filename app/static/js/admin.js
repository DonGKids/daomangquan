// 管理后台前端逻辑：标签切换 + 论坛/信息库/用户/反馈的 CRUD
// 依赖 base.js 提供的全局 api / post / showToast 工具

let POSTS_PAGE = 1;
const POSTS_LIMIT = 10;
let editingInfoId = null;
// 缓存信息列表，便于点击编辑时按 id 取出对象，避免在 HTML 属性中塞 JSON
let infosCache = [];

// ─── 通用工具 ───

function escapeHtml(s) {
    if (s == null) return '';
    return String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function fmtTime(t) {
    if (!t) return '未知';
    return String(t).substring(0, 19);
}

function fmtDate(t) {
    if (!t) return '未知';
    return String(t).substring(0, 10);
}

// ─── Tab 切换 ───

function switchTab(name) {
    document.querySelectorAll('.admin-tab').forEach(el => {
        el.classList.toggle('active', el.dataset.tab === name);
    });
    document.querySelectorAll('.admin-panel').forEach(el => {
        el.classList.toggle('active', el.id === 'panel-' + name);
    });
    // 切换到对应 tab 时懒加载数据
    if (name === 'posts') loadAdminPosts(1);
    else if (name === 'infos') loadAdminInfos();
    else if (name === 'users') loadAdminUsers();
    else if (name === 'feedbacks') loadAdminFeedbacks();
}

// ─── 论坛管理 ───

function loadAdminPosts(page) {
    page = page || 1;
    POSTS_PAGE = page;
    const wrap = document.getElementById('posts-table-wrap');
    wrap.innerHTML = '<p class="admin-empty">正在加载...</p>';
    api.get(`/api/admin/posts?page=${page}&limit=${POSTS_LIMIT}`, d => {
        if (d.code !== 200) {
            wrap.innerHTML = `<p class="admin-empty" style="color:#ef4444;">加载失败：${escapeHtml(d.msg || '服务器错误')}</p>`;
            document.getElementById('posts-pagination').innerHTML = '';
            return;
        }
        if (!d.data || d.data.length === 0) {
            wrap.innerHTML = '<p class="admin-empty">暂无帖子</p>';
            document.getElementById('posts-pagination').innerHTML = '';
            return;
        }
        let html = '<table class="admin-table"><thead><tr>'
            + '<th>ID</th><th>标题</th><th>作者</th><th>评论</th>'
            + '<th>点赞</th><th>发布时间</th><th>操作</th>'
            + '</tr></thead><tbody>';
        d.data.forEach(p => {
            const title = escapeHtml(p.title);
            const excerpt = title.length > 40 ? title.substring(0, 40) + '…' : title;
            html += `<tr>
                <td>${p.id}</td>
                <td title="${escapeHtml(p.title)}"><a href="/post/${p.id}" target="_blank">${excerpt}</a></td>
                <td>${escapeHtml(p.author)}</td>
                <td>${p.reply_count || 0}</td>
                <td>${p.like_count || 0}</td>
                <td>${fmtTime(p.create_time)}</td>
                <td class="actions">
                    <button class="btn-delete" onclick="deletePost(${p.id})">🗑️ 删除</button>
                </td>
            </tr>`;
        });
        html += '</tbody></table>';
        wrap.innerHTML = html;
        renderPostsPagination(d.page, d.total_pages);
    }, false);
}

function renderPostsPagination(current, total) {
    const el = document.getElementById('posts-pagination');
    if (!total || total <= 1) { el.innerHTML = ''; return; }
    let html = '';
    html += `<button ${current > 1 ? '' : 'disabled'} onclick="loadAdminPosts(${current - 1})">上一页</button>`;
    for (let i = 1; i <= total; i++) {
        if (i === current) {
            html += `<button class="active" disabled>${i}</button>`;
        } else if (Math.abs(i - current) <= 3 || i === 1 || i === total) {
            html += `<button onclick="loadAdminPosts(${i})">${i}</button>`;
        } else if (Math.abs(i - current) === 4) {
            html += '<span style="color:var(--text-light);">…</span>';
        }
    }
    html += `<button ${current < total ? '' : 'disabled'} onclick="loadAdminPosts(${current + 1})">下一页</button>`;
    el.innerHTML = html;
}

function deletePost(postId) {
    if (!confirm(`确定删除帖子 #${postId} 吗？相关评论和点赞也会一并删除。`)) return;
    api.post(`/api/admin/posts/${postId}/delete`, {}, d => {
        if (d.code === 200) {
            showToast('删除成功', 'success');
            loadAdminPosts(POSTS_PAGE);
        } else {
            showToast(d.msg || '删除失败', 'error');
        }
    });
}

// ─── 信息库管理 ───

function loadAdminInfos() {
    const wrap = document.getElementById('infos-table-wrap');
    wrap.innerHTML = '<p class="admin-empty">正在加载...</p>';
    api.get('/api/admin/infos', d => {
        if (d.code !== 200) {
            wrap.innerHTML = `<p class="admin-empty" style="color:#ef4444;">加载失败：${escapeHtml(d.msg || '服务器错误')}</p>`;
            return;
        }
        if (!d.data || d.data.length === 0) {
            wrap.innerHTML = '<p class="admin-empty">暂无信息条目</p>';
            return;
        }
        infosCache = d.data;
        let html = '<table class="admin-table"><thead><tr>'
            + '<th>ID</th><th>标题</th><th>分类</th><th>操作</th>'
            + '</tr></thead><tbody>';
        d.data.forEach(it => {
            const title = escapeHtml(it.title);
            const excerpt = title.length > 40 ? title.substring(0, 40) + '…' : title;
            html += `<tr>
                <td>${it.id}</td>
                <td title="${escapeHtml(it.title)}">${excerpt}</td>
                <td>${escapeHtml(it.category || '未分类')}</td>
                <td class="actions">
                    <button class="btn-edit" onclick="editInfo(${it.id})">✏️ 编辑</button>
                    <button class="btn-delete" onclick="deleteInfo(${it.id})">🗑️ 删除</button>
                </td>
            </tr>`;
        });
        html += '</tbody></table>';
        wrap.innerHTML = html;
    }, false);
}

function loadCategories() {
    // 默认 4 个分类（与 models.py 的 init_database 保持一致）
    // 后续若 categories 表扩展为可配置，应改用专门的 /api/categories 接口
    const select = document.getElementById('info-cate-id');
    const defaults = [
        { id: 1, name: '生活常识' },
        { id: 2, name: '升学就业' },
        { id: 3, name: '法律知识' },
        { id: 4, name: '创业资讯' }
    ];
    let html = '<option value="">请选择分类</option>';
    defaults.forEach(c => {
        html += `<option value="${c.id}">${escapeHtml(c.name)}</option>`;
    });
    select.innerHTML = html;
}

function submitInfo() {
    const cateId = document.getElementById('info-cate-id').value;
    const title = document.getElementById('info-title').value.trim();
    const content = document.getElementById('info-content').value.trim();

    if (!cateId) { showToast('请选择分类', 'error'); return; }
    if (!title) { showToast('请输入标题', 'error'); return; }
    if (title.length > 200) { showToast('标题不能超过 200 字', 'error'); return; }
    if (!content) { showToast('请输入内容', 'error'); return; }
    if (content.length > 5000) { showToast('内容不能超过 5000 字', 'error'); return; }

    const payload = { title, content, cate_id: cateId };
    if (editingInfoId) {
        api.post(`/api/admin/infos/${editingInfoId}/update`, payload, d => {
            if (d.code === 200) {
                showToast('更新成功', 'success');
                cancelEditInfo();
                loadAdminInfos();
            } else {
                showToast(d.msg || '更新失败', 'error');
            }
        });
    } else {
        api.post('/api/admin/infos', payload, d => {
            if (d.code === 200) {
                showToast('新增成功', 'success');
                document.getElementById('info-title').value = '';
                document.getElementById('info-content').value = '';
                loadAdminInfos();
            } else {
                showToast(d.msg || '新增失败', 'error');
            }
        });
    }
}

function editInfo(id) {
    const data = infosCache.find(x => x.id === id);
    if (!data) {
        showToast('未找到该条目，请刷新重试', 'error');
        return;
    }
    editingInfoId = id;
    document.getElementById('info-edit-banner').style.display = 'flex';
    document.getElementById('info-edit-id').textContent = id;
    document.getElementById('info-cate-id').value = data.cate_id;
    document.getElementById('info-title').value = data.title;
    document.getElementById('info-content').value = data.content;
    document.getElementById('info-submit-btn').textContent = '保存修改';
    document.getElementById('panel-infos').scrollIntoView({ behavior: 'smooth' });
}

function cancelEditInfo() {
    editingInfoId = null;
    document.getElementById('info-edit-banner').style.display = 'none';
    document.getElementById('info-title').value = '';
    document.getElementById('info-content').value = '';
    document.getElementById('info-cate-id').value = '';
    document.getElementById('info-submit-btn').textContent = '新增信息';
}

function deleteInfo(infoId) {
    if (!confirm(`确定删除信息条目 #${infoId} 吗？`)) return;
    api.post(`/api/admin/infos/${infoId}/delete`, {}, d => {
        if (d.code === 200) {
            showToast('删除成功', 'success');
            if (editingInfoId === infoId) cancelEditInfo();
            loadAdminInfos();
        } else {
            showToast(d.msg || '删除失败', 'error');
        }
    });
}

// ─── 用户管理 ───

function loadAdminUsers() {
    const wrap = document.getElementById('users-table-wrap');
    wrap.innerHTML = '<p class="admin-empty">正在加载...</p>';
    api.get('/api/admin/users', d => {
        if (d.code !== 200) {
            wrap.innerHTML = `<p class="admin-empty" style="color:#ef4444;">加载失败：${escapeHtml(d.msg || '服务器错误')}</p>`;
            return;
        }
        if (!d.data || d.data.length === 0) {
            wrap.innerHTML = '<p class="admin-empty">暂无用户</p>';
            return;
        }
        let html = '<table class="admin-table"><thead><tr>'
            + '<th>ID</th><th>用户名</th><th>学号</th><th>学院</th>'
            + '<th>专业</th><th>角色</th><th>发帖数</th><th>检测数</th><th>注册时间</th>'
            + '</tr></thead><tbody>';
        d.data.forEach(u => {
            const role = u.is_admin
                ? '<span class="admin-status-badge status-resolved">管理员</span>'
                : '<span class="admin-status-badge status-pending">普通用户</span>';
            html += `<tr>
                <td>${u.id}</td>
                <td>${escapeHtml(u.username)}</td>
                <td>${escapeHtml(u.student_id || '-')}</td>
                <td>${escapeHtml(u.college || '-')}</td>
                <td>${escapeHtml(u.major || '-')}</td>
                <td>${role}</td>
                <td>${u.post_count || 0}</td>
                <td>${u.detect_count || 0}</td>
                <td>${fmtDate(u.created_at)}</td>
            </tr>`;
        });
        html += '</tbody></table>';
        wrap.innerHTML = html;
    }, false);
}

// ─── 反馈管理 ───

function loadAdminFeedbacks() {
    const wrap = document.getElementById('feedbacks-table-wrap');
    wrap.innerHTML = '<p class="admin-empty">正在加载...</p>';
    api.get('/api/admin/feedbacks', d => {
        if (d.code !== 200) {
            wrap.innerHTML = `<p class="admin-empty" style="color:#ef4444;">加载失败：${escapeHtml(d.msg || '服务器错误')}</p>`;
            return;
        }
        if (!d.data || d.data.length === 0) {
            wrap.innerHTML = '<p class="admin-empty">暂无反馈</p>';
            return;
        }
        let html = '<table class="admin-table"><thead><tr>'
            + '<th>ID</th><th>用户名</th><th>内容</th><th>联系方式</th>'
            + '<th>状态</th><th>提交时间</th><th>操作</th>'
            + '</tr></thead><tbody>';
        d.data.forEach(f => {
            const content = escapeHtml(f.content || '');
            const excerpt = content.length > 60 ? content.substring(0, 60) + '…' : content;
            const statusBadge = f.status === 'resolved'
                ? '<span class="admin-status-badge status-resolved">已处理</span>'
                : '<span class="admin-status-badge status-pending">待处理</span>';
            const action = f.status === 'resolved'
                ? '<span style="color:var(--text-light);font-size:12px;">已处理</span>'
                : `<button class="btn-resolve" onclick="resolveFeedback(${f.id})">标记已处理</button>`;
            html += `<tr>
                <td>${f.id}</td>
                <td>${escapeHtml(f.username || '-')}</td>
                <td title="${escapeHtml(f.content || '')}">${excerpt}</td>
                <td>${escapeHtml(f.contact || '-')}</td>
                <td>${statusBadge}</td>
                <td>${fmtTime(f.create_time)}</td>
                <td class="actions">${action}</td>
            </tr>`;
        });
        html += '</tbody></table>';
        wrap.innerHTML = html;
    }, false);
}

function resolveFeedback(fbId) {
    if (!confirm(`确定将反馈 #${fbId} 标记为已处理吗？`)) return;
    api.post(`/api/admin/feedbacks/${fbId}/resolve`, {}, d => {
        if (d.code === 200) {
            showToast('已标记为已处理', 'success');
            loadAdminFeedbacks();
        } else {
            showToast(d.msg || '操作失败', 'error');
        }
    });
}

// ─── 初始化 ───

window.addEventListener('load', function() {
    loadCategories();
    loadAdminPosts(1);
});
