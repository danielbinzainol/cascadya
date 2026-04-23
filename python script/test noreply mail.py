import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

smtp_server = "smtp-relay.brevo.com"
smtp_port = 587
smtp_user = os.environ.get("BREVO_SMTP_USER", "97aa5d001@smtp-brevo.com")
smtp_password = os.environ["BREVO_SMTP_PASSWORD"]

sender_email = "noreply@cascadya.com"
receiver_email = os.environ.get("TEST_RECEIVER_EMAIL", "danielbinzainol@gmail.com")
subject = "DMARC/DKIM Test from Noreply"
body = (
    "This script requires BREVO_SMTP_PASSWORD from the environment. "
    "Do not commit live SMTP credentials into the repository."
)

msg = MIMEMultipart()
msg["From"] = sender_email
msg["To"] = receiver_email
msg["Subject"] = subject
msg.attach(MIMEText(body, "plain"))

server = None
try:
    print(f"Connecting to the SMTP server as {sender_email}...")
    server = smtplib.SMTP(smtp_server, smtp_port)
    server.starttls()
    server.login(smtp_user, smtp_password)
    server.sendmail(sender_email, receiver_email, msg.as_string())
    print("Success: email sent.")
except smtplib.SMTPResponseException as exc:
    print(f"SMTP error: {exc.smtp_code} - {exc.smtp_error}")
except Exception as exc:
    print(f"Failure: {exc}")
finally:
    if server is not None:
        server.quit()
