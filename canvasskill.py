import datetime as dt
import re
# lists of synonyms for stuff coming in from Alexa
weeks = [ "this week", "this next week", "for the next week", "for this week", "for the week",
            "in the next week", "in this week", "week"]
tomorrows = ["in the next 2 days", "for tomorrow", "tomorrow"]
todays = [ "for today", "today"]

homeworks = [ "homework", "homeworks", "task", "tasks", "project", "projects", "assignment", "assignments", "hw", "lab", "labs"]
exams = ["exam", "exams", "tests", "midterm", "midterms", "examination", "examinations", "quiz", "quizzes", "test"]

# tested, is ok
def getEndDate(type, time):
    # time assumed to be str, all lower case
    # returns a date instance
    now = dt.date.today()
    if time == "week":
        end = now + dt.timedelta(weeks=1)
    elif time == "tomorrow":
        end = now + dt.timedelta(days=1)
    elif time == "today":
        end = now # this works because we are only dealing with dates right now
    else: # selecting default values for the type
        if type == "test":
            end = now + dt.timedelta(weeks=1)
        else: # assignments or default
            end = now + dt.timedelta(days=1)

    return end

# tested, seems pretty ok
def getThisDate(date_str):
    # get the next date
    if re.search("DTEND:([0-9]{8})", date_str):
        d = re.search("DTEND:([0-9]{8})", date_str).groups()[0]
    else:
        d = re.search("DTEND;VALUE=DATE:([0-9]{8})", date_str).groups()[0]
    # d is a str of exactly 8 chars
    # set this date to the date of the next thing
    return dt.date(year=int(d[:4]), month=int(d[4:6]), day=int(d[6:]))

def cleanUpTime(t):
    if t in weeks:
        return "week"
    elif t in tomorrows:
        return "tomorrow"
    elif t in todays:
        return "today"
    else:
        return None

def cleanUpType(t):
    if t in exams:
        return "test"
    elif t in homeworks:
        return "hw"
    else:
        return None

# tested, is ok
def make_msg(d):
    ret = "In " + d['class'] + ", you have "
    ret += d['name'] + " on " + d['date'] + ". \n"
    return ret


def canvas_skill(type=None, time=None):
    cal_file = open('canvas_test_data.txt')
    # this is the entire ics file as a str
    cal_str = cal_file.read()
    end = getEndDate(type, time)
    print("end date: ", end)
    # list [] of events
    events = cal_str.split("END:VEVENT")[:-1]

    assignment_list = []
    i = 0
    now = dt.date.today()
    # find all the assignments before the specified end date
    for e in events:
        try:
            print("loop iteration")
            thisdate = getThisDate(e)
            # the next assignment is still within the date frame we want
            if thisdate < now:
                # skip old assignments
                continue
            elif thisdate > end:
                # these assignments are too far in the future, so stop looking
                break
            else:
                assignment_list.append([e, thisdate])
            # get the next date
        except IndexError:
            # we have reached the end of the file
            break

    # now we have a list of strings of all events in the right date range

    # lists of dicts? tentatively?
    tests = []
    hw = []

    for a in assignment_list:
        assignRE = re.compile("UID:event-assignment")
        # let's filter out anything that isn't an assignment
        if not assignRE.search(a[0]):
            # it's not an assignment, so remove it
            continue
        # at this point, we'll parse the raw ICS into something sensible, then sort by type.
        # the chunk b/n SUMMARY: and UID: is what we want, so get that and put it in a temp string
        s = a[0].split("SUMMARY:")[1].split("UID:")[0].strip()
        # s is of the form "Assignment Name [Class]"

        name = s.split("[")[0].strip()
        cls = s.split("[")[1].replace("]","").strip()
        cls = " ".join([cls.split("-")[0], cls.split("-")[1]])

        # attempt to format the date as a str
        md_str = a[1].strftime("%A")
        d = {'name': name, 'class': cls, 'date': md_str}

        if re.search("test|exam|quiz|midterm|mid-term", name, flags=re.IGNORECASE):
            # this is a test-like object, so put it in the test list
            tests.append(d)
        else:
            # this is a homework like object, so put it in the hw list
            hw.append(d)


    # now, time to put together the message and send it back to Alexa

    if type == "test":
        msg = "You have " + str(len(tests)) + " tests and quizzes coming up.\n"
        for t in tests:
            msg += make_msg(t)
    elif type == "hw":
        msg = "You have " + str(len(hw)) + " assignments coming up.\n"
        for h in hw:
            msg += make_msg(h)
    else:
        msg = "You have " + str(len(tests)) + " tests and quizzes coming up.\n"
        for t in tests:
            msg += make_msg(t)
        msg += "You have " + str(len(hw)) + " assignments coming up.\n"
        for h in hw:
            msg += make_msg(h)

    msg += " Good luck studying!"
    return msg

# JSON formatting helpers. Also lifted from AWS tutorials
def build_speechlet_response(title, output, reprompt_text, should_end_session):
    return {
        'outputSpeech': {
            'type': 'PlainText',
            'text': output
        },
        'card': {
            'type': 'Simple',
            'title': "Upcoming",
            'content': output
        },
        'reprompt': {
            'outputSpeech': {
                'type': 'PlainText',
                'text': reprompt_text
            }
        },
        'shouldEndSession': should_end_session
    }


def build_response(session_attributes, speechlet_response):
    return {
        'version': '1.0',
        'sessionAttributes': session_attributes,
        'response': speechlet_response
    }

# these are messages for different events
# most of this is copied from the AWS tutorials
def get_help_message():
    help_msg = "Invoke study buddy to inquire about your canvas homework due dates and test dates today, tomorrow, or within the next week."
    return build_response({}, build_speechlet_response(
        "HelpIntent", help_msg, None, True))

def handle_session_end_request():
    card_title = "Session Ended"
    speech_output = "Good luck studying!"
    # Setting this to true ends the session and exits the skill.
    should_end_session = True
    return build_response({}, build_speechlet_response(
        card_title, speech_output, None, should_end_session))

def parse_json(intent, session):
    """Parse the intent dict from the JSON request and pass those parameters to canvas_skill()"""
    time_dict = intent['slots']['time']
    type_dict = intent['slots']['type']

    my_time = cleanUpTime(time_dict.get('value', None))
    my_type = cleanUpType(type_dict.get('value', None))

    speech_msg = canvas_skill(type=my_type, time=my_time)

    return build_response({}, build_speechlet_response(
        intent['name'], speech_msg, None, True))

# these are the different kinds of intents we handle
# most of this code lifted from the AWS tutorials
def on_session_started(session_started_request, session):
    """ Called when the session starts """

    print("on_session_started requestId=" + session_started_request['requestId']
          + ", sessionId=" + session['sessionId'])


def on_launch(launch_request, session):
    """ Called when the user launches the skill without specifying what they
    want
    """
    print("on_launch requestId=" + launch_request['requestId'] +
          ", sessionId=" + session['sessionId'])
    # Dispatch to your skill's launch
    return None


def on_intent(intent_request, session):
    """ Called when the user specifies an intent for this skill """

    print("on_intent requestId=" + intent_request['requestId'] +
          ", sessionId=" + session['sessionId'])

    intent = intent_request['intent']
    intent_name = intent_request['intent']['name']

    # Dispatch to your skill's intent handlers
    if intent_name == "CanvasIntent":
        return parse_json(intent, session)
    elif intent_name == "AMAZON.HelpIntent":
        return get_help_message()
    elif intent_name == "AMAZON.CancelIntent" or intent_name == "AMAZON.StopIntent":
        return handle_session_end_request()
    else:
        raise ValueError("Invalid intent")


def on_session_ended(session_ended_request, session):
    """ Called when the user ends the session.

    Is not called when the skill returns should_end_session=true
    """
    print("on_session_ended requestId=" + session_ended_request['requestId'] +
          ", sessionId=" + session['sessionId'])
    # add cleanup logic here


def lambda_handler(event, context):
    """ Route the incoming request based on type (LaunchRequest, IntentRequest,
    etc.) The JSON body of the request is provided in the event parameter.
    """
    print("event.session.application.applicationId=" +
          event['session']['application']['applicationId'])

    if event['session']['new']:
        on_session_started({'requestId': event['request']['requestId']},
                           event['session'])

    if event['request']['type'] == "LaunchRequest":
        return on_launch(event['request'], event['session'])
    elif event['request']['type'] == "IntentRequest":
        return on_intent(event['request'], event['session'])
    elif event['request']['type'] == "SessionEndedRequest":
        return on_session_ended(event['request'], event['session'])
