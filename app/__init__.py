from flask import Flask, render_template
from flask_bootstrap import Bootstrap
from config import config
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail
from flask_login import LoginManager
from flask_moment import Moment
from flask_pagedown import PageDown
from flask_ckeditor import CKEditor
from flask_dropzone import Dropzone
from flask_uploads import UploadSet, configure_uploads, IMAGES
from flask_msearch import Search
from jieba.analyse import ChineseAnalyzer

bootstrap = Bootstrap()
db = SQLAlchemy()
mail = Mail()
moment = Moment()
pagedown=PageDown()
ckeditor=CKEditor()
dropzone=Dropzone()
search = Search(analyzer=ChineseAnalyzer())


#photos = UploadSet('photos',IMAGES)

login_manager = LoginManager()
login_manager.session_protection = 'strong'
login_manager.login_view = 'auth.login'


def create_app(config_name):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    #app.config.from_pyfile('config.py')
    config[config_name].init_app(app)
    bootstrap.init_app(app)
    mail.init_app(app)
    db.init_app(app)
    moment.init_app(app)
    ckeditor.init_app(app)
    from .auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint)
    login_manager.init_app(app)
    dropzone.init_app(app)
    search.init_app(app)

    #configure_uploads(app, photos)
    return app
