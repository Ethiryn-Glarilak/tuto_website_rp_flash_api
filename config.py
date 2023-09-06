#config.py

import pathlib
import connexion

from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow

import connexion_mod

basedir = pathlib.Path(__file__).parent.resolve()
# connexion_app = connexion_mod.NewFlaskApp(__name__, specification_dir=basedir, debug = True)
connexion_app = connexion.App(__name__, specification_dir=basedir, debug = True)

app = connexion_app.app
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{basedir / 'people.db'}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
ma = Marshmallow(app)
