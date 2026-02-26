import smtplib
from email.message import EmailMessage

# 1. Setup your credentials and server details
EMAIL_ADDRESS = "guus.van.marle@smarterliving.nl"
EMAIL_PASSWORD = "nrbt nbaw qvrl ehnt"  # Do not use your regular password!

# 2. Create the email container
msg = EmailMessage()
msg['Subject'] = "Cycletester status:"
msg['From'] = EMAIL_ADDRESS
msg['To'] = "engineering@smarterliving.nl"

counter = 1234

msg_stalled = """\
<!DOCTYPE html>
<html>
    <body>
        <h1 style="color: Red;">CYCLETESTER STALLED!</h1>
        <h2>Please check machine and restart.</h2>
        <h3>Current cycle count: <b>""" + str(counter) + """</b></h3>
        <p>Visit me at <a href>10.181.106.124</a></p>
    </body>
</html>
"""

msg_paused = """\
<!DOCTYPE html>
<html>
    <body>
        <h1 style="color: Orange;">CYCLETESTER PAUSED!</h1>
        <h2>Please replace pins and continue test.</h2>
        <h3>Current cycle count: <b>""" + str(counter) + """</b></h3>
        <p>Visit me at <a href>10.181.106.124</a></p>
    </body>
</html>
"""

msg_finished = """\
<!DOCTYPE html>
<html>
    <body>
        <h1 style="color: Limegreen;">CYCLETESTER FINISHED!</h1>
        <h2>Test completed.</h2>
        <h3>Current cycle count: <b>""" + str(counter) + """</b></h3>
        <p>Visit me at <a href>10.181.106.124</a></p>
    </body>
</html>
"""

# (Optional) Add an HTML version
messages = [msg_stalled, msg_paused, msg_finished]

# 3. Send the email
for i in range(3):
    msg.set_content(messages[i], subtype='html')
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)
        print("Email sent successfully!")
    except Exception as e:
        print(f"Error: {e}")
