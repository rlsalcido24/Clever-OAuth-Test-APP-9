# A sample Clever Instant Login implementation.
# Uses the Bottle framework and raw HTTP requests to demonstrate the OAuth2 flow.
import base64
import json
import os
import requests
import urllib

from bottle import app, redirect, request, route, run, template
from beaker.middleware import SessionMiddleware

# Obtain your Client ID and secret from your Clever developer dashboard at https://account.clever.com/partner/applications
CLIENT_ID = os.environ['CLIENT_ID']
CLIENT_SECRET = os.environ['CLIENT_SECRET']

PORT = int(os.environ.get('PORT', 2587))

# Clever redirect URIs must be preregistered on your developer dashboard.
# If using the default PORT set above, make sure to register "http://localhost:2587/oauth".
# Redirect URI is https://cryptic-retreat-43545.herokuapp.com/oauth on production. Also the
# host on production is "0.0.0.0". Those are the only differences between the
# dvelopment code and the production code.
REDIRECT_URI = 'http://localhost:{port}/oauth'.format(port=PORT)
CLEVER_OAUTH_URL = 'https://clever.com/oauth/tokens'
CLEVER_API_BASE = 'https://api.clever.com'

# Use the bottle session middleware to store an object to represent a "logged in" state.
session_opts = {
	'session.type': 'memory',
	'session.cookie_expires': 300,
	'session.auto': True
}
myapp = SessionMiddleware(app(), session_opts)

# Our home page route will create a Clever Instant Login button.
@route('/')
def index():
	encoded_string = urllib.urlencode({
		'response_type': 'code',
		'redirect_uri': REDIRECT_URI,
		'client_id': CLIENT_ID,
		'scope': 'read:user_id read:sis'        
	})
	return template("<h1>Login!<br/><br/> \
		<a href='https://clever.com/oauth/authorize?" + encoded_string +
		"'><img src='http://assets.clever.com/sign-in-with-clever/sign-in-with-clever-small.png'/></a></h1>"
	)

# Our OAuth 2.0 redirect URI location corresponds to what we've set above as our REDIRECT_URI
# When this route is executed, we will retrieve the "code" parameter and exchange it for a Clever access token.
# After receiving the access token, we use it with api.clever.com/me to determine its owner,
# save our session state, and redirect our user to our application.
@route('/oauth')
def oauth():
	code = request.query.code
	encoded_string = urllib.urlencode({
		'response_type': 'code',
		'redirect_uri': REDIRECT_URI,
		'client_id': CLIENT_ID,
		'scope': 'read:user_id read:sis'        
	})

	payload = {
		'code': code,
		'grant_type': 'authorization_code',
		'redirect_uri': REDIRECT_URI
	}

	headers = {
		'Authorization': 'Basic {base64string}'.format(base64string =
			base64.b64encode(CLIENT_ID + ':' + CLIENT_SECRET)),
		'Content-Type': 'application/json',
	}

	# This logic deals with handling errors when calling Clever's /OAuth API. If an error arises, the script
	# will stop running and inform the user that an error occured and that they should attempt try to log in again
	# by using the "Log in With Clever" link provided. 

	response = requests.post(CLEVER_OAUTH_URL, data=json.dumps(payload), headers=headers)
	httpcode = response.status_code
	if httpcode != 200:
		return template("<h1>Error in previous login attempt. Please try again!<br/><br/> \
			<a href='https://clever.com/oauth/authorize?" + encoded_string +
			"'><img src='http://assets.clever.com/sign-in-with-clever/sign-in-with-clever-small.png'/></a></h1>"
		)
	else:
		jsonresponse = response.json()
		token = jsonresponse['access_token']

		bearer_headers = {
			'Authorization': 'Bearer {token}'.format(token=token)}
	

	# This logic deals with handling errors when calling Clever's /ME API. If an error arises, the script
	# will stop running and inform the user that an error occured and that they should attempt try to log in again
	# by using the "Log in With Clever" link provided. 

		result = requests.get(CLEVER_API_BASE + '/me', headers=bearer_headers)
		httpcode2 = result.status_code
		if httpcode2 != 200:
			return template("<h1>Error in previous login attempt. Please try again!<br/><br/> \
				<a href='https://clever.com/oauth/authorize?" + encoded_string +
				"'><img src='http://assets.clever.com/sign-in-with-clever/sign-in-with-clever-small.png'/></a></h1>"
			)
		else:
			jsonresult = result.json()
			data = jsonresult['data']

	# Only handle student and teacher logins for our app (other types include districts)
			if data['type'] != 'student' and data['type'] != 'teacher':
				return template ("You must be a student or teacher to log in to this app but you are a {{type}}.", type=data['type'])
			else:
				if 'name' in data: #SIS scope
					nameObject = data['name']
				else:
					if data['type'] == 'student':
						studentId = data['id']
						studentinfo = requests.get(CLEVER_API_BASE + '/v1.1/students/{studentId}'.format(studentId=studentId),headers=bearer_headers).json()
			
						nameObject = studentinfo['data']['name']
		
						session = request.environ.get('beaker.session')
						session['nameObject'] = nameObject

						redirect('/app')
					else:
						if data['type'] == 'teacher':
							teacherId = data['id']
							teacherinfo = requests.get(CLEVER_API_BASE + '/v1.1/teachers/{teacherId}'.format(teacherId=teacherId),headers=bearer_headers).json()
							
							nameObject = teacherinfo['data']['name']
		
							session = request.environ.get('beaker.session')
							session['nameObject'] = nameObject

							redirect('/app')

# Our application logic lives here and is reserved only for users we've authenticated and identified.
@route('/app')
def app():
	session = request.environ.get('beaker.session')
	if 'nameObject' in session:
		nameObject = session['nameObject']
		return template("You are now logged in as {{name}}", name=nameObject['first'] + ' ' + nameObject['last'])
	else:
		return "You must be logged in to see this page! Click <a href='/'>here</a> to log in."

if __name__ == '__main__':
	run(app=myapp, host='localhost', port=PORT)
