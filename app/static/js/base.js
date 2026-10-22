function showLoading() {
    let loading = document.getElementById('global-loading');
    if (!loading) {
        loading = document.createElement('div');
        loading.id = 'global-loading';
        loading.innerHTML = '<div style="position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;z-index:9999;"><div style="background:white;padding:20px 40px;border-radius:8px;">加载中...</div></div>';
        document.body.appendChild(loading);
    }
    loading.style.display = 'flex';
}

function hideLoading() {
    const loading = document.getElementById('global-loading');
    if (loading) loading.style.display = 'none';
}

const api = {
    post: function(url, data, callback, showLoad = true) {
        console.log('POST请求:', url, data);
        if (showLoad) showLoading();
        fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: new URLSearchParams(data)
        })
        .then(res => {
            console.log('响应状态:', res.status);
            return res.json();
        })
        .then(d => {
            console.log('响应数据:', d);
            if (showLoad) hideLoading();
            callback(d);
        })
        .catch(err => {
            console.error('请求错误:', err);
            if (showLoad) hideLoading();
            showToast('网络错误，请稍后重试', 'error');
        });
    },
    get: function(url, callback, showLoad = true) {
        console.log('GET请求:', url);
        if (showLoad) showLoading();
        fetch(url)
        .then(res => res.json())
        .then(d => {
            console.log('响应数据:', d);
            if (showLoad) hideLoading();
            callback(d);
        })
        .catch(err => {
            console.error('请求错误:', err);
            if (showLoad) hideLoading();
            showToast('网络错误，请稍后重试', 'error');
        });
    }
};

function post(url, data, callback) {
    api.post(url, data, callback);
}

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.style.cssText = `position:fixed;top:20px;left:50%;transform:translateX(-50%);padding:12px 24px;background:${type === 'success' ? '#10b981' : type === 'error' ? '#ef4444' : '#3b82f6'};color:white;border-radius:8px;z-index:10000;animation:slideDown 0.3s ease`;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}
