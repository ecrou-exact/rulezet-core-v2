from app import create_app, db
import argparse
from flask import render_template, request, Response, session
import json
import os
from app.core.utils.init_db import create_admin


parser = argparse.ArgumentParser()
parser.add_argument("-i", "--init_db", help="Initialise the db if it not exist", action="store_true")
parser.add_argument("-r", "--recreate_db", help="Delete and initialise the db", action="store_true")
parser.add_argument("-d", "--delete_db", help="Delete the db", action="store_true")
args = parser.parse_args()

os.environ.setdefault('FLASKENV', 'development')

app = create_app()

@app.errorhandler(404)
def error_page_not_found(e):
    if request.path.startswith('/api/'):
        return Response(json.dumps({"status": "error", "reason": "404 Not Found"}, indent=2, sort_keys=True), mimetype='application/json'), 404
    return render_template('/utils/404.html'), 404


@app.errorhandler(500)
def error_page_internal_server_error(e):
    if request.path.startswith('/api/'):
        return Response(json.dumps({"status": "error", "reason": "500 Internal Server Error"}, indent=2, sort_keys=True), mimetype='application/json'), 500
    return render_template('/utils/500.html'), 500

@app.errorhandler(403)
def error_page_forbidden(e):
    if request.path.startswith('/api/'):
        return Response(json.dumps({"status": "error", "reason": "403 Forbidden"}, indent=2, sort_keys=True), mimetype='application/json'), 403
    return render_template('/utils/403.html'), 403
    

if args.init_db:
    with app.app_context():
        db.create_all()
        create_admin()
elif args.recreate_db:
    with app.app_context():
        db.drop_all()
        db.create_all()
elif args.delete_db:
    with app.app_context():
        db.drop_all()
else:
    app.run(host=app.config.get("FLASK_URL"), port=app.config.get("FLASK_PORT"))

