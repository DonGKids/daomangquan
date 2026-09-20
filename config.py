import datetime
import os


class Config:
    # 会话加密密钥：默认值仅供本地开发使用，生产环境请通过环境变量设置
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-only-do-not-use-in-prod')

    PERMANENT_SESSION_LIFETIME = datetime.timedelta(days=7)

    DATABASE = os.environ.get('DATABASE', 'daomangquan.db')
