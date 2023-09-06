from flask import render_template
from models import Person

def people():
    people = Person.query.all()
    return render_template('people.html', people=people)
