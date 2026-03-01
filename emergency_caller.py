import os
import html
from twilio.rest import Client
from dotenv import load_dotenv

# Load credentials from the .env file
load_dotenv()

# Find your Account SID and Auth Token at twilio.com/console
# and set the environment variables. See http://twil.io/secure
account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
twilio_number = os.environ.get('TWILIO_PHONE_NUMBER')
default_emergency_number = os.environ.get('EMERGENCY_CONTACT_NUMBER')

# Initialize the Twilio client
client = None
if account_sid and auth_token:
    client = Client(account_sid, auth_token)

def trigger_emergency_call(to_number=None, threat_overview=""):
    """
    Places an automated phone call to the designated number using Twilio.
    The threat_overview string will be read out loud to the person who answers.
    """
    if not client:
        print("ERROR: Twilio credentials are not set. Cannot place emergency call.")
        return False

    call_to = to_number if to_number else default_emergency_number
    
    if not call_to:
        print("ERROR: No destination phone number provided.")
        return False
        
    print(f"📞 Placing emergency call to {call_to}...")

    # We use TwiML (Twilio Markup Language) to construct the voice response.
    # The <Say> verb converts text to speech when the call is answered.
    # IMPORTANT: <Pause> must be a sibling of <Say>, NOT nested inside it (per Twilio docs).
    safe_overview = html.escape(threat_overview) if threat_overview else "No additional details."
    twiml_instructions = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Pause length="1"/>
    <Say voice="Polly.Matthew" language="en-US">Emergency alert triggered. Please listen carefully to the following situation overview.</Say>
    <Pause length="1"/>
    <Say voice="Polly.Matthew" language="en-US">{safe_overview}</Say>
    <Pause length="2"/>
    <Say voice="Polly.Matthew" language="en-US">Repeating alert.</Say>
    <Pause length="1"/>
    <Say voice="Polly.Matthew" language="en-US">{safe_overview}</Say>
</Response>"""

    try:
        call = client.calls.create(
            twiml=twiml_instructions,
            to=call_to,
            from_=twilio_number
        )
        print(f"✅ Call successfully queued! Call SID: {call.sid}")
        return True
    
    except Exception as e:
        print(f"❌ Failed to place call. Error: {e}")
        return False

# Example usage for testing standalone
if __name__ == "__main__":
    test_overview = "A potential threat was detected by the monitoring system. Visual weapons have been flagged with high confidence."
    
    # Check if env vars are loaded before randomly calling
    if account_sid and auth_token and twilio_number and default_emergency_number:
         print("Credentials found. Attempting to run test call...")
         trigger_emergency_call(threat_overview=test_overview)
    else:
        print("Please configure .env before running this script.")