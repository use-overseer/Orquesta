# server.py
from flask import Flask
from orquesta import app as orquesta_app

app = Flask(__name__)
app.register_blueprint(orquesta_app)

if __name__ == "__main__":
    print("Orquesta está lista y aprendiendo...")
    app.run(
        host="0.0.0.0",  
        port=port,
        debug=False      
    )
