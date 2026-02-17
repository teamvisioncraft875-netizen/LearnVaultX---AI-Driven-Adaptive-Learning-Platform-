import secrets
import logging
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

logger = logging.getLogger(__name__)

# Purpose-specific email config
_EMAIL_CONFIG = {
    'signup': {
        'subject': 'LearnVaultX — Verify Your Email',
        'heading': 'Email Verification',
        'body': 'Use the code below to verify your email and complete your LearnVaultX registration.',
        'fallback': 'Your OTP for LearnVaultX signup verification is:\n\n    {otp}\n\nThis code is valid for 5 minutes. Do not share it with anyone.\n\n— LearnVaultX Team',
    },
    'login': {
        'subject': 'LearnVaultX — Login Verification',
        'heading': 'Login Verification',
        'body': 'Use the code below to complete your LearnVaultX login.',
        'fallback': 'Your OTP for LearnVaultX login is:\n\n    {otp}\n\nThis code is valid for 5 minutes. Do not share it with anyone.\n\n— LearnVaultX Team',
    },
    'password_reset': {
        'subject': 'LearnVaultX — Password Reset',
        'heading': 'Password Reset',
        'body': 'Use the code below to reset your LearnVaultX password.',
        'fallback': 'Your OTP for resetting your LearnVaultX password is:\n\n    {otp}\n\nThis code is valid for 5 minutes. Do not share it with anyone.\n\n— LearnVaultX Team',
    },
}


class EmailService:
    def __init__(self):
        self.smtp_email = os.environ.get('SMTP_EMAIL', '')
        self.smtp_password = os.environ.get('SMTP_PASSWORD', '')
        self.smtp_host = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
        self.smtp_port = int(os.environ.get('SMTP_PORT', '587'))

    def generate_otp(self, length=6):
        """Generate a cryptographically secure numeric OTP."""
        upper = 10 ** length
        lower = 10 ** (length - 1)
        return str(secrets.randbelow(upper - lower) + lower)

    def hash_otp(self, otp):
        """Hash OTP for secure storage."""
        return generate_password_hash(str(otp))

    def verify_otp(self, stored_hash, otp):
        """Verify OTP against stored hash."""
        return check_password_hash(stored_hash, str(otp))

    def get_otp_expiry(self, minutes=5):
        """Return expiry timestamp (5 minutes from now)."""
        return (datetime.now() + timedelta(minutes=minutes)).isoformat()

    def send_otp_email(self, email, otp, purpose='password_reset'):
        """Send OTP email. Uses SMTP if configured, otherwise console fallback.
        
        Args:
            email: recipient email address
            otp: the plaintext OTP to send
            purpose: 'signup', 'login', or 'password_reset'
            
        Returns:
            bool: True if sent (or simulated), False if failed.
        """
        cfg = _EMAIL_CONFIG.get(purpose, _EMAIL_CONFIG['password_reset'])
        subject = cfg['subject']
        body_text = cfg['fallback'].format(otp=otp)

        # Check if SMTP is configured
        smtp_configured = bool(self.smtp_email and self.smtp_password)
        
        if smtp_configured:
            try:
                msg = MIMEMultipart('alternative')
                msg['Subject'] = subject
                msg['From'] = f"LearnVaultX Support <{self.smtp_email}>"
                msg['To'] = email

                msg.attach(MIMEText(body_text, 'plain'))

                html_body = f"""
                <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 480px; margin: 0 auto;
                            background: linear-gradient(160deg, #050816, #0d1035); color: #eaf0ff;
                            border-radius: 16px; padding: 40px; border: 1px solid rgba(255,255,255,0.08);">
                    <h2 style="margin: 0 0 8px; color: #ffffff;">{cfg['heading']}</h2>
                    <p style="color: rgba(234,240,255,0.7); margin: 0 0 28px; font-size: 14px;">
                        {cfg['body']}
                    </p>
                    <div style="background: rgba(124,58,237,0.15); border: 1px solid rgba(124,58,237,0.3);
                                border-radius: 12px; padding: 20px; text-align: center; margin: 0 0 24px;">
                        <span style="font-size: 36px; font-weight: 700; letter-spacing: 8px; color: #a78bfa;">
                            {otp}
                        </span>
                    </div>
                    <p style="color: rgba(234,240,255,0.5); font-size: 13px; margin: 0 0 4px;">
                        This code expires in <strong>5 minutes</strong>.
                    </p>
                    <p style="color: rgba(234,240,255,0.4); font-size: 12px; margin: 20px 0 0;">
                        If you didn't request this, you can safely ignore this email.
                    </p>
                </div>
                """
                msg.attach(MIMEText(html_body, 'html'))

                # Connect to server
                logger.info(f"[EMAIL] Connecting to {self.smtp_host}:{self.smtp_port}...")
                with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                    server.ehlo()
                    server.starttls()
                    server.ehlo()
                    server.login(self.smtp_email, self.smtp_password)
                    server.sendmail(self.smtp_email, email, msg.as_string())
                
                logger.info(f"[EMAIL] {purpose} OTP sent to {email} via SMTP")
                return True
                
            except Exception as e:
                logger.error(f"[EMAIL] SMTP Delivery Failed: {e}")
                import traceback
                traceback.print_exc() 
                
                # Production safety: if not in dev mode, fail hard
                is_dev = os.environ.get('FLASK_ENV') == 'development' or os.environ.get('FLASK_DEBUG') == '1' or app.debug
                
                if not is_dev:
                    return False
                
                logger.warning("[EMAIL] SMTP failed. Falling back to console simulation (Dev Mode only)")

        # Console fallback (Development Mode Only)
        logger.info("=" * 50)
        logger.info(f"  EMAIL SIMULATION ({purpose.upper()} OTP)")
        logger.info(f"  To:      {email}")
        logger.info(f"  Subject: {subject}")
        logger.info(f"  OTP:     {otp}")
        logger.info(f"  Expires: 5 minutes")
        logger.info("=" * 50)
        return True


# Singleton instance
email_service = EmailService()

# Module-level convenience functions
def generate_otp():
    return email_service.generate_otp()

def hash_otp(otp):
    return email_service.hash_otp(otp)

def verify_otp(stored_hash, otp):
    return email_service.verify_otp(stored_hash, otp)

def get_otp_expiry():
    return email_service.get_otp_expiry()

def send_otp_email(email, otp, purpose='password_reset'):
    return email_service.send_otp_email(email, otp, purpose)
