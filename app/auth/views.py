# -*- coding:utf-8 -*-
from flask import g,render_template, send_from_directory, redirect, request, url_for, flash, make_response , send_from_directory , Flask
from ..models import User, Role, Post, Permission, Comment ,PostType
from . import auth
from .forms import LoginForm, RegistrationForm, EditProfileForm, EditProfileAdminForm, PostForm, CommentForm
from flask_login import login_user, login_required, logout_user, current_user, current_app
from ..email import send_email
from .. import db
from ..decorators import admin_required, permission_required
import os
from flask_ckeditor import CKEditor,CKEditorField
from .. import ckeditor



@auth.route('/', methods=['GET', 'POST']) 
def index():
    form = PostForm()
    test = current_user.can(Permission.WRITE_ARTICLES)
    page = request.args.get('page', 1, type=int)
    pagination = Post.query.order_by(Post.timestamp.desc()).paginate(
        page, per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],
        error_out=False)
    if test and \
            form.validate_on_submit():
        post = Post(title=form.title.data,body=form.body.data,body_type=PostType.query.get(form.body_type.data).id, author=current_user._get_current_object())
        db.session.add(post)
        return redirect(url_for('.index'))
    Post.query.order_by(Post.timestamp.desc()).all()
    show_followed = False
    if current_user.is_authenticated:
        show_followed = bool(request.cookies.get('show_followed', ''))
    if show_followed:
        query = current_user.followed_posts
    else:
        query = Post.query
    pagination = query.order_by(Post.timestamp.desc()).paginate(
        page, per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],
        error_out=False)
    posts = pagination.items
    return render_template('index.html', form=form, posts=posts, test=test, show_followed=show_followed,
                           pagination=pagination)




@auth.route('/files/<filename>')
def files(filename):
    path = current_app.config['UPLOADED_PATH']
    return send_from_directory(path, filename)

@auth.route('/upload', methods=['POST'])
@ckeditor.uploader
def upload():
    f = request.files.get('upload')
    f.save(os.path.join(current_app.config['UPLOADED_PATH'], f.filename))
    url = url_for('auth.files', filename=f.filename)
    return url







@auth.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user is not None and user.verify_password(form.password.data):
            login_user(user, form.remember_me.data)
            return redirect(request.args.get('next') or url_for('auth.index'))
        flash('Invalid username or password.')
    return render_template('auth/login.html', form=form)


@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.')
    return redirect(url_for('auth.index'))


@auth.route('/confirm/<token>')
@login_required
def confirm(token):
    if current_user.confirmed:
        return redirect(url_for('.index'))
    if current_user.confirm(token):
        flash('You have confirmed your account. Thanks!')
    else:
        flash('The confirmation link is invalid or has expired.')
    return redirect(url_for('.index'))

@auth.before_app_request
def before_request():
    if current_user.is_authenticated \
        and not current_user.confirmed \
        and request.endpoint[:5] != 'auth.' \
        and request.endpoint != 'static':
            return redirect(url_for('auth.unconfirmed'))

@auth.route('/unconfirmed')
def unconfirmed():
    if current_user.is_anonymous or current_user.confirmed:
        return redirect(url_for('.index'))
    return render_template('auth/unconfirmed.html')

@auth.route('/confirm')
@login_required
def resend_confirmation():
    token = current_user.generate_confirmation_token()
    send_email(current_user.email, 'Confirm Your Account',
               'auth/email/confirm', user=current_user, token=token)
    flash('A new confirmation email has been sent to you by email.')
    return redirect(url_for('.index'))




@auth.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(email=form.email.data, username=form.username.data, password=form.password.data)
        db.session.add(user)
        db.session.commit()
        token = user.generate_confirmation_token()
        send_email(user.email, 'Confirm Your Account',
                   'auth/email/confirm', user=user, token=token)
        flash('A confirmation email has been sent to you by email.')
        return redirect(url_for('auth.login'))
    return render_template('auth/register.html', form=form)


@auth.route('/user/<username>')
def user(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        abort(404)
    posts = user.posts.order_by(Post.timestamp.desc()).all()
    return render_template('user.html', user=user, posts=posts)


@auth.route('/edit-profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm()
    if form.validate_on_submit():
        current_user.name = form.name.data
        current_user.location = form.location.data
        current_user.about_me = form.about_me.data
        db.session.add(current_user)
        flash('Your profile has been updated')
        return redirect(url_for('.user', username=current_user.username))
    form.name.data = current_user.name
    form.location.data = current_user.location
    form.about_me.data = current_user.about_me
    return render_template('edit_profile.html', form=form)


@auth.route('/edit-profile/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_profile_admin(id):
    user = User.query.get_or_404(id)
    form = EditProfileAdminForm(user=user)
    if form.validate_on_submit():
        user.email = form.email.data
        user.username = form.username.data
        user.confirmed = form.confirmed.data
        user.role = Role.query.get(form.role.data)
        user.name = form.name.data
        user.location = form.location.data
        user.about_me = form.about_me.data
        db.session.add(user)
        flash('The profile has been updated.')
        return redirect(url_for('.user', username=user.username))
    form.email.data = user.email
    form.username.data = user.username
    form.confirmed.data = user.confirmed
    form.role.data = user.role_id
    form.name.data = user.name
    form.location.data = user.location
    form.about_me.data = user.about_me
    return render_template('edit_profile.html', form=form, user=user)


@auth.route('/post/<int:id>', methods=['GET', 'POST'])
def post(id):
    post = Post.query.get_or_404(id)
    form = CommentForm()
    if form.validate_on_submit():
        comment = Comment(body=form.body.data,
                          post=post,
                          author=current_user._get_current_object())
        db.session.add(comment)
        flash('Your comment has been published.')
        return redirect(url_for('.post', id=post.id, page=-1))
    page = request.args.get('page', 1, type=int)
    if page == -1:
        page = (post.comments.count() - 1) // \
               current_app.config['FLASKY_COMMENTS_PER_PAGE'] + 1
    pagination = post.comments.order_by(Comment.timestamp.asc()).paginate(
        page, per_page=current_app.config['FLASKY_COMMENTS_PER_PAGE'],
        error_out=False)
    comments = pagination.items
    return render_template('post.html', posts=[post], form=form,
                           comments=comments, pagination=pagination)


@auth.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    post = Post.query.get_or_404(id)
    if current_user != post.author and \
            not current_user.can(Permission.ADMINISTER):
        abort(403)
    form = PostForm()
    if form.validate_on_submit():
        post.title = form.title.data
        post.body = form.body.data
        post.body_type = PostType.query.get(form.body_type.data).id
        db.session.add(post)
        flash('The post has been updated.')
        return redirect(url_for('.post', id=post.id))
    form.body.data = post.body
    form.title.data = post.title
    form.body_type.data = post.body_type
    return render_template('edit_post.html', form=form)

@auth.route('/write/<username>',methods=['POST','GET'])
def write(username):
    form = PostForm()
    test = current_user.can(Permission.WRITE_ARTICLES)
    page = request.args.get('page', 1, type=int)
    pagination = Post.query.order_by(Post.timestamp.desc()).paginate(
        page, per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],
        error_out=False)
    if test and \
            form.validate_on_submit():
        post = Post(title=form.title.data,body=form.body.data,body_type=PostType.query.get(form.body_type.data).id, author=current_user._get_current_object())
        db.session.add(post)
        return redirect(url_for('.index'))
    Post.query.order_by(Post.timestamp.desc()).all()
    show_followed = False
    if current_user.is_authenticated:
        show_followed = bool(request.cookies.get('show_followed', ''))
    if show_followed:
        query = current_user.followed_posts
    else:
        query = Post.query
    pagination = query.order_by(Post.timestamp.desc()).paginate(
        page, per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],
        error_out=False)
    posts = pagination.items
    return render_template('write.html', form=form, posts=posts, test=test, show_followed=show_followed,
                           pagination=pagination)



@auth.route('/follow/<username>')
@login_required
@permission_required(Permission.FOLLOW)
def follow(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('Invalid user.')
        return redirect(url_for('.index'))
    if current_user.is_following(user):
        flash('You are already following this user.')
        return redirect(url_for('.user', username=username))
    current_user.follow(user)
    flash('You are now following %s.' % username)
    return redirect(url_for('.user', username=username))


@auth.route('/unfollow/<username>')
@login_required
@permission_required(Permission.FOLLOW)
def unfollow(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('Invalid user.')
        return redirect(url_for('.index'))
    if not current_user.is_following(user):
        flash('You are not following this user.')
        return redirect(url_for('.user', username=username))
    current_user.unfollow(user)
    flash('You are not following %s anymore.' % username)
    return redirect(url_for('.user', username=username))


@auth.route('/followers/<username>')
def followers(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('Invalid user.')
        return redirect(url_for('.index'))
    page = request.args.get('page', 1, type=int)
    pagination = user.followers.paginate(
        page, per_page=current_app.config['FLASKY_FOLLOWERS_PER_PAGE'],
        error_out=False)
    follows = [{'user': item.follower, 'timestamp': item.timestamp}
               for item in pagination.items]
    return render_template('followers.html', user=user, title="Followers of",
                           endpoint='.followers', pagination=pagination,
                           follows=follows)


@auth.route('/followed-by/<username>')
def followed_by(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('Invalid user.')
        return redirect(url_for('.index'))
    page = request.args.get('page', 1, type=int)
    pagination = user.followed.paginate(
        page, per_page=current_app.config['FLASKY_FOLLOWERS_PER_PAGE'],
        error_out=False)
    follows = [{'user': item.followed, 'timestamp': item.timestamp}
               for item in pagination.items]
    return render_template('followers.html', user=user, title="Followed by",
                           endpoint='.followed_by', pagination=pagination,
                           follows=follows)


@auth.route('/all')
@login_required
def show_all():
    resp = make_response(redirect(url_for('.index')))
    resp.set_cookie('show_followed', '', max_age=30 * 24 * 60 * 60)
    return resp


@auth.route('/followed')
@login_required
def show_followed():
    resp = make_response(redirect(url_for('.index')))
    resp.set_cookie('show_followed', '1', max_age=30 * 24 * 60 * 60)
    return resp


@auth.route('/moderate')
@login_required
@permission_required(Permission.MODERATE_COMMENTS)
def moderate():
    page = request.args.get('page', 1, type=int)
    pagination = Comment.query.order_by(Comment.timestamp.desc()).paginate(
        page, per_page=current_app.config['FLASKY_COMMENTS_PER_PAGE'],
        error_out=False)
    comments = pagination.items
    return render_template('moderate.html', comments=comments,
                           pagination=pagination, page=page)


@auth.route('/moderate/enable/<int:id>')
@login_required
@permission_required(Permission.MODERATE_COMMENTS)
def moderate_enable(id):
    comment = Comment.query.get_or_404(id)
    comment.disabled = False
    db.session.add(comment)
    return redirect(url_for('.moderate',
                            page=request.args.get('page', 1, type=int)))


@auth.route('/moderate/disable/<int:id>')
@login_required
@permission_required(Permission.MODERATE_COMMENTS)
def moderate_disable(id):
    comment = Comment.query.get_or_404(id)
    comment.disabled = True
    db.session.add(comment)
    return redirect(url_for('.moderate',
                            page=request.args.get('page', 1, type=int)))

@auth.route('/tomato/',methods=['POST','GET'])
def tomato():
    return render_template('tomato.html')

@auth.route('/pic/',methods=['POST','GET'])
def pic():
    
    return render_template('pic.html')


@auth.route('/computer/',methods=['POST','GET'])
def computer():
    body_type = Post.query.filter_by(body_type='1')
    if body_type is None:
        abort(404)
    posts = body_type.order_by(Post.timestamp.desc()).all()
    return render_template('computer.html',body_type=body_type,posts=posts)

@auth.route('/electronic/',methods=['POST','GET'])
def electronic():
    body_type = Post.query.filter_by(body_type='2')
    if body_type is None:
        abort(404)
    posts = body_type.order_by(Post.timestamp.desc()).all()
    return render_template('electronic.html',body_type=body_type,posts=posts)

@auth.route('/environment/',methods=['POST','GET'])
def environment():
    body_type = Post.query.filter_by(body_type='3')
    if body_type is None:
        abort(404)
    posts = body_type.order_by(Post.timestamp.desc()).all()
    return render_template('environment.html',body_type=body_type,posts=posts)

@auth.route('/economic/',methods=['POST','GET'])
def economic():
    body_type = Post.query.filter_by(body_type='4')
    if body_type is None:
        abort(404)
    posts = body_type.order_by(Post.timestamp.desc()).all()
    return render_template('economic.html',body_type=body_type,posts=posts)

@auth.route('/thammasat/',methods=['POST','GET'])
def thammasat():
    body_type = Post.query.filter_by(body_type='5')
    if body_type is None:
        abort(404)
    posts = body_type.order_by(Post.timestamp.desc()).all()
    return render_template('thammasat.html',body_type=body_type,posts=posts)

@auth.route('/english/',methods=['POST','GET'])
def english():
    body_type = Post.query.filter_by(body_type='6')
    if body_type is None:
        abort(404)
    posts = body_type.order_by(Post.timestamp.desc()).all()
    return render_template('english.html',body_type=body_type,posts=posts)

@auth.route('/financial/',methods=['POST','GET'])
def financial():
    body_type = Post.query.filter_by(body_type='7')
    if body_type is None:
        abort(404)
    posts = body_type.order_by(Post.timestamp.desc()).all()
    return render_template('financial.html',body_type=body_type,posts=posts)

@auth.route('/art/',methods=['POST','GET'])
def art():
    body_type = Post.query.filter_by(body_type='8')
    if body_type is None:
        abort(404)
    posts = body_type.order_by(Post.timestamp.desc()).all()
    return render_template('art.html',body_type=body_type,posts=posts)

@auth.route('/information/',methods=['POST','GET'])
def information():
    body_type = Post.query.filter_by(body_type='9')
    if body_type is None:
        abort(404)
    posts = body_type.order_by(Post.timestamp.desc()).all()
    return render_template('information.html',body_type=body_type,posts=posts)

@auth.route('/maths/',methods=['POST','GET'])
def maths():
    body_type = Post.query.filter_by(body_type='10')
    if body_type is None:
        abort(404)
    posts = body_type.order_by(Post.timestamp.desc()).all()
    return render_template('maths.html',body_type=body_type,posts=posts)





#以上功能块进行修改中

@auth.route('/messages')
@login_required
@permission_required(Permission.MODERATE_COMMENTS)
def messages():
    page = request.args.get('page', 1, type=int)
    pagination = Post.query.order_by(Post.timestamp.desc()).paginate(
        page, per_page=current_app.config['FLASKY_COMMENTS_PER_PAGE'],
        error_out=False)
    posts = pagination.items
    return render_template('messages.html', posts=posts,
                           pagination=pagination, page=page)


@auth.route('/users')
@login_required
@permission_required(Permission.MODERATE_COMMENTS)
def users():
    page = request.args.get('page', 1, type=int)
    pagination = User.query.order_by(User.id.desc()).paginate(
        page, per_page=current_app.config['FLASKY_COMMENTS_PER_PAGE'],
        error_out=False)
    users = pagination.items
    return render_template('users.html', users=users,
                           pagination=pagination, page=page)


@auth.route('/search', methods = ['GET','POST'])
@login_required
def search():
    keyword = request.form.get('q','default value')
    page = request.args.get('page', 1, type=int)
    show_followed = False

    # 为了显示某页中的记录，要把 all() 换成 Flask-SQLAlchemy 提供的 paginate() 方法。页数是 paginate() 方法的第一个参数，也是唯一必需的参数。可选参数 per_page 用来指定每页显示的记录数量；如果没有指定，则默认显示 20 个记录。另一个可选参数为 error_out ，当其设为 True 时（默认值），如果请求的页数超出了范围，则会返回 404 错误；如果设为 False ，页数超出范围时会返回一个空列表。为了能够很便利地配置每页显示的记录数量，参数 per_page 的值从程序的环境变量 FLASKY_POSTS_PER_PAGE 中读取。这样修改之后，首页中的文章列表只会显示有限数量的文章。若想查看第 2 页中的文章，要在浏览器地址栏中的 URL 后加上查询字符串 ?page=2。
    pagination = Post.query.msearch(keyword).order_by(Post.timestamp.desc()).paginate(
        page, per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],
        error_out=False)
    posts = pagination.items
    results = Post.query.msearch(keyword,fields=['title','body'],limit=20)
    return render_template('search_results.html',results =results,keyword=keyword,posts=posts)


##################################################################
'''
def save_image(files):
    images = []
    for img in files:
        # 处理文件名
        filename = hashlib.md5(current_user.username + str(time.time())).hexdigest()[:10]
        image = photos.save(img, name=filename + '.')
        file_url = photos.url(image)
        url_s = create_show(image)  # 创建展示图
        url_t = create_thumbnail(image)  # 创建缩略图
        images.append((file_url, url_s, url_t))
    return images

def image_resize(image, base_width):
    #: create thumbnail
    filename, ext = os.path.splitext(image)
    img = Image.open(photos.path(image))
    if img.size[0] <= base_width:
        return photos.url(image)
    w_percent = (base_width / float(img.size[0]))
    h_size = int((float(img.size[1]) * float(w_percent)))
    img = img.resize((base_width, h_size), PIL.Image.ANTIALIAS)
    img.save(os.path.join(current_app.config['UPLOADED_PHOTOS_DEST'], filename + img_suffix[base_width] + ext))
    return url_for('.uploaded_file', filename=filename + img_suffix[base_width] + ext)


@auth.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(current_app.config['UPLOADED_PHOTOS_DEST'],
                               filename)


@auth.route('/new-album', methods=['GET', 'POST'])
@login_required
def new_album():
    form = NewAlbumForm()
    if form.validate_on_submit(): # current_user.can(Permission.CREATE_ALBUMS)
        if request.method == 'POST' and 'photo' in request.files:
            images = save_image(request.files.getlist('photo'))

        title = form.title.data
        about = form.about.data
        author = current_user._get_current_object()
        no_public = form.no_public.data
        no_comment = form.no_comment.data
        album = Album(title=title, about=about,
                      cover=images[0][2], author=author,
                      no_public=no_public, no_comment=no_comment)
        db.session.add(album)

        for url in images:
            photo = Photo(url=url[0], url_s=url[1], url_t=url[2],
                          album=album, author=current_user._get_current_object())
            db.session.add(photo)
        db.session.commit()
        flash(u'相册创建成功！', 'success')
        return redirect(url_for('.edit_photo', id=album.id))
    return render_template('new_album.html', form=form)


@auth.route('/add-photo/<int:id>', methods=['GET', 'POST'])
@login_required
def add_photo(id):
    album = Album.query.get_or_404(id)
    form = AddPhotoForm()
    if form.validate_on_submit(): # current_user.can(Permission.CREATE_ALBUMS)
        if request.method == 'POST' and 'photo' in request.files:
            images = save_image(request.files.getlist('photo'))

            for url in images:
                photo = Photo(url=url[0], url_s=url[1], url_t=url[2],
                              album=album, author=current_user._get_current_object())
                db.session.add(photo)
            db.session.commit()
        flash(u'图片添加成功！', 'success')
        return redirect(url_for('.album', id=album.id))
    return render_template('add_photo.html', form=form, album=album)


@auth.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    return render_template('upload.html')


@auth.route('/upload-add', methods=['GET', 'POST'])
@login_required
def upload_add():
    id = request.form.get('album')
    return redirect(url_for('.add_photo', id=id))

@auth.route('/delete/photo/<id>')
@login_required
def delete_photo(id):
    photo = Photo.query.filter_by(id=id).first()
    album = photo.album
    if photo is None:
        flash(u'无效的操作。', 'warning')
        return redirect(url_for('.index', username=current_user.username))
    if current_user.username != photo.author.username:
        abort(403)
    db.session.delete(photo)
    db.session.commit()
    flash(u'删除成功。', 'success')
    return redirect(url_for('.album', id=album.id))


@auth.route('/delete/edit-photo/<id>')
@login_required
def delete_edit_photo(id):
    photo = Photo.query.filter_by(id=id).first()
    album = photo.album
    if photo is None:
        flash(u'无效的操作。', 'warning')
        return redirect(url_for('.index', username=current_user.username))
    if current_user.username != photo.author.username:
        abort(403)
    db.session.delete(photo)
    db.session.commit()
    return (''), 204


@auth.route('/delete/album/<id>')
@login_required
def delete_album(id):
    album = Album.query.filter_by(id=id).first()
    if album is None:
        flash(u'无效的操作。', 'warning')
        return redirect(url_for('.index', username=current_user.username))
    if current_user.username != album.author.username:
        abort(403)
    db.session.delete(album)
    db.session.commit()
    flash(u'删除成功。', 'success')
    return redirect(url_for('.albums', username=album.author.username))


@auth.route('/album/<int:id>')
def album(id):
    album = Album.query.get_or_404(id)
    # display default cover when an album is empty
    placeholder = 'http://p1.bpimg.com/567591/15110c0119201359.png'
    photo_amount = len(list(album.photos))
    if photo_amount == 0:
        album.cover = placeholder
    elif photo_amount != 0 and album.cover == placeholder:
        album.cover = album.photos[0].path

    if current_user != album.author and album.no_public == True:
        abort(404)
    page = request.args.get('page', 1, type=int)
    if album.asc_order:
        pagination = album.photos.order_by(Photo.order.asc()).paginate(
            page, per_page=current_app.config['FANXIANGCE_PHOTOS_PER_PAGE'],
            error_out=False)
    else:
        pagination = album.photos.order_by(Photo.order.asc()).paginate(
            page, per_page=current_app.config['FANXIANGCE_PHOTOS_PER_PAGE'],
            error_out=False)
    photos = pagination.items
    if len(photos) == 0:
        no_pic = True
    else:
        no_pic = False
    if current_user.is_authenticated:
        user = User.query.filter_by(username=current_user.username).first()
        likes = user.photo_likes.order_by(LikePhoto.timestamp.asc()).all()
        likes = [{'id': like.like_photo, 'timestamp': like.timestamp, 'url_t': like.like_photo.url_t} for like in likes]
    else:
        likes = ""

    return render_template('album.html', album=album, photos=photos, pagination=pagination,
                           likes=likes, no_pic=no_pic)


@auth.route('/photo/<int:id>', methods=['GET', 'POST'])
def photo(id):
    photo = Photo.query.get_or_404(id)
    album = photo.album
    if current_user != album.author and album.no_public == True:
        abort(404)

    photo_sum = len(list(album.photos))
    form = CommentForm()
    photo_index = [p.id for p in album.photos.order_by(Photo.order.asc())].index(photo.id) + 1
    if current_user.is_authenticated:
        user = User.query.filter_by(username=current_user.username).first()
        likes = user.photo_likes.order_by(LikePhoto.timestamp.desc()).all()
        likes = [{'id': like.like_photo, 'timestamp': like.timestamp, 'url': like.like_photo.url, 'liked':like.photo_liked} for like in likes]
    else:
        likes = ""

    if form.validate_on_submit():
        if current_user.is_authenticated:
            comment = Comment(body=form.body.data,
                              photo=photo,
                              author=current_user._get_current_object())
            db.session.add(comment)
            flash(u'你的评论已经发表。', 'success')
            return redirect(url_for('.photo', id=photo.id))
        else:
            flash(u'请先登录。', 'info')
    page = request.args.get('page', 1, type=int)
    pagination = photo.comments.order_by(Comment.timestamp.asc()).paginate(
        page, per_page=current_app.config['FANXIANGCE_COMMENTS_PER_PAGE'],
        error_out=False)
    comments = pagination.items
    amount = len(comments)
    return render_template('photo.html', form=form, album=album, amount=amount,
                           photo=photo, pagination=pagination,
                           comments=comments, photo_index=photo_index, photo_sum=photo_sum)


@auth.route('/photo/n/<int:id>')
def photo_next(id):
    "redirect to next imgae"
    photo_now = Photo.query.get_or_404(id)
    album = photo_now.album
    photos = album.photos.order_by(Photo.order.asc())
    position = list(photos).index(photo_now) + 1
    if position == len(list(photos)):
        flash(u'已经是最后一张了。', 'info')
        return redirect(url_for('.photo', id=id))
    photo = photos[position]
    return redirect(url_for('.photo', id=photo.id))


@auth.route('/photo/p/<int:id>')
def photo_previous(id):
    "redirect to previous imgae"
    photo_now = Photo.query.get_or_404(id)
    album = photo_now.album
    photos = album.photos.order_by(Photo.order.asc())
    position = list(photos).index(photo_now) - 1
    if position == -1:
        flash(u'已经是第一张了。', 'info')
        return redirect(url_for('.photo', id=id))
    photo = photos[position]
    return redirect(url_for('.photo', id=photo.id))'''