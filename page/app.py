import requests
import json

from flask import Flask, render_template, url_for, request, redirect, flash
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from oauthlib.oauth2 import WebApplicationClient

from .user import User
from .common import PATH, get_logger, get_oauth_credential
from .api.student import enroll_class, recommend_problems
from .api.doc import get_header, get_post
from .api.gist import display_gist


def deployment():
  app = Flask(__name__)
  app.secret_key = "page"

  logger = get_logger(__name__)

  login_manager = LoginManager()
  login_manager.init_app(app)

  GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"
  app.jinja_env.globals.update(display_gist=display_gist)  # use python function inside jinja

  @login_manager.user_loader
  def load_user(id):
    return User.get(id)

  @app.route("/admin", methods=["POST", "GET"])
  def admin():
    if request.method == 'POST':
      return render_template("admin.html", students=recommend_problems(kr_names=request.form["nm"]))
    return render_template("admin.html")

  @app.route("/premium", methods=["POST", "GET"])
  def premium():
    if request.method == 'POST':
      class_id = request.form["class_id"]
      enroll_class(current_user.id, class_id)
      return render_template("index.html", headers=get_header(), h0="", h1="", posts={})
    return render_template("premium.html")

  @app.route("/", methods=["GET"])
  @app.route("/<string:h0>/", methods=["GET"])
  @app.route("/<string:h0>/<string:h1>/", methods=["GET"])
  @app.route("/<string:h0>/<string:h1>/<string:h2>", methods=["GET"])
  @app.route("/<string:h0>/<string:h1>/<string:h2>/<string:h3>", methods=["GET"])
  def index(h0="Python", h1="", h2="", h3=""):
    logger.debug(f"Opening {h0}/{h1}/{h2}/{h3} in {PATH.DOC}/{h0}.json")

    posts = get_post(h0, h1, h2, h3)
    headers = get_header()

    return render_template("index.html", headers=headers, h0=h0, h1=h1, posts=posts)

  @app.route("/signin", methods=["POST", "GET"])
  def signin():
    oauth_cred = get_oauth_credential()
    client = WebApplicationClient(oauth_cred["client_id"])
    authorization_endpoint = requests.get(GOOGLE_DISCOVERY_URL).json()["authorization_endpoint"]
    request_uri = client.prepare_request_uri(authorization_endpoint, redirect_uri=request.base_url + "/callback", scope=["openid", "email", "profile"],)
    logger.debug(request_uri)
    return redirect(request_uri)

  @app.route("/signin/callback")
  def callback():
    oauth_cred = get_oauth_credential()
    code = request.args.get("code")
    client = WebApplicationClient(oauth_cred["client_id"])

    token_endpoint = requests.get(GOOGLE_DISCOVERY_URL).json()["token_endpoint"]
    token_url, headers, body = client.prepare_token_request(token_endpoint, authorization_response=request.url, redirect_url=request.base_url, code=code)
    token_response = requests.post(token_url, headers=headers, data=body, auth=(oauth_cred["client_id"], oauth_cred["client_secret"]))
    client.parse_request_body_response(json.dumps(token_response.json()))
    userinfo_endpoint = requests.get(GOOGLE_DISCOVERY_URL).json()["userinfo_endpoint"]
    uri, headers, body = client.add_token(userinfo_endpoint)

    if "http:" in uri:
      uri = "https:" + uri[5:]

    userinfo_response = requests.get(uri, headers=headers, data=body).json()

    logger.debug(userinfo_response)
    user = User(id=userinfo_response["email"].split('@')[0], en_name=userinfo_response["name"])
    login_user(user, remember=True)
    return redirect(url_for("index"))

  @app.route("/signout", methods=["POST", "GET"])
  def signout():
    logger.debug("signing out")
    logout_user()
    return redirect(url_for("index"))

  return app


def production():
  from livereload import Server

  app = Flask(__name__)
  app.jinja_env.globals.update(display_gist=display_gist)

  @app.route("/", methods=["GET"])
  def index():
    h0, h1, h2, h3 = "Python", "Syntax", "IO", "Print"
    posts = get_post(h0, h1, h2, h3)

    return render_template("index.html", headers=get_header(), h0=h0, h1=h1, posts=posts, debug=True)

  @app.route("/signin", methods=["GET"])
  def signin():
    return render_template("practice.html")

  server = Server(app.wsgi_app)
  server.serve(debug=True)
  return app