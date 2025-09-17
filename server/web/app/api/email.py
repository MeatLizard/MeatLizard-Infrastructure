"""
Email service API endpoints.
"""
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional
from datetime import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from server.web.app.dependencies import get_db
from server.web.app.models import User
from server.web.app.config import get_settings
from server.web.app.api.auth import get_current_user

router = APIRouter(prefix="/api/email", tags=["email"])
settings = get_settings()

class EmailRequest(BaseModel):
    to: List[EmailStr]
    subject: str
    body: str
    html_body: Optional[str] = None
    cc: Optional[List[EmailStr]] = None
    bcc: Optional[List[EmailStr]] = None

class EmailTemplate(BaseModel):
    name: str
    subject: str
    body: str
    html_body: Optional[str] = None

class EmailResponse(BaseModel):
    message_id: str
    status: str
    sent_at: datetime

class EmailService:
    def __init__(self):
        self.smtp_server = settings.SMTP_SERVER
        self.smtp_port = settings.SMTP_PORT
        self.smtp_username = settings.SMTP_USERNAME
        self.smtp_password = settings.SMTP_PASSWORD
        self.from_email = settings.FROM_EMAIL
        
    async def send_email(
        self,
        to: List[str],
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None
    ) -> str:
        """Send an email using SMTP."""
        message_id = str(uuid.uuid4())
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.from_email
            msg['To'] = ', '.join(to)
            msg['Message-ID'] = f"<{message_id}@{settings.DOMAIN}>"
            
            if cc:
                msg['Cc'] = ', '.join(cc)
            
            # Add text part
            text_part = MIMEText(body, 'plain')
            msg.attach(text_part)
            
            # Add HTML part if provided
            if html_body:
                html_part = MIMEText(html_body, 'html')
                msg.attach(html_part)
            
            # Create secure connection and send
            context = ssl.create_default_context()
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls(context=context)
                server.login(self.smtp_username, self.smtp_password)
                
                recipients = to + (cc or []) + (bcc or [])
                server.send_message(msg, to_addrs=recipients)
            
            return message_id
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")

email_service = EmailService()

@router.post("/send", response_model=EmailResponse)
async def send_email(
    email_request: EmailRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """Send an email."""
    # Add to background task to avoid blocking
    message_id = await email_service.send_email(
        to=email_request.to,
        subject=email_request.subject,
        body=email_request.body,
        html_body=email_request.html_body,
        cc=email_request.cc,
        bcc=email_request.bcc
    )
    
    return EmailResponse(
        message_id=message_id,
        status="sent",
        sent_at=datetime.utcnow()
    )

@router.post("/send-template")
async def send_template_email(
    template_name: str,
    to: List[EmailStr],
    variables: dict = {},
    current_user: User = Depends(get_current_user)
):
    """Send an email using a predefined template."""
    templates = {
        "welcome": {
            "subject": "Welcome to MeatLizard AI Platform!",
            "body": """
Hello {username},

Welcome to MeatLizard AI Platform! Your account has been successfully created.

You can now access all our features:
- AI Chat with local inference
- URL Shortener with analytics
- Pastebin with syntax highlighting
- Video platform with transcoding
- Media import from various sources

Get started at: {platform_url}

Best regards,
The MeatLizard Team
            """,
            "html_body": """
<html>
<body>
    <h2>Welcome to MeatLizard AI Platform!</h2>
    <p>Hello {username},</p>
    <p>Welcome to MeatLizard AI Platform! Your account has been successfully created.</p>
    
    <h3>Available Features:</h3>
    <ul>
        <li>🤖 AI Chat with local inference</li>
        <li>🔗 URL Shortener with analytics</li>
        <li>📝 Pastebin with syntax highlighting</li>
        <li>🎥 Video platform with transcoding</li>
        <li>📥 Media import from various sources</li>
    </ul>
    
    <p><a href="{platform_url}" style="background-color: #10B981; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Get Started</a></p>
    
    <p>Best regards,<br>The MeatLizard Team</p>
</body>
</html>
            """
        },
        "password_reset": {
            "subject": "Password Reset - MeatLizard AI Platform",
            "body": """
Hello {username},

You requested a password reset for your MeatLizard AI Platform account.

Click the link below to reset your password:
{reset_url}

This link will expire in 24 hours.

If you didn't request this reset, please ignore this email.

Best regards,
The MeatLizard Team
            """,
            "html_body": """
<html>
<body>
    <h2>Password Reset</h2>
    <p>Hello {username},</p>
    <p>You requested a password reset for your MeatLizard AI Platform account.</p>
    
    <p><a href="{reset_url}" style="background-color: #EF4444; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Reset Password</a></p>
    
    <p><strong>This link will expire in 24 hours.</strong></p>
    
    <p>If you didn't request this reset, please ignore this email.</p>
    
    <p>Best regards,<br>The MeatLizard Team</p>
</body>
</html>
            """
        }
    }
    
    if template_name not in templates:
        raise HTTPException(status_code=404, detail="Template not found")
    
    template = templates[template_name]
    
    # Replace variables in template
    subject = template["subject"].format(**variables)
    body = template["body"].format(**variables)
    html_body = template["html_body"].format(**variables) if template.get("html_body") else None
    
    message_id = await email_service.send_email(
        to=to,
        subject=subject,
        body=body,
        html_body=html_body
    )
    
    return EmailResponse(
        message_id=message_id,
        status="sent",
        sent_at=datetime.utcnow()
    )

@router.get("/templates")
async def list_email_templates(current_user: User = Depends(get_current_user)):
    """List available email templates."""
    return {
        "templates": [
            {"name": "welcome", "description": "Welcome email for new users"},
            {"name": "password_reset", "description": "Password reset email"}
        ]
    }

@router.post("/test")
async def test_email_configuration(current_user: User = Depends(get_current_user)):
    """Test email configuration by sending a test email."""
    try:
        message_id = await email_service.send_email(
            to=[current_user.email or settings.ADMIN_EMAIL],
            subject="MeatLizard Email Test",
            body="This is a test email to verify your email configuration is working correctly.",
            html_body="<p>This is a test email to verify your email configuration is working correctly.</p>"
        )
        
        return {
            "status": "success",
            "message": "Test email sent successfully",
            "message_id": message_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Email test failed: {str(e)}")