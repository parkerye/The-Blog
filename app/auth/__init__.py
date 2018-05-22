from flask import Blueprint

auth = Blueprint('auth', __name__)

from . import views
from ..models import Permission


@auth.app_context_processor
def inject_permissions():
    return dict(Permission=Permission)
