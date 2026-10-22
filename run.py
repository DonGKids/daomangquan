"""
导茫犬平台启动入口模块。

本模块创建 Flask 应用实例并启动开发服务器：
    - 通过环境变量 ``FLASK_HOST`` / ``FLASK_PORT`` / ``FLASK_DEBUG`` 配置
    - 默认监听 127.0.0.1:5000，开启 debug 与 reloader
    - 生产环境建议使用 gunicorn / waitress 等 WSGI 服务器，而非直接运行此模块

使用示例：
    python run.py
    FLASK_PORT=8000 python run.py
"""
import os

from app import create_app

# 应用实例：被 wsgi 服务器（gunicorn/waitress）以 ``run:app`` 形式导入
app = create_app()


if __name__ == '__main__':
    # 主入口：仅在直接运行 ``python run.py`` 时启动开发服务器
    host = os.environ.get('FLASK_HOST', '127.0.0.1')
    port = int(os.environ.get('FLASK_PORT', '5000'))
    debug = os.environ.get('FLASK_DEBUG', '1') == '1'

    app.logger.info("正在启动导茫犬平台...")
    app.logger.info(f"应用启动成功，运行在 http://{host}:{port}")
    app.run(host=host, port=port, debug=debug, use_reloader=debug)
