import os
import base64
from email.message import EmailMessage
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from tools.permission_gate import describe_permission_error, guard

SCOPES = ["https://mail.google.com/"]

def _authenticate():
    """Internal function to authenticate the user and set up the Gmail service."""
    credentials_path = "credentials.json"
    token_path = "token.json"
    creds = None
    
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_path, SCOPES
            )
            creds = flow.run_local_server(port=0)
            
        with open(token_path, "w") as token:
            token.write(creds.to_json())
            
    try:
        service = build("gmail", "v1", credentials=creds)
        return service
    except HttpError as error:
        print(f"An error occurred: {error}")
        return None

def check_unread_emails(max_results: int = 5) -> str:
    """
    Fetches the latest unread emails from the user's Gmail inbox.
    
    Args:
        max_results: The maximum number of emails to fetch (default 5).
        
    Returns:
        A string summarizing the unread emails, or an error message.
    """
    service = _authenticate()
    if not service:
        return "Gmail service not initialized. Authentication failed."
        
    try:
        results = service.users().messages().list(userId="me", labelIds=["INBOX", "UNREAD"], maxResults=max_results).execute()
        messages = results.get("messages", [])

        if not messages:
            return "No new messages."

        email_summaries = []
        for message in messages:
            msg = service.users().messages().get(userId="me", id=message["id"]).execute()
            payload = msg.get('payload', {})
            headers = payload.get('headers', [])
            
            subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), 'No Subject')
            sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), 'Unknown Sender')
            snippet = msg.get('snippet', '')
            
            email_summaries.append(f"From: {sender}\nSubject: {subject}\nSnippet: {snippet}\nID: {message['id']}\n---")
            
        return "\n".join(email_summaries)

    except HttpError as error:
        return f"An error occurred: {error}"

def send_email(to_email: str, subject: str, content: str) -> str:
    """
    Sends an email using the user's Gmail account.
    
    Args:
        to_email: The recipient's email address.
        subject: The subject of the email.
        content: The body text of the email.
        
    Returns:
        A status message indicating success or failure.
    """
    try:
        guard(
            "email_send",
            "send_email",
            payload={"to_email": to_email, "subject": subject, "content": content},
        )
        service = _authenticate()
        if not service:
            return "Gmail service not initialized. Authentication failed."

        message = EmailMessage()
        message.set_content(content)
        message["To"] = to_email
        message["From"] = "me"
        message["Subject"] = subject

        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

        create_message = {"raw": encoded_message}
        send_message = (
            service.users()
            .messages()
            .send(userId="me", body=create_message)
            .execute()
        )
        return f"Message sent successfully! Message Id: {send_message['id']}"

    except HttpError as error:
        return f"An error occurred: {error}"
    except Exception as error:
        return describe_permission_error(error)

def delete_email(message_id: str) -> str:
    """
    Moves an email to the trash.
    
    Args:
        message_id: The ID of the email message to delete (returned by check_unread_emails).
        
    Returns:
        A status message indicating success or failure.
    """
    try:
        guard("email_delete", "delete_email", payload={"message_id": message_id})
        service = _authenticate()
        if not service:
            return "Gmail service not initialized. Authentication failed."

        service.users().messages().trash(userId="me", id=message_id).execute()
        return f"Email {message_id} successfully moved to trash."
    except HttpError as error:
        return f"An error occurred: {error}"
    except Exception as error:
        return describe_permission_error(error)
