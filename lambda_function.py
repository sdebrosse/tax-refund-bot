import math
import dateutil.parser
import datetime
import time
import os
import logging
import boto3
import decimal
import json
import re
from boto3.dynamodb.conditions import Key, Attr

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


""" --- Helpers to build responses which match the structure of the necessary dialog actions --- """


def get_slots(intent_request):
    return intent_request['currentIntent']['slots']


def elicit_slot(session_attributes, intent_name, slots, slot_to_elicit, message):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'ElicitSlot',
            'intentName': intent_name,
            'slots': slots,
            'slotToElicit': slot_to_elicit,
            'message': message
        }
    }


def close(session_attributes, fulfillment_state, message):
    response = {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'Close',
            'fulfillmentState': fulfillment_state,
            'message': message
        }
    }

    return response


def delegate(session_attributes, slots):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'Delegate',
            'slots': slots
        }
    }


""" --- Helper Functions --- """


def parse_int(n):
    try:
        return int(n)
    except ValueError:
        return float('nan')


def build_validation_result(is_valid, violated_slot, message_content):
    if message_content is None:
        return {
            "isValid": is_valid,
            "violatedSlot": violated_slot,
        }

    return {
        'isValid': is_valid,
        'violatedSlot': violated_slot,
        'message': {'contentType': 'PlainText', 'content': message_content}
    }


def isvalid_date(date):
    try:
        dateutil.parser.parse(date)
        return True
    except ValueError:
        return False

def validate_tax_refund_info(ssn, zipCode, refundAmount):
   
    print("SSN is "+str(ssn))
    print("ZIP is "+str(zipCode))

    if ssn is not None:
        if len(ssn) != 9:
            # Not a valid ssn; use a prompt defined on the build-time model.
            return build_validation_result(False, 'SSN', 'That social security number does not seem to have the right number of digits. Can you try again?')
    if zipCode is not None:
        if len(zipCode) != 5:
            # Not a valid zip; use a prompt defined on the build-time model.
            return build_validation_result(False, 'zipCode', 'That zip code does not seem to have the right number of digits. Can you try again?')


    return build_validation_result(True, None, None)


""" --- Functions that control the bot's behavior --- """


def get_tax_refund_status(intent_request):

    ssn = get_slots(intent_request)["SSN"]
    refundAmount = get_slots(intent_request)["RefundAmount"]
    zipCode = get_slots(intent_request)["zipCode"]
    source = intent_request['invocationSource']

    if source == 'DialogCodeHook':
        slots = get_slots(intent_request)

        # Perform basic validation on the supplied input slots.
        validation_result = validate_tax_refund_info(ssn, zipCode, refundAmount)
        if not validation_result['isValid']:
            slots[validation_result['violatedSlot']] = None
            return elicit_slot(intent_request['sessionAttributes'],
                               intent_request['currentIntent']['name'],
                               slots,
                               validation_result['violatedSlot'],
                               validation_result['message'])

        output_session_attributes = intent_request['sessionAttributes'] if intent_request['sessionAttributes'] is not None else {}
        
        
        if intent_request['bot']['alias'] == 'demo_Connect':
            if ssn is not None:
                ssn = " ".join(ssn)
                ssn = insert_char(ssn, 5, ',')
                output_session_attributes['SSN_Formatted'] = insert_char(ssn, 10, ',')
            if refundAmount is not None:
                refundAmount = get_num(refundAmount)
                output_session_attributes['RefundAmount_Formatted'] = refundAmount
            if zipCode is not None:
                output_session_attributes['zipCode_Formatted'] = " ".join(zipCode)
        else:
            if ssn is not None:
                ssn = insert_char(ssn, 3, '-')
                ssn = insert_char(ssn, 6, '-')
                output_session_attributes['SSN_Formatted'] = ssn
            if refundAmount is not None:
                refundAmount = get_num(refundAmount)
                output_session_attributes['RefundAmount_Formatted'] = refundAmount
                intent_request['currentIntent']['slots']["RefundAmount"] = refundAmount
            if zipCode is not None:
                output_session_attributes['zipCode_Formatted'] = zipCode        
        return delegate(output_session_attributes, get_slots(intent_request))

    # Call DynamoDB to retrieve information about our tax payer's refund
    dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
    table = dynamodb.Table("taxpayers")
    
    if ssn=="*":
        items = table.scan()
    else:
        items = table.query(
            KeyConditionExpression=Key('SSN').eq(int(ssn))
        )
    

    if(len(items["Items"]) < 1):
        fulfillmentResponse = "Sorry, I don't have any record of that refund. Please try again and make sure you've entered all information correctly."
        return close(intent_request['sessionAttributes'],
                 'Fulfilled',
                 {'contentType': 'PlainText',
                  'content': fulfillmentResponse})
                  
    # The result we found by querying DynamoDB
    result = items["Items"][0]
    
    print(str(result))
    retrievedRefundAmount = result["refundAmount"];
    retrievedZipCode = result["zip"];
    retrievedRefundStatus = result["refundStatus"]
    
    # We're creating the upper and lower bounds for the acceptable refund amount the user can claim (for lookup purposes)
    upperBoundRefundAmount = retrievedRefundAmount * decimal.Decimal('1.05')
    lowerBoundRefundAmount = retrievedRefundAmount * decimal.Decimal('0.95')
    print(str(upperBoundRefundAmount))
    print(str(lowerBoundRefundAmount))
    print(str(zipCode))

    statusResponse = "";
    
    # Check our records against what the user provided to Lex. If it's incorrect, we let the user know we couldn't find a record of their refund.
    if(retrievedZipCode != decimal.Decimal(zipCode)):
        fulfillmentResponse = "Sorry, I don't have any record of that refund. Please try again and make sure you've entered all information correctly."
        return close(intent_request['sessionAttributes'],
                 'Fulfilled',
                 {'contentType': 'PlainText',
                  'content': fulfillmentResponse})
    elif(decimal.Decimal(refundAmount) > upperBoundRefundAmount):
        fulfillmentResponse = "Sorry, I don't have any record of that refund. Please try again and make sure you've entered all information correctly."
        return close(intent_request['sessionAttributes'],
                 'Fulfilled',
                 {'contentType': 'PlainText',
                  'content': fulfillmentResponse})
    elif(decimal.Decimal(refundAmount) < lowerBoundRefundAmount):
        fulfillmentResponse = "Sorry, I don't have any record of that refund. Please try again and make sure you've entered all information correctly."
        return close(intent_request['sessionAttributes'],
                 'Fulfilled',
                 {'contentType': 'PlainText',
                  'content': fulfillmentResponse})    
                  

    if(retrievedRefundStatus == "COMPLETE"):
        statusResponse = "The review process for your refund has been completed. It is scheduled for direct deposit within 2-4 business days."
    elif (retrievedRefundStatus == "UnderReview"):
        statusResponse = "Your refund has been received and it is currently under review. This process may take 1-2 business weeks."
    elif (retrievedRefundStatus == "RECEIVED"):
        statusResponse = "Your refund was only recently received. We will begin our review process within 1-2 business days."
        
    
    
    return close(intent_request['sessionAttributes'],
                 'Fulfilled',
                 {'contentType': 'PlainText',
                  'content': 'Thanks, I found a record of your tax refund for ${}. '.format(retrievedRefundAmount)+ statusResponse})


""" --- Intents --- """


def dispatch(intent_request):
    """
    Called when the user specifies an intent for this bot.
    """

    logger.debug('dispatch userId={}, intentName={}'.format(intent_request['userId'], intent_request['currentIntent']['name']))
    logger.debug('alias={}'.format(intent_request['bot']['alias']))


    intent_name = intent_request['currentIntent']['name']

    # Dispatch to your bot's intent handlers
    if intent_name == 'CheckTaxRefundStatus':
        return get_tax_refund_status(intent_request)

    raise Exception('Intent with name ' + intent_name + ' not supported')


""" --- Main handler --- """


def lambda_handler(event, context):
    """
    Route the incoming request based on intent.
    The JSON body of the request is provided in the event slot.
    """
    # By default, treat the user request as coming from the America/Los_Angeles time zone.
    os.environ['TZ'] = 'America/Los_Angeles'
    time.tzset()
    logger.debug('event.bot.name={}'.format(event['bot']['name']))
    print(json.dumps(event));

    return dispatch(event)


""" --- Helper functions --- """

def insert_dash(string, index):
    return string[:index] + '-' + string[index:]

def insert_char(string, index, char):
    return string[:index] + char + string[index:]

def get_num(x):
    return float(''.join(ele for ele in x if ele.isdigit() or ele == '.'))