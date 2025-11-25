
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class GraphConfig:
    tenant_id: str = os.getenv("MS_TENANT_ID", "")
    client_id: str = os.getenv("MS_CLIENT_ID", "")
    client_secret: str = os.getenv("MS_CLIENT_SECRET", "")
    user_id: str = os.getenv("MS_USER_ID", "")  # tek mailbox (senin kullanıcı UPN'in)
    # Buraya TrainMails yazacaksın (Inbox altındaki klasör ismi)
    mail_folder_display_name: str = os.getenv("MS_MAIL_FOLDER", "TrainMails")

    # Eğitim için kaç mail çekelim
    max_training_emails: int = int(os.getenv("TRAIN_MAX_EMAILS", "500"))
