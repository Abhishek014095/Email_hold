import json
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import imaplib
import email
import smtplib
from email.mime.text import MIMEText

with open("config.json") as f:
    params = json.load(f)["params"]

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
    recipient = db.Column(db.String(120), nullable=True)
    subject = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending')

# Function to fetch emails via IMAP
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

            new_email = Email(sender=sender, recipient=recipient, subject=subject, body=body)
            db.session.add(new_email)
            db.session.commit()
            print(new_email)

        mail.logout()
    except Exception as e:
        print("Email fetching failed:", e)

# Forward email via SMTP
def forward_email(to_email, subject, body):
    try:
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = params['EMAIL_ADDRESS']
        msg['To'] = to_email

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(params['EMAIL_ADDRESS'], params['EMAIL_PASSWORD'])
            server.send_message(msg)
        print("Forwarded to:", to_email)
        return True
    except Exception as e:
        print("Forwarding failed:", e)
        return False

# Routes
@app.before_request
def setup():
    db.create_all()

@app.route('/')
def home():
    fetch_emails()
    emails = Email.query.order_by(Email.id.desc()).all()
    return render_template('pending_emails.html', emails=emails)

@app.route('/approve/<int:email_id>', methods=['POST'])
def approve_email(email_id):
    email_entry = Email.query.get_or_404(email_id)
    if email_entry.status == 'pending':
        if forward_email("abhishekpgi003@poornima.org", email_entry.subject, email_entry.body):
            email_entry.status = 'approved'
        else:
            email_entry.status = 'failed'
        db.session.commit()
    return redirect(url_for('home'))

@app.route('/reject/<int:email_id>', methods=['POST'])
def reject_email(email_id):
    email_entry = Email.query.get_or_404(email_id)
    if email_entry.status == 'pending':
        email_entry.status = 'rejected'
        db.session.commit()
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)
