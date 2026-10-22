"""
导茫犬平台应用工厂模块。

本模块通过 ``create_app()`` 工厂函数构建 Flask 应用实例：
    - 配置日志（写入 app.log 文件 + 控制台输出）
    - 加载配置对象（默认 ``config.Config``，可通过参数覆盖）
    - 初始化数据库（建表 + 迁移 + 默认数据）
    - 注册 ``main`` 蓝图（路由全部在该蓝图上）
    - 注册全局 404 / 500 错误处理器（返回 JSON 而非默认 HTML 错误页）

使用示例：
    from app import create_app
    app = create_app()
    app.run()
"""
import logging

from flask import Flask, jsonify

from app.models import init_database
from app.routes import bp
from config import Config

# 日志配置：同时输出到文件（app.log，UTF-8）与控制台
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)


def create_app(config_object=None):
    """Flask 应用工厂函数。

    流程：
        1. 创建 Flask 实例，指定模板/静态文件夹位置。
        2. 从 ``config_object``（或默认 ``Config``）读取配置。
        3. 调用 ``init_database()`` 建表与迁移。
        4. 注册 ``main`` 蓝图，挂载全部路由。
        5. 注册 404 / 500 全局错误处理器，统一返回 JSON。

    Args:
        config_object: 配置对象或配置类，可选；不传则使用 ``config.Config``。
            测试时可以传入自定义配置类覆盖数据库路径等。

    Returns:
        Flask: 已完成配置与初始化的 Flask 应用实例。
    """
    app = Flask(__name__, template_folder='templates', static_folder='static')

    app.config.from_object(config_object or Config)

    init_database()
    app.register_blueprint(bp)

    # 全局错误处理器（蓝图级别的 errorhandler 无法捕获 404）
    @app.errorhandler(404)
    def not_found(e):
        """全局 404 处理器：返回 JSON 而非默认 HTML 错误页。"""
        return jsonify(code=404, msg='页面不存在'), 404

    @app.errorhandler(500)
    def internal_error(e):
        """全局 500 处理器：返回统一 JSON 错误结构。"""
        return jsonify(code=500, msg='服务器内部错误'), 500

    logging.info("应用初始化完成")
    return app
