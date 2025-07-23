import json

from flask import Flask, render_template,jsonify,json
from flask_sqlalchemy import SQLAlchemy
import imaplib
import email
import os

with open("config.json") as f:
    params=json.load(f)["params"]

print(params["EMAIL_ADDRESS"])

app = Flask(__name__)

# Database config
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:@localhost/hold'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Email model
class Email(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender = db.Column(db.String(120), nullable=False)
    recipient = db.Column(db.String(120), nullable=True)  # Optional if not present
    subject = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending')


# Fetch emails using IMAP
def fetch_emails():
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(params['EMAIL_ADDRESS'], params['EMAIL_PASSWORD'])
        mail.select("inbox")

        _, data = mail.search(None, "UNSEEN")

        for num in data[0].split():
            _, msg_data = mail.fetch(num, "(RFC822)")
            raw_msg = email.message_from_bytes(msg_data[0][1])

            sender = raw_msg["From"]
            recipient = raw_msg["To"]
            subject = raw_msg["Subject"] or "(No Subject)"
            body = ""

            if raw_msg.is_multipart():
                for part in raw_msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode(errors='ignore')
                        break
            else:
                body = raw_msg.get_payload(decode=True).decode(errors='ignore')

            # Save to database
            new_email = Email(sender=sender, recipient=recipient, subject=subject, body=body, status='pending')
            db.session.add(new_email)
            db.session.commit()
            print(new_email)

        mail.logout()
    except Exception as e:
        print("Email fetching failed:", e)


# Database setup before first request
@app.before_request
def setup():
    db.create_all()

# Homepage route
@app.route('/')
def home():
    fetch_emails()  # Fetch new emails
    emails = Email.query.order_by(Email.id.desc()).all()
    return render_template('pending_emails.html', emails=emails)

# Run the app
if __name__ == '__main__':
    app.run(debug=True)
