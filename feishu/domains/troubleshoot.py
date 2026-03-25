import os
from typing import Any, Dict, Optional


class TroubleshootMixin:
    def feishu_doctor(self, user_access_token: Optional[str] = None) -> Dict:
        diagnostics: Dict[str, Any] = {
            "env": {
                "app_id": bool(os.environ.get("FEISHU_APP_ID")),
                "app_secret": bool(os.environ.get("FEISHU_APP_SECRET")),
                "domain": os.environ.get("FEISHU_DOMAIN"),
                "user_access_token": bool(os.environ.get("FEISHU_USER_ACCESS_TOKEN") or user_access_token),
            }
        }
        token_check = None
        try:
            token = self.get_tenant_access_token()
            token_check = {"ok": True, "token_present": bool(token)}
        except Exception as e:
            token_check = {"ok": False, "error": str(e)}
        diagnostics["tenant_token"] = token_check
        bot_info = self._request_with_token(method="GET", path="/open-apis/bot/v3/info")
        diagnostics["bot_info"] = bot_info
        return self._wrap_result(code=0, msg="ok", data=diagnostics)
