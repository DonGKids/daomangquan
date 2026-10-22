function toggleLike() {
    if (!LOGGED_IN) {
        showToast('请先登录后再点赞', 'error');
        setTimeout(() => location.href = '/login', 1000);
        return;
    }
    api.post(`/api/posts/${POST_ID}/like`, {}, d => {
        if (d.code === 200) {
            const icon = document.getElementById('like-icon');
            const count = document.getElementById('like-count');
            let n = parseInt(count.textContent) || 0;
            if (d.liked) {
                icon.textContent = '❤️';
                count.textContent = n + 1;
                showToast('点赞成功', 'success');
            } else {
                icon.textContent = '🤍';
                count.textContent = n - 1;
                showToast('已取消点赞', 'info');
            }
        } else {
            showToast(d.msg, 'error');
        }
    });
}

function deletePost() {
    if (!confirm('确定删除这篇帖子吗？删除后无法恢复，相关评论和点赞也会一并删除。')) return;
    api.post(`/api/posts/${POST_ID}/delete`, {}, d => {
        if (d.code === 200) {
            showToast('删除成功，正在跳转...', 'success');
            setTimeout(() => location.href = '/forum', 1000);
        } else {
            showToast(d.msg, 'error');
        }
    });
}

function escapeHtml(s) {
    if (s == null) return '';
    return String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function loadComments() {
    api.get(`/api/posts/${POST_ID}/comments`, d => {
        const list = document.getElementById('comment-list');
        const counter = document.getElementById('comment-count');
        if (d.code !== 200) {
            list.innerHTML = '<p style="color:#ef4444;text-align:center;">加载失败</p>';
            return;
        }
        const items = d.data || [];
        counter.textContent = `(${items.length})`;
        if (items.length === 0) {
            list.innerHTML = '<p style="color:var(--text-light);text-align:center;padding:20px 0;">还没有评论，来发表第一条吧 →</p>';
            return;
        }
        list.innerHTML = items.map(c => `
            <div class="list-item">
                <div style="display:flex;justify-content:space-between;align-items:start;gap:12px;margin-bottom:6px;">
                    <strong style="color:var(--primary);">${escapeHtml(c.author)}</strong>
                    <span style="color:var(--text-light);font-size:12px;white-space:nowrap;">${escapeHtml(c.create_time ? c.create_time.substring(0,19) : '')}</span>
                </div>
                <p style="white-space:pre-wrap;">${escapeHtml(c.content)}</p>
            </div>
        `).join('');
    }, false);
}

function submitComment() {
    const content = document.getElementById('comment-content').value.trim();
    if (!content) {
        showToast('请输入评论内容', 'error');
        return;
    }
    if (content.length > 500) {
        showToast('评论不能超过500字', 'error');
        return;
    }
    api.post(`/api/posts/${POST_ID}/comments`, { content: content }, d => {
        if (d.code === 200) {
            showToast(d.msg, 'success');
            document.getElementById('comment-content').value = '';
            loadComments();
        } else {
            showToast(d.msg, 'error');
        }
    });
}

window.addEventListener('load', function() { loadComments(); });
