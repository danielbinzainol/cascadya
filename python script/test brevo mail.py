import os
import smtplib
from email.mime.text import MIMEText

smtp_server = "smtp-relay.brevo.com"
smtp_port = 587
smtp_user = os.environ.get("BREVO_SMTP_USER", "97aa5d001@smtp-brevo.com")
smtp_password = os.environ["BREVO_SMTP_PASSWORD"]

sender_email = "Dev_accounts@cascadya.com"
receiver_email = os.environ.get("TEST_RECEIVER_EMAIL", "danielbinzainol@gmail.com")
subject = "Security Test - SMTP Access"
body = (
    "This script requires BREVO_SMTP_PASSWORD from the environment. "
    "Do not commit live SMTP credentials into the repository."
)

msg = MIMEText(body)
msg["Subject"] = subject
msg["From"] = sender_email
msg["To"] = receiver_email

server = None
try:
    print("Connecting to the SMTP server...")
    server = smtplib.SMTP(smtp_server, smtp_port)
    server.starttls()

    print("Authenticating...")
    server.login(smtp_user, smtp_password)

    print("Sending the test email...")
    server.sendmail(sender_email, receiver_email, msg.as_string())
    print("Success: email sent.")
except Exception as exc:
    print(f"Failure: {exc}")
finally:
    if server is not None:
        server.quit()
