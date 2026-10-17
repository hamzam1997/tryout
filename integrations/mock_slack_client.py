class MockSlackClient:
    def __init__(self, token=None, base_url=None):
        self.token = token or "mock-slack-token"
        self.base_url = base_url or "https://mock.slack.com/api"
        self.calls = []
        
    def notify_attempt_completed(self, attempt_id: int, report_link: str) -> dict:
        self.calls.append({
            "attempt_id": attempt_id,
            "report_link": report_link
        })
        return {
            "ok": True,
            "ts": "1234567890.123456",
            "message": {
                "text": f"Attempt {attempt_id} completed. Report: {report_link}"
            }
        }
