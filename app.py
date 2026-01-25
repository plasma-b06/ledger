from flask import Flask, render_template, request,redirect
from dotenv import load_dotenv()
from datetime import datetime
import os
from flask_sqlalchemy import SQlAlchemy

app = Flask(__name__)

@app.route("/login")
def login():


@app.route("/register")
def register():
    //todo


@app.route("/")
def index():
    //todo
