function detect() {
    const content = document.getElementById('content').value;
    if (!content.trim()) {
        showToast('请先描述你的困惑', 'error');
        return;
    }
    post('/api/maze', { content: content }, d => {
        showToast(d.msg, d.code === 200 ? 'success' : 'error');
        if (d.code === 200 && d.data) {
            renderResult(d.data);
        }
    });
}

function renderResult(data) {
    const resultDiv = document.getElementById('result');
    const kwSection = document.getElementById('kw-section');
    const recSection = document.getElementById('rec-section');

    // 关键词 + 情绪信号
    let kwHtml = '';
    if (data.keywords && data.keywords.length) {
        kwHtml += '<div style="margin-bottom:8px;"><strong style="color:var(--primary);">命中关键词</strong></div>';
        kwHtml += '<div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px;">';
        data.keywords.forEach(k => {
            kwHtml += `<span style="background:#dbeafe;color:#1e40af;padding:4px 12px;border-radius:999px;font-size:13px;">${escapeHtml(k)}</span>`;
        });
        kwHtml += '</div>';
    } else {
        kwHtml += '<p style="color:var(--text-light);margin-bottom:16px;">未识别到明确方向关键词，可尝试更具体描述困惑（如"考研""实习""合同"等）</p>';
    }
    if (data.mood && data.mood.length) {
        kwHtml += '<div style="margin-bottom:8px;"><strong style="color:#9a3412;">情绪信号</strong></div>';
        kwHtml += '<div style="display:flex;flex-wrap:wrap;gap:8px;">';
        data.mood.forEach(m => {
            kwHtml += `<span style="background:#ffedd5;color:#9a3412;padding:4px 12px;border-radius:999px;font-size:13px;">${escapeHtml(m)}</span>`;
        });
        kwHtml += '</div>';
    }
    kwSection.innerHTML = kwHtml;

    // 分类推荐
    let recHtml = '';
    if (data.recommendations && data.recommendations.length) {
        data.recommendations.forEach(rec => {
            recHtml += '<div class="card">';
            recHtml += `<h3 class="title">${escapeHtml(rec.category)}</h3>`;
            recHtml += `<p style="color:var(--text-light);font-size:13px;margin-bottom:12px;">${escapeHtml(rec.reason)}</p>`;
            if (rec.items && rec.items.length) {
                rec.items.forEach(item => {
                    recHtml += '<div class="list-item">';
                    recHtml += `<h3>${escapeHtml(item.title)}</h3>`;
                    recHtml += `<p>${escapeHtml(item.content)}</p>`;
                    recHtml += '</div>';
                });
            } else {
                recHtml += '<p style="color:var(--text-light);">该方向暂无信息，欢迎在<a href="/forum" style="color:var(--primary);">互助论坛</a>发起讨论</p>';
            }
            recHtml += '</div>';
        });
    } else {
        recHtml += '<div class="card"><p style="color:var(--text-light);">信息库暂无内容，可前往<a href="/forum" style="color:var(--primary);">互助论坛</a>发起讨论</p></div>';
    }
    recSection.innerHTML = recHtml;

    resultDiv.style.display = 'block';
    resultDiv.scrollIntoView({ behavior: 'smooth' });
}

function escapeHtml(s) {
    if (s == null) return '';
    return String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}
