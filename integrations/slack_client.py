import os
import requests

class SlackClient:
    def __init__(self, token=None, base_url=None):
        self.token = token or os.environ.get("SLACK_APP_TOKEN")
        self.base_url = base_url or os.environ.get("NOTIFICATIONS_SERVICE_URL", "https://slack.com/api")
        
    def notify_attempt_completed(self, attempt_id: int, report_link: str) -> dict:
        url = f"{self.base_url}/chat.postMessage"
        payload = {
            "channel": "#engineering-updates",
            "text": f"Attempt {attempt_id} completed. Report: {report_link}"
        }
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
            
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
