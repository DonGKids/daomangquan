function escapeHtml(s) {
    if (s == null) return '';
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

let currentCat = '';

function selectCategory(cat) {
    currentCat = cat;
    // 搜索框清空
    document.getElementById('search-input').value = '';
    // 切换 tab 高亮
    document.querySelectorAll('.cat-tab').forEach(el => {
        el.classList.toggle('active', el.dataset.cat === cat);
    });
    loadInfo(cat, '');
}

function doSearch() {
    const q = document.getElementById('search-input').value.trim();
    // 搜索时取消分类高亮
    document.querySelectorAll('.cat-tab').forEach(el => el.classList.remove('active'));
    loadInfo(currentCat, q);
}

function loadInfo(cat, q) {
    let url = '/api/info';
    const params = [];
    if (cat) params.push(`category=${encodeURIComponent(cat)}`);
    if (q) params.push(`q=${encodeURIComponent(q)}`);
    if (params.length) url += '?' + params.join('&');

    const list = document.getElementById('info_list');
    list.innerHTML = '<p style="color: var(--text-light); text-align: center; padding: 40px;">正在加载...</p>';

    api.get(url, d => {
        if (d.code === 200 && d.data.length > 0) {
            const hint = q
                ? `<div class="search-hint">🔎 搜索 "<strong>${escapeHtml(q)}</strong>" 找到 ${d.data.length} 条结果</div>`
                : (cat ? `<div class="search-hint">📂 ${escapeHtml(cat)} 分类，共 ${d.data.length} 条</div>` : '');
            list.innerHTML = hint + d.data.map(item => `
                <div class="info-card">
                    <span class="info-cat-badge">${escapeHtml(item.category || '未分类')}</span>
                    <h3 style="margin-bottom:6px;">${escapeHtml(item.title)}</h3>
                    <p style="color:var(--text);line-height:1.7;">${escapeHtml(item.content)}</p>
                </div>
            `).join('');
        } else if (d.code === 200) {
            const msg = q
                ? `未找到与 "${escapeHtml(q)}" 相关的信息，试试其他关键词`
                : '该分类下暂无信息';
            list.innerHTML = `<p style="color: var(--text-light); text-align: center; padding: 40px;">${msg}</p>`;
        } else {
            list.innerHTML = `<p style="color:#ef4444; text-align: center; padding: 40px;">加载失败</p>`;
        }
    }, false);
}

// 从 URL 参数初始化（支持从首页 pill 跳转）
// 用 load 事件确保 base.html 的 api 对象已定义
window.addEventListener('load', function() {
    const params = new URLSearchParams(location.search);
    const initCat = params.get('category') || '';
    const initQ = params.get('q') || '';
    if (initQ) {
        document.getElementById('search-input').value = initQ;
        loadInfo(initCat, initQ);
    } else if (initCat) {
        selectCategory(initCat);
    } else {
        loadInfo('', '');
    }
});
