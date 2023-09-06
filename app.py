# app.py

from flask import render_template
import config
from models import Person
from preload_swagger import config_api

# import logging

# logging.basicConfig(level=logging.DEBUG)


app = config.connexion_app
app.add_api(config_api)

@app.route('/')
def home():
    people = Person.query.all()
    return render_template('home.html', people=people)

if __name__ == '__main__':
    app.run(debug=True)
