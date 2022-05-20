import os
from flask import Flask, render_template
from resallocserver.app import session_scope
from resallocserver.app import app as application
from resalloc.helpers import load_config_file
from resallocserver import models
from resallocwebui import static_folder

tmpl_dir = os.path.join(static_folder, "templates")
app = Flask(__name__, template_folder=tmpl_dir)
app.static_folder = os.path.join(static_folder, "static")


@app.route("/")
def home():
    return "OK"


@app.route('/resources')
def resources():
    with session_scope() as session:
        resources = session.query(models.Resource)
    config = application.instantiate_config()
    pools = load_config_file(os.path.join(config["config_dir"], "pools.yaml"))
    resources_list = append_resources(resources)
    resources_status = {}
    status = {"UP": 0, "STARTING": 0, "DELETING": 0, "RELEASING": 0, "ENDED": 0, "TAKEN": 0}
    for resource in resources_list:
        resources_status.setdefault(resource["pool"], status)
        resources_status[resource["pool"]][resource["status"]] += 1
        if resource["ticket"]:
            resources_status[resource["pool"]]["TAKEN"] += 1
    information = {}
    for name, status in resources_status.items():
        information[name] = {
            "available": pools[name]["max"] - status["TAKEN"],
            "max": pools[name]["max"],
            "status": status,
        }
    return render_template('resources.html', information=information)


def append_resources(resources):
    resources_list = []
    for resource in resources.all():
        resources_list.append({
            'id': resource.id,
            'name': resource.name,
            'pool': resource.pool,
            'tags': ', '.join(list(resource.tag_set)),
            'status': resource.state,
            'releases': resource.releases_counter,
            'ticket': resource.ticket.id if resource.ticket else None,
        })
    return resources_list


if __name__ == '__main__':
    app.run(host="0.0.0.0")
