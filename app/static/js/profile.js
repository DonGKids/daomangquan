function escapeHtml(s) {
    if (s == null) return '';
    return String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function submitFeedback() {
    const content = document.getElementById('feedback-content').value.trim();
    const contact = document.getElementById('feedback-contact').value.trim();
    if (!content) {
        showToast('请输入反馈内容', 'error');
        return;
    }
    if (content.length > 500) {
        showToast('反馈内容不能超过 500 字', 'error');
        return;
    }
    api.post('/api/feedback', { content: content, contact: contact }, d => {
        if (d.code === 200) {
            showToast(d.msg, 'success');
            // 刷新页面以显示新的反馈记录
            setTimeout(() => location.reload(), 1200);
        } else {
            showToast(d.msg, 'error');
        }
    });
}

// 渲染迷茫检测历史的关键词 / 分类标签
// 参数 data 由模板通过内联 script 注入（const data = {{ detections | tojson | safe }};）
function renderDetectionTags(data) {
    if (!data || !Array.isArray(data)) return;
    data.forEach(d => {
        const container = document.getElementById('det-' + d.id);
        if (!container) return;
        let kws = [], cats = [];
        try { kws = JSON.parse(d.keywords || '[]'); } catch (e) {}
        try { cats = JSON.parse(d.categories || '[]'); } catch (e) {}
        let html = '';
        cats.forEach(c => {
            html += `<span style="background:#dbeafe;color:#1e40af;padding:2px 8px;border-radius:999px;font-size:12px;">${escapeHtml(c)}</span>`;
        });
        kws.forEach(k => {
            html += `<span style="background:#f1f5f9;color:#475569;padding:2px 8px;border-radius:999px;font-size:12px;">${escapeHtml(k)}</span>`;
        });
        if (!html) {
            html = `<span style="color:var(--text-light);font-size:12px;">未识别到明确关键词</span>`;
        }
        container.innerHTML = html;
    });
}
