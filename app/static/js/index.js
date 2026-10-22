// 首页脚本：首页专属交互逻辑
// 该文件由 base.html 中的 base.js 之后加载，可使用 api / showToast 等全局函数
(function () {
    'use strict';

    // 平稳滚动到锚点（点击 hero CTA 时使用，仅对页面内 # 锚点生效）
    function smoothScrollTo(targetSelector) {
        const el = document.querySelector(targetSelector);
        if (el) {
            el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }

    // 给 hero 区的 CTA 链接加上平滑滚动（仅页面内 # 锚点，外链不拦截）
    function bindHeroCtaSmoothScroll() {
        document.querySelectorAll('.hero .cta').forEach(function (a) {
            const href = a.getAttribute('href') || '';
            if (href.charAt(0) === '#') {
                a.addEventListener('click', function (e) {
                    e.preventDefault();
                    smoothScrollTo(href);
                });
            }
        });
    }

    // 卡片点击反馈：按下时轻微缩小，松开/移出时回弹
    function bindCardPressFeedback() {
        const cards = document.querySelectorAll('.feature-card, .recommend-card, .stat-card, .trend-item');
        cards.forEach(function (card) {
            card.addEventListener('mousedown', function () {
                card.style.transition = 'transform 0.1s ease';
                card.style.transform = (card.style.transform || '').replace(/\s*scale\([^)]*\)/g, '') + ' scale(0.98)';
            });
            const reset = function () {
                card.style.transform = (card.style.transform || '').replace(/\s*scale\(0\.98\)/g, '');
            };
            card.addEventListener('mouseup', reset);
            card.addEventListener('mouseleave', reset);
        });
    }

    // 章节标题"查看全部 →"链接悬停时高亮对应区块
    function bindSectionTitleHover() {
        document.querySelectorAll('.section-title a').forEach(function (a) {
            a.addEventListener('mouseenter', function () {
                a.style.transition = 'color 0.15s';
            });
        });
    }

    // 主题切换占位（保留扩展位，便于后续接入深色模式）
    function initThemeHook() {
        window.__indexThemeHook__ = function () {
            // 预留给后续深色模式扩展
        };
    }

    // 等待 DOM 就绪后初始化
    function init() {
        bindHeroCtaSmoothScroll();
        bindCardPressFeedback();
        bindSectionTitleHover();
        initThemeHook();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
