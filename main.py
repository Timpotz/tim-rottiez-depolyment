from datetime import date
from hashlib import md5
from flask import Flask, abort, render_template, redirect, url_for, flash, request, session
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user, login_required
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text, Column
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
# Import your forms from the forms.py
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from dotenv import load_dotenv
import os

# Load environment variables from .env
load_dotenv()
secret_key=os.getenv("SECRET_KEY")
app = Flask(__name__)
app.config['SECRET_KEY'] = secret_key
ckeditor = CKEditor(app)
Bootstrap5(app)
# Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)


# CREATE DATABASE
class Base(DeclarativeBase):
    pass


app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog1.db'
db = SQLAlchemy(model_class=Base)
db.init_app(app)

# CONFIGURE TABLES
class User(db.Model, UserMixin):
    __tablename__ = "User"
    id = Column(Integer, primary_key=True)
    email = Column(String(250), unique=True, nullable=False)
    name = Column(String(250), nullable=False)
    password = Column(String(250), nullable=False)
    posts = db.relationship('BlogPost', backref='user', lazy=True)
    comments = db.relationship('Comment', backref='user', lazy=True)

class BlogPost(db.Model):
    __tablename__ = "BlogPost"
    id = Column(Integer, primary_key=True)
    title = Column(String(250), unique=True, nullable=False)
    subtitle = Column(String(250), nullable=False)
    date = Column(String(250), nullable=False)
    body = Column(Text, nullable=False)
    author = Column(String(250), nullable=False)
    img_url = Column(String(250), nullable=False)
    user_id=db.Column(db.Integer, db.ForeignKey('User.id'), nullable= False)
    comments= db.relationship('Comment', backref= 'blogpost', lazy=True)

class Comment(db.Model):
    __tablename__ = "Comments"
    id = Column(Integer, primary_key=True)
    body= Column(Text,nullable=False)
    author= Column(String(250), nullable=False)
    user_id=db.Column(db.Integer, db.ForeignKey('User.id'), nullable= False)
    blogpost_id=Column(db.Integer, db.ForeignKey('BlogPost.id'), nullable= False)



with app.app_context():
    db.create_all()


#### Define a context processor to make is_authenticated available to all templates###
@app.context_processor
def inject_is_authenticated():
    is_authenticated = current_user.is_authenticated
    return dict(is_authenticated=is_authenticated)


@app.context_processor
def inject_current_username():
    name = current_user.name if current_user.is_authenticated else None
    return dict(name=name)

@app.context_processor
def inject_current_admin_status():
    is_admin = session.get('is_admin') if current_user.is_authenticated else None
    return dict(is_admin=is_admin)

def gravatar_url(email, size=100, rating='g', default='retro', force_default=False):
    hash_value = md5(email.lower().encode('utf-8')).hexdigest()
    return f"https://www.gravatar.com/avatar/{hash_value}?s={size}&d={default}&r={rating}&f={force_default}"
#####################################################################################

################################CUSTOM WRAPPER#######################################
def admin_user(func):
    @wraps(func)
    def check_if_admin(*args, **kwargs):
        if current_user.id == 1:
            return func(*args, **kwargs)
        else:
            abort(403)  # Unauthorized
    return check_if_admin
#####################################################################################

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if request.method == "POST":
        # email=form.email.data
        # user_exist = User.query.filter_by(email=email).first()
        if form.validate_on_submit():
            try:
                user = User(
                    name=form.name.data,
                    email=form.email.data,
                    password=generate_password_hash(form.password.data, method='pbkdf2', salt_length=16)
                )
                # if user_exist:
                #     flash('You have an existing account, Please log in')
                #     return redirect(url_for('register'))
                # else:
                db.session.add(user)
                db.session.commit()
                login_user(user)
                return redirect(url_for('get_all_posts'))
            except IntegrityError:
                db.session.rollback()
                flash('Registration failed. Email address already exists.')
                return redirect(url_for('register'))
    else:
        return render_template("register.html", form=form)


# TODO: Retrieve a user from the database based on their email. 
@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if request.method == 'POST':
        email = form.email.data
        password = form.password.data
        user_exist = User.query.filter_by(email=email).first()
        # matches=check_password_hash(email_exist.password, password)
        if user_exist and check_password_hash(user_exist.password, password):
            login_user(user_exist)
            #print(current_user.id)
            if current_user.id == 1:
                session['is_admin'] = True
                print(session.get('is_admin'))
                #flash("You are successfully logged in")
                return redirect(url_for('get_all_posts'))
            else:
                session['is_admin'] = False
                #flash("You are successfully logged in")
                return redirect(url_for('get_all_posts'))
        else:
            flash("Invalid email or password. Please try again.")
            return redirect(url_for('login'))
    else:
        return render_template("login.html", form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


##just to check the user data
@app.route('/currentuser')
@login_required
def currentuser():
    name = current_user.name
    email = current_user.email
    id = current_user.id
    status=session.get('is_admin')
    return f'{name}, {email}, {id},{status}'


@app.route('/')
def get_all_posts():
    result = db.session.execute(db.select(BlogPost))
    posts = result.scalars().all()
    return render_template("index.html", all_posts=posts)


# TODO: Allow logged-in users to comment on posts
@app.route("/post/<int:post_id>", methods=['GET', 'POST'])
def show_post(post_id):
    form=CommentForm()
    if form.validate_on_submit():
        comment_post(post_id, form)
        return redirect(url_for('show_post', post_id=post_id))
    else:
        requested_post = db.get_or_404(BlogPost, post_id)
        gravatar_image=gravatar_url('timpot187@gmail.com')
        comments=requested_post.comments
        return render_template("post.html", post=requested_post, form=form, comments=comments,gravatar=gravatar_image)

@login_required
def comment_post(post_id, form):
    new_comment = Comment(
        body=form.comment.data,
        user_id=current_user.id,
        author=current_user.name,
        blogpost_id=post_id
    )
    db.session.add(new_comment)
    db.session.commit()


# TODO: Use a decorator so only an admin user can create a new post
@app.route("/new-post", methods=["GET", "POST"])
@login_required
@admin_user
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        author = User.query.filter_by(email=current_user.email).first()
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=author.name,
            date=date.today().strftime("%B %d, %Y"),
            user_id = current_user.id
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


# TODO: Use a decorator so only an admin user can edit a post
@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@login_required
@admin_user
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = post.author
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True)


# TODO: Use a decorator so only an admin user can delete a post
@app.route("/delete/<int:post_id>")
@login_required
@admin_user
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


if __name__ == "__main__":
    app.run(debug=True, port=5002)
