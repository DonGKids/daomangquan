import logging

from flask import Flask, jsonify

from app.models import init_database
from app.routes import bp
from config import Config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)


def create_app(config_object=None):
    """应用工厂函数"""
    app = Flask(__name__, template_folder='templates', static_folder='static')

    app.config.from_object(config_object or Config)

    init_database()
    app.register_blueprint(bp)

    # 全局错误处理器（蓝图级别的 errorhandler 无法捕获 404）
    @app.errorhandler(404)
    def not_found(e):
        return jsonify(code=404, msg='页面不存在'), 404

    @app.errorhandler(500)
    def internal_error(e):
        return jsonify(code=500, msg='服务器内部错误'), 500

    logging.info("应用初始化完成")
    return app
