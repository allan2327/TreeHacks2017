import os
import sys
import json
import psycopg2
import urlparse
import requests
from flask import Flask, request
from flask.ext.sqlalchemy import SQLAlchemy
from wit import Wit

current_user = 'rj'
def send(request, response):
    recipient_id = request['session_id']
    text = response['text']
    send_message(recipient_id, text)

def initializeSession(request):
    print('REQUEST: '+ str(request))
    global current_user
    current_user = request['entities']['email'][0]['value']
    current = Report.query.filter(Report.id == 0).first()
    current.email = current_user
    db.session.commit()
    print('CURRENT USER: ' + str(current_user))
    report = Report(current_user)
    db.session.add(report)
    db.session.commit()
    return request['context']

def storeHandle(request):
    print('REQUEST: ' + str(request))
    context = request['context']
    entry = dict()
    entry['confidence'] = 0

    for val in request['entities']['handle']: # obtain highest confidence entry
        if val['confidence'] > entry['confidence']:
            entry = val

    bully = Bullies(entry['value'])
    db.session.add(bully)
    db.session.commit()
    return context

def storeTweet(request):
    context = request['context']
    entry = dict()
    entry['confidence'] = 0
    print request
    for val in request['entities']['url']: # obtain highest confidence entry
        if val['confidence'] > entry['confidence']:
            entry = val

    tweet = Tweet(entry['value'])
    db.session.add(tweet)
    db.session.commit()
    return context

actions = {
    'send': send,
    'initializeSession': initializeSession,
    'storeHandle': storeHandle,
    'storeTweet': storeTweet
}

access_token = os.environ['WIT_ACCESS_TOKEN']

client = Wit(access_token=access_token, actions=actions)

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']
db = SQLAlchemy(app)

class Tweet(db.Model):
    __tablename__ = "tweets"
    report_id = db.Column(db.Integer, primary_key=True)
    tweet_url = db.Column(db.String, primary_key=True)
    def __init__(self, tweet_url):
        self.tweet_url = tweet_url
        current_user = Report.query.filter(Report.id == 0).first().email
        print("TWEET CURRENT USER*****: " + str(current_user))
        self.report_id = Report.query.filter(Report.email == current_user, Report.is_active == True).first().id


class Bullies(db.Model):
    __tablename__ = "bullies"
    report_id = db.Column(db.Integer, primary_key=True)
    handle = db.Column(db.String, primary_key = True)
    def __init__(self, handle):
        current_user = Report.query.filter(Report.id == 0).first().email
        print("BULLY CURRENT USER*****: " + str(current_user))
        self.handle = handle
        self.report_id = Report.query.filter(Report.email == current_user, Report.is_active == True).first().id

class Report(db.Model):
    __tablename__ = "report"
    id = db.Column(db.Integer, primary_key=True)
    is_active = db.Column(db.Boolean)
    email = db.Column(db.String)
    def __init__(self, email):
        self.is_active = True
        self.email = email

@app.route('/', methods=['GET'])
def verify():
    # when the endpoint is registered as a webhook, it must echo back
    # the 'hub.challenge' value it receives in the query arguments
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.challenge"):
        if not request.args.get("hub.verify_token") == os.environ["VERIFY_TOKEN"]:
            return "Verification token mismatch", 403
        return request.args["hub.challenge"], 200

    return "Hello Robbie and Tofe", 200


@app.route('/', methods=['POST'])
def webhook():

    # endpoint for processing incoming messaging events

    data = request.get_json()
    log(data)  # you may not want to log every incoming message in production, but it's good for testing

    if data["object"] == "page":

        for entry in data["entry"]:
            for messaging_event in entry["messaging"]:

                if messaging_event.get("message"):  # someone sent us a message

                    sender_id = messaging_event["sender"]["id"]        # the facebook ID of the person sending you the message
                    recipient_id = messaging_event["recipient"]["id"]  # the recipient's ID, which should be your page's facebook ID
                    message_text = messaging_event["message"]["text"]  # the message's text

                    client.run_actions(session_id=sender_id, message=message_text)


                if messaging_event.get("delivery"):  # delivery confirmation
                    pass

                if messaging_event.get("optin"):  # optin confirmation
                    pass

                if messaging_event.get("postback"):  # user clicked/tapped "postback" button in earlier message
                    pass

    return "ok", 200



def send_message(recipient_id, message_text):

    log("sending message to {recipient}: {text}".format(recipient=recipient_id, text=message_text))

    params = {
        "access_token": os.environ["PAGE_ACCESS_TOKEN"]
    }
    headers = {
        "Content-Type": "application/json"
    }
    data = json.dumps({
        "recipient": {
            "id": recipient_id
        },
        "message": {
            "text": message_text
        }
    })
    r = requests.post("https://graph.facebook.com/v2.6/me/messages", params=params, headers=headers, data=data)
    if r.status_code != 200:
        log(r.status_code)
        log(r.text)


def log(message):  # simple wrapper for logging to stdout on heroku
    print str(message)
    sys.stdout.flush()


if __name__ == '__main__':
    app.run(debug=True)

