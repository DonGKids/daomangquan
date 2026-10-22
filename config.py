"""
导茫犬平台配置模块。

集中维护 Flask 应用与业务相关的配置项，通过环境变量覆盖默认值：
    - SECRET_KEY: session 加密密钥，**生产环境必须通过环境变量设置强随机值**
    - PERMANENT_SESSION_LIFETIME: session 有效期（默认 7 天）
    - DATABASE: SQLite 数据库文件路径

使用示例：
    # 通过环境变量覆盖
    export SECRET_KEY='your-strong-random-key'
    export DATABASE='/var/data/daomangquan.db'
    python run.py
"""
import datetime
import os


class Config:
    """Flask 应用配置类。

    属性均为类属性，被 ``app.config.from_object()`` 加载后转为 ``app.config`` 项。
    所有敏感配置都支持通过环境变量覆盖，默认值仅供本地开发使用。
    """

    # 会话加密密钥：默认值仅供本地开发使用，生产环境请通过环境变量设置
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-only-do-not-use-in-prod')

    # session 有效期：默认 7 天，到期后用户需要重新登录
    PERMANENT_SESSION_LIFETIME = datetime.timedelta(days=7)

    # SQLite 数据库文件路径，可指向任意可写位置
    DATABASE = os.environ.get('DATABASE', 'daomangquan.db')
