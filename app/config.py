import os
SECRET_KEY = os.environ.get("SECRET_KEY", os.urandom(24).hex())
DB_URI     = os.environ.get("DB_URI", "sqlite:///data/BD.db")