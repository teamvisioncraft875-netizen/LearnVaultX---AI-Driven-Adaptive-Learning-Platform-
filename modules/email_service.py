import random
import string
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class EmailService:
    def generate_otp(self, length=6):
        return ''.join(random.choices(string.digits, k=length))

    def get_otp_expiry(self, minutes=10):
        return datetime.now() + timedelta(minutes=minutes)

    def send_otp_email(self, email, otp):
        # In a real production app, this would use SMTP or an API like SendGrid
        # For this restoration/demo, we log it to the console
        logger.info(f"==========================================")
        logger.info(f"EMAIL SIMULATION: To {email}")
        logger.info(f"Subject: Password Reset OTP")
        logger.info(f"Your OTP is: {otp}")
        logger.info(f"==========================================")
        return True

# Singleton instance
email_service = EmailService()

def generate_otp():
    return email_service.generate_otp()

def get_otp_expiry():
    return email_service.get_otp_expiry()

def send_otp_email(email, otp):
    return email_service.send_otp_email(email, otp)
