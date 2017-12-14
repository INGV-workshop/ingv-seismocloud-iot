from cloudant import Cloudant
from flask import Flask, render_template, request, jsonify
import atexit
import cf_deployment_tracker
import os
import json
import time
import requests
import datetime
import random
from random import randint
import math
import ibmiotf.device
from requests.auth import HTTPBasicAuth


app = Flask(__name__)

db_name = 'mydb'
client = None
db = None

organization = None
deviceType = None
deviceId = None
authMethod = None
authToken = None

if 'VCAP_SERVICES' in os.environ:
    vcap = json.loads(os.getenv('VCAP_SERVICES'))
    print('Found VCAP_SERVICES')
    if 'cloudantNoSQLDB' in vcap:
        creds = vcap['cloudantNoSQLDB'][0]['credentials']
        user = creds['username']
        password = creds['password']
        url = 'https://' + creds['host']
        client = Cloudant(user, password, url=url, connect=True)
        db = client.create_database(db_name, throw_on_exists=False)
elif os.path.isfile('vcap-local.json'):
    with open('vcap-local.json') as f:
        vcap = json.load(f)
        print('Found local VCAP_SERVICES')
        creds = vcap['services']['cloudantNoSQLDB'][0]['credentials']
        user = creds['username']
        password = creds['password']
        url = 'https://' + creds['host']
        client = Cloudant(user, password, url=url, connect=True)
        db = client.create_database(db_name, throw_on_exists=False)

# On Bluemix, get the port number from the environment variable PORT
# When running this app on the local machine, default the port to 8000
port = int(os.getenv('PORT', 8000))

@app.route('/')
def home():
    return render_template('index.html')

# /* Endpoint to greet and add a new visitor to database.
# * Send a POST request to localhost:8000/api/visitors with body
# * {
# *     "name": "Bob"
# * }
# */
@app.route('/api/visitors', methods=['GET'])
def get_visitor():
    if client is not None:
        return jsonify(list(map(lambda doc: doc['name'], db)))
    else:
        print('No database')
        return jsonify([])

# /**
#  * Endpoint to get a JSON array of all the visitors in the database
#  * REST API example:
#  * <code>
#  * GET http://localhost:8000/api/visitors
#  * </code>
#  *
#  * Response:
#  * [ "Bob", "Jane" ]
#  * @return An array of all the visitor names
#  */
@app.route('/api/visitors', methods=['POST'])
def put_visitor():
    if request is not None:
        user = request.json['name']
        if client is not None:
            data = {'name':user}
            db.create_document(data)
            return 'Hello %s! I added you to the database.' % user
        else:
            print('No database')
            return 'Hello %s!' % user
    else:
        print ('Request is none')

@app.route('/api/register', methods=['POST'])
def put_device():
    if 'key' in os.environ:
        key = os.getenv('key')
        token = os.getenv('token')
        org = os.getenv('org')
        type = os.getenv('type')

    basic = HTTPBasicAuth(key, token)
    url = "https://" + org + ".internetofthings.ibmcloud.com/api/v0002/device/types/" + type + "/devices"
    global deviceId
    deviceId = request.json['deviceId']
    data = {"deviceId" : deviceId, "authToken": "123456zzzz"}
    data_json = json.dumps(data)

    print (data_json)

    headers = {'Content-type': 'application/json'}

    response = requests.post(url, auth=basic, data=data_json, headers=headers)
    print(response.text)

    data = response.json()
    
    clientid = data['clientId']
    tokens = clientid.split(":")
    organization = tokens[1]
    print (organization)
    deviceType = tokens[2]
    print (deviceType)
    authToken = data['authToken']
    print(authToken)

    result = {
        "org": organization,
        "type": deviceType,
        "id": deviceId,
        "auth-method": "token",
        "auth-token": authToken
    }

    return json.dumps(result) 


@app.route('/api/registration', methods=['GET'])
def get_device():
    return jsonify({"deviceid": deviceId, "deviceType": deviceType, "org":organization, "token":authToken})


@app.route('/api/publish', methods=['POST'])
def emit_event():
    data = request.get_json()

    global organization
    if organization is None:
        organization = os.getenv('org')

    global deviceType
    if deviceType is None:
	deviceType = os.getenv('type')

    global deviceId
    if deviceId is None:
	deviceId = data['deviceId']

    global authToken
    if authToken is None:
	authToken = "123456zzzz"

    options = {
        "org": organization,
        "type": deviceType,
        "id": deviceId,
        "auth-method": "token",
        "auth-token": authToken
    }
    count = 0;
    client = ibmiotf.device.Client(options)
    client.connect()
    evnum = request.json['num']
    lat_start = data['latitude']
    lon_start = data['longitude']
    lat_last = lat_start
    lon_last = lon_start

    for x in range (0, evnum):
        now = datetime.datetime.now()
	dec_lat = random.random()
        dec_lon = random.random()

        selector = randint(0,1)

        if selector > 0.5:
	    latitude = lat_last
            longitude = lon_last
        else:
            latitude = float("{0:.6f}".format(lat_start+dec_lat))
	    longitude = float("{0:.6f}".format(lon_start+dec_lon))
            lat_last = latitude
	    lon_last = longitude

        data['latitude'] = latitude
	data['longitude'] = longitude
        data['time'] = now.strftime("%a,%d-%b-%Y %I:%M:%S %Z")
        data.pop('num', None)
        data.pop('deviceId', None)
	def myOnPublishCallback():
                print("Confirmed event %s received by IoTF\n" % x)
	
	success = client.publishEvent("greeting", "json", data, qos=0, on_publish=myOnPublishCallback)
	if not success:
		print("Not connected to IoTF")
        sr = randint(500,1500)
	time.sleep(sr/1000)
        count+=1	

    # Disconnect the device and application from the cloud
    client.disconnect()
    return 'sent %s events' % count

    
@atexit.register
def shutdown():
    if client is not None:
        client.disconnect()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=port, debug=True)
