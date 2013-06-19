import logging
import json
import urllib
import base64
import uuid
import re
import collections
import copy
import webapp2

from xml.etree import ElementTree as ET
from google.appengine.api import urlfetch

BASE_ACTIVITY_ID = 'http://mlearnconsms.appspot.com/xapi/activities/shirtbill'


#message is what will show when this state is *reached*
#TODO: figure all that out.
State = collections.namedtuple('State', ['transition', 'message'])

def first_step(identity, message):
    #obviously unsatisfactory, but this is a demo with few dependencies
    if len(message) > 3 and '@' in message:
        identity['email'] = message
        report_experience(identity, 'began', response=message)
        return '1'
    else:
        raise Exception("Please respond with an email")

def step_into(step):
    def _transition(identity, message):
        if message != 'next':
            raise Exception("Send 'next' to go to the next step")
        report_experience(identity, 'transitioned to', step, STATES[step].message, response=message)
        return step
    return _transition

def end_jump(identity, message):
    if message == 'start over':
        report_experience(identity, 'started over', response=message)
        return '1'
    else:
        raise Exception("Send 'start over' to go back to the beginning")

STATES = {
    'begin': State(first_step,
"""Welcome! Please respond with your email so we can keep a record."""
),

    '1': State(step_into('2'),
"""Step 1. You're going to learn to make a shirt from a one dollar bill. It'll look like this when you're done:

http://s3.amazonaws.com/sbox-random/shirt11_1_.jpg

Reply with 'next' to get started and 'next' to proceed past each step.
Send 'help' at any time to see help, or send the number of any step to jump straight to it"""),

    '2': State(step_into('3'),
"""Step 2. As with all these designs, try to start with a relatively clean, crisp bill. It will make it much easier. All folds should be sharply creased. It helps to go over the fold with a fingernail on a flat, hard surface.

Start by folding the bill precisely in half lengthwise. 
Unfold the bill, leaving the crease produced by the fold for the next step...

http://s3.amazonaws.com/sbox-random/shirt1_1_.jpg"""),

    '3': State(step_into('4'),
"""Step 3. Fold the bill one quarter of the way in from each side lengthwise. The edge of the bill should just meet the crease made by the fold in the previous step. 

Do this for both sides as shown.

http://s3.amazonaws.com/sbox-random/shirt2_1_.jpg"""),
    '4': State(step_into('5'),
"""Step 4. Turn the bill over. Fold the white of one end over as shown. 

This will become the collar in the next step...

http://s3.amazonaws.com/sbox-random/fade_edge_note.jpg"""),
    '5': State(step_into('6'),
"""Step 5. Turn the bill over again. 
From this side, fold in the two corners at an angle from the edge.

http://s3.amazonaws.com/sbox-random/shirt4_2_.jpg

The angle is not terribly important but the two points should meet at the centreline as shown. 

http://s3.amazonaws.com/sbox-random/shirt4_1_.jpg"""),
    '6': State(step_into('7'),
"""Step 6. Fold a little less than one third of the bill lengthwise from the opposite end as shown. 

http://s3.amazonaws.com/sbox-random/shirt5_1_.jpg"""),
    '7': State(step_into('8'),
"""Step 7. Now you will fold inward in the same direction, tucking the previous fold under the "collar". 

http://s3.amazonaws.com/sbox-random/shirt6_1_.jpg

Wait, there's more..."""),
    '8': State(step_into('9'),
"""Step 8. Open up all the folds whilst keeping the collar folds and all the creases intact.
On the lateral fold furthest from the collar, refold it straight across as shown. 

http://s3.amazonaws.com/sbox-random/shirt7_1_.jpg"""),
    '9': State(step_into('10'),
"""Step 9. You are going to introduce two new folds on each "sleeve". 

Do this by holding each side of the previous fold between thumb and forefinger in the orientation shown, just on either side of the vertical fold as shown. 

Force the angle to close slightly, and force the extra paper inside the vertical folds. 

Once you've got it looking right, force the insides to crease by pressing on a hard surface. 

http://s3.amazonaws.com/sbox-random/shirt8_1_.jpg"""),
    '10': State(step_into('end'),
"""Step 10. This is what it should look like after both sides are complete...

http://s3.amazonaws.com/sbox-random/shirt10_1_.jpg

Now re-tuck the fold you've been working on back under the collar, and you're done!"""),
    'end': State(end_jump,
"""It should look about like this. 

With the basic shape, the collar and the sleeves, it should be recognizable. 

http://s3.amazonaws.com/sbox-random/shirt11_1_.jpg

To start from the beginning of the instructions, send 'start over'.
""")

}

def retrieve_profile(number, lrs, credentials):
    params = {
        'activityId': BASE_ACTIVITY_ID,
        'profileId': number
    }
    url = 'https://%s.waxlrs.com/TCAPI/activities/profile?%s' % (lrs, urllib.urlencode(params))
    headers = {
        'x-experience-api-version': '1.0.0',
        'authorization': 'Basic %s' % base64.b64encode(credentials)
    }
    response = urlfetch.fetch(url, headers=headers, deadline=60)
    if response.status_code == 200:
        metadata = json.loads(response.content)
        metadata['etag'] = response.headers['etag']
        return metadata
    elif response.status_code == 404:
        logging.info('Nothing there! %s', response.headers)
        return {}
    else:
        logging.warning("problem with response %s %s %s", response.status_code, response.headers, response.content)
        raise Exception("Problem!")

def retrieve_metadata(number, lrs, credentials):
    metadata = {
        'number': number,
        'lrs': lrs,
        'credentials': credentials
    }
    metadata.update(retrieve_profile(number, lrs, credentials))
    return metadata

def save_profile(number, profile):
    params = {
        'activityId': BASE_ACTIVITY_ID,
        'profileId': number
    }
    url = 'https://%s.waxlrs.com/TCAPI/activities/profile?%s' % (profile['lrs'], urllib.urlencode(params))
    headers = {
        'x-experience-api-version': '1.0.0',
        'authorization': 'Basic %s' % base64.b64encode(profile['credentials']),
        'content-type': 'application/json'
    }
    if 'etag' in profile:
        headers['if-match'] = profile['etag']
    else:
        headers['if-none-match'] = '*'
    profile2 = copy.deepcopy(profile)
    del profile2['lrs']
    del profile2['credentials']
    response = urlfetch.fetch(url, headers=headers, method=urlfetch.PUT, payload=json.dumps(profile2), deadline=60)
    #TODO HERE: add try agains

def transition(identity, message):
    if 'state' not in identity:
        identity['state'] = 'begin'
        identity['registration'] = str(uuid.uuid4())
    else:
        state = identity['state']
        model = STATES[state]
        try:
            identity['state'] = model.transition(identity, message)
        except Exception as e: #problem with message
            logging.exception('unable to transition, sending message %s', e.message)
            return e.message
    logging.info('saving profile %s', identity)
    save_profile(identity['number'], identity)
    logging.info('sending message %s', STATES[identity['state']].message)
    return STATES[identity['state']].message


BREAKER_RE = re.compile(r'\s*(?P<chunk>.{1,159})(?:\s+|\s*$)')

def breakdown(response):
    while response:
        match = BREAKER_RE.match(response)
        response = response[match.end():]
        yield match.group('chunk')


def is_command(message):
    return message in ['reset', 'help'] or message in STATES

def command_transition(identity, message):
    if message == 'help':
        if 'email' in identity:
            report_experience(identity, 'asked for help in', response='help')
        return """To go to the next step, send 'next'.
To jump to a particular step, send the number of the step (1-10)."""
    elif message in STATES:
        if 'email' in identity:
            report_experience(identity, 'jumped to', message, STATES[message].message, response=message)
        identity['state'] = message
        save_profile(identity['number'], identity)
        return STATES[message].message
    elif message == 'reset':
        reset_identity = {}
        if 'etag' in identity:
            reset_identity['etag'] = identity['etag']
            reset_identity['lrs'] = identity['lrs']
            reset_identity['credentials'] = identity['credentials']
        save_profile(identity['number'], reset_identity)
        return "Reset finished"
    raise Exception("Should not be possible, is_command let us in")


def report_experience(identity, verb, activity=None, description=None, response=None):
    logging.info('reporting experience %s %s %s %s %s', identity, verb, activity, description, response)
    url = 'https://%s.waxlrs.com/TCAPI/statements' % identity['lrs']
    headers = {
        'x-experience-api-version': '1.0.0',
        'authorization': 'Basic %s' % base64.b64encode(identity['credentials']),
        'content-type': 'application/json'
    }
    activity_id = BASE_ACTIVITY_ID + '/' + activity if activity else BASE_ACTIVITY_ID
    description = description or 'Dollar Bill Shirt Folding'
    statement = {
        'id': str(uuid.uuid4()),
        'actor': {
            'name': identity['number'],
            'mbox': 'mailto:%s' % identity['email'] #really need to escape first part of email, but demo
        },
        'verb': {
            'id': 'http://mlearnconsms.appspot.com/xapi/verbs/%s' % verb.replace(' ', '_'),
            'display': {
                'en': verb
            }
        },
        'object': {
            'id': activity_id,
            'definition': {
                'description': {
                    'en': description
                }
            }
        },
        'context': {
            'registration': identity['registration']
        }
    }
    if activity_id != BASE_ACTIVITY_ID:
        statement['context']['contextActivities'] = {
            'parent': [{
                'id': BASE_ACTIVITY_ID,
                'definition': {
                    'description': {
                        'en': 'Dollar Bill Shirt Folding'
                    }
                }
            }]
        }
    if response:
        statement['result'] = {
            'response': response
        }
    urlfetch.fetch(url, headers=headers, method=urlfetch.POST, payload=json.dumps(statement), deadline=60)

class MainPage(webapp2.RequestHandler):
    def get(self, lrs, user, password):
        self.response.headers['Content-Type'] = 'text/plain'
        self.response.write('Hello, world!')
    def post(self, lrs, user, password):
        credentials = user + ':' + password
        logging.info("LRS %s, credentials '%s'", lrs, credentials)
        number = self.request.get('From')
        message = self.request.get('Body').strip().lower()

        identity = retrieve_metadata(number, lrs, credentials)
        logging.info('metadata %s', identity)
        if is_command(message): #email proxies for necessary info
            logging.info('received command %s', message)
            self.respond(command_transition(identity, message))
            return
        logging.info('transitioning based on %s', message)
        response = transition(identity, message)
        self.respond(response)
    def respond(self, response):
        logging.info("responding with %s", response)
        if len(response) < 160:
            logging.info("short response")
            self.response.headers['Content-Type'] = 'text/plain'
            self.response.write(response)
        else:
            logging.info("long response")
            twiml = ET.TreeBuilder()
            twiml.start('Response', {})
            for chunk in breakdown(response):
                twiml.start('Sms', {})
                twiml.data(chunk)
                twiml.end('Sms')
            twiml.end('Response')
            self.response.headers['Content-Type'] = 'text/xml'
            self.response.write(ET.tostring(twiml.close()))


application = webapp2.WSGIApplication([
    webapp2.Route('/<lrs>/<user>/<password>', MainPage),
], debug=True)