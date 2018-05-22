#!/usr/bin/env python
import os
from app import create_app, db
from app.models import User, Role, Post, Follow, Album, Photo, PostType
from flask_script import Manager, Shell, Server
from flask_migrate import Migrate, MigrateCommand
from flask_ckeditor import CKEditor

app = create_app(os.getenv('FLASK_CONFIG') or 'default')
manager = Manager(app)


migrate = Migrate(app, db)
manager.add_command('db', MigrateCommand)


def make_shell_context():
    return dict(app=app, db=db, User=User, Role=Role, Post=Post, Follow=Follow ,PostType=PostType)


manager.add_command("shell", Shell(make_context=make_shell_context))
manager.add_command("runserver", Server(host="0.0.0.0", port=5000, use_debugger=True, threaded=True))
if __name__ == '__main__':
    manager.run()
