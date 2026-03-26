"""
Feishu/Lark OpenAPI Python Client
**完全基于官方 larksuite-oapi SDK 实现**
兼容所有原有接口，自动管理token，更稳定可靠
"""
import os
import json
import time
import base64
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Optional, Dict, Any, Union, Callable, List, Tuple
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

try:
    import lark_oapi as lark
    from lark_oapi.api.auth.v3 import InternalTenantAccessTokenRequestBody
    from lark_oapi.api.auth.v3.tenant_access_token.internal import InternalTenantAccessTokenRequest
except ModuleNotFoundError:
    lark = None
    InternalTenantAccessTokenRequest = None
    InternalTenantAccessTokenRequestBody = None

LARK_ERROR = {
    "APP_SCOPE_MISSING": 99991672,
    "USER_SCOPE_INSUFFICIENT": 99991679,
    "TOKEN_INVALID": 99991668,
    "TOKEN_EXPIRED": 99991677,
    "REFRESH_SERVER_ERROR": 20050,
    "REFRESH_TOKEN_EXPIRED": 20037,
}

TOKEN_RETRY_CODES = {LARK_ERROR["TOKEN_INVALID"], LARK_ERROR["TOKEN_EXPIRED"]}
REFRESH_TOKEN_RETRYABLE = {LARK_ERROR["REFRESH_SERVER_ERROR"]}

mixin_classes = []

try:
    from .domains import ImMixin
    if ImMixin is not None:
        mixin_classes.append(ImMixin)
except ImportError:
    pass

try:
    from .domains import DocxMixin
    if DocxMixin is not None:
        mixin_classes.append(DocxMixin)
except ImportError:
    pass

try:
    from .domains import BitableMixin
    if BitableMixin is not None:
        mixin_classes.append(BitableMixin)
except ImportError:
    pass

try:
    from .domains import CalendarMixin
    if CalendarMixin is not None:
        mixin_classes.append(CalendarMixin)
except ImportError:
    pass

try:
    from .domains import DriveMixin
    if DriveMixin is not None:
        mixin_classes.append(DriveMixin)
except ImportError:
    pass

try:
    from .domains import TaskMixin
    if TaskMixin is not None:
        mixin_classes.append(TaskMixin)
except ImportError:
    pass

try:
    from .domains import WikiMixin
    if WikiMixin is not None:
        mixin_classes.append(WikiMixin)
except ImportError:
    pass

try:
    from .domains import TroubleshootMixin
    if TroubleshootMixin is not None:
        mixin_classes.append(TroubleshootMixin)
except ImportError:
    pass


class _FeishuCore:
    def __init__(self, app_id: Optional[str] = None, app_secret: Optional[str] = None, domain: Optional[str] = None):
        """
        初始化飞书客户端
        
        Args:
            app_id: 飞书应用ID，不填则从环境变量FEISHU_APP_ID读取
            app_secret: 飞书应用密钥，不填则从环境变量FEISHU_APP_SECRET读取
            domain: API域名，默认公网，字节内部可设置为https://fsopen.bytedance.net
        """
        self.app_id = app_id or os.environ.get("FEISHU_APP_ID")
        self.app_secret = app_secret or os.environ.get("FEISHU_APP_SECRET")
        self.domain = domain or os.environ.get("FEISHU_DOMAIN", "https://open.feishu.cn")
        
        # 如果环境变量没有，尝试从nanobot的config.json读取
        if not self.app_id or not self.app_secret:
            config_path = os.environ.get("FEISHU_CONFIG_PATH") or os.path.expanduser("~/.nanobot/config.json")
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    if 'channels' in config and 'feishu' in config['channels']:
                        feishu_config = config['channels']['feishu']
                        if not self.app_id and 'appId' in feishu_config:
                            self.app_id = feishu_config['appId']
                        if not self.app_secret and 'appSecret' in feishu_config:
                            self.app_secret = feishu_config['appSecret']
        
        if not self.app_id or not self.app_secret:
            raise ValueError("请设置FEISHU_APP_ID和FEISHU_APP_SECRET，或在config.json的channels.feishu配置")

        if lark is None:
            raise ModuleNotFoundError("缺少依赖 lark-oapi，请先安装：pip install lark-oapi")

        # 初始化官方SDK客户端，自动管理token、重试、限流
        self.client = lark.Client.builder() \
            .app_id(self.app_id) \
            .app_secret(self.app_secret) \
            .domain(self.domain) \
            .log_level(lark.LogLevel.ERROR) \
            .build()
        self._user_access_token_provider: Optional[Callable[[], str]] = None
        self._user_access_token_refresher: Optional[Callable[[], Optional[str]]] = None
        self._user_access_token_cache: Optional[str] = None
        self._user_access_token_lock = Lock()
        self._uat_store: Dict[str, Dict[str, Any]] = {}
        self._uat_store_lock = Lock()
        self._uat_refresh_locks: Dict[str, Lock] = {}

    def set_user_access_token_provider(self, provider: Optional[Callable[[], str]]) -> "FeishuClient":
        self._user_access_token_provider = provider
        return self

    def set_user_access_token_refresher(self, refresher: Optional[Callable[[], Optional[str]]]) -> "FeishuClient":
        self._user_access_token_refresher = refresher
        return self

    def _get_user_access_token(self, user_access_token: Optional[str] = None) -> str:
        if user_access_token:
            self._user_access_token_cache = user_access_token
            return user_access_token
        if self._user_access_token_provider is not None:
            token = self._user_access_token_provider()
            if token:
                self._user_access_token_cache = token
                return token
        if self._user_access_token_cache:
            return self._user_access_token_cache
        token = os.environ.get("FEISHU_USER_ACCESS_TOKEN")
        if token:
            self._user_access_token_cache = token
            return token
        raise ValueError("缺少 user_access_token：请传参或通过 set_user_access_token_provider 提供，或设置环境变量 FEISHU_USER_ACCESS_TOKEN")

    def _refresh_user_access_token(self) -> Optional[str]:
        if self._user_access_token_refresher is None:
            return None
        with self._user_access_token_lock:
            token = self._user_access_token_refresher()
        if token:
            self._user_access_token_cache = token
        return token

    def _coerce_datetime_to_ms(self, value: Optional[Union[str, int, float]]) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            number = int(value)
            if number < 10**11:
                return str(number * 1000)
            return str(number)
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.isdigit():
                number = int(stripped)
                if number < 10**11:
                    return str(number * 1000)
                return str(number)
            normalized = stripped.replace("Z", "+00:00")
            dt = datetime.fromisoformat(normalized)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone(timedelta(hours=8)))
            return str(int(dt.timestamp() * 1000))
        return None

    def _normalize_message_content(self, msg_type: str, content: Union[str, Dict]) -> str:
        if msg_type == "text" and isinstance(content, str):
            return json.dumps({"text": content}, ensure_ascii=False)
        if isinstance(content, str):
            return content
        return json.dumps(content, ensure_ascii=False)

    def _request_with_token(
        self,
        *,
        method: str,
        path: str,
        token_type: str = "tenant",
        user_access_token: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        body: Optional[Any] = None,
    ) -> Dict:
        try:
            uri = path
            if uri.startswith("http://") or uri.startswith("https://"):
                if uri.startswith(self.domain):
                    uri = uri[len(self.domain):]
                else:
                    idx = uri.find("/open-apis/")
                    uri = uri[idx:] if idx >= 0 else uri
            if not uri.startswith("/"):
                uri = "/" + uri

            http_method = method.upper()
            http_method_enum = {
                "GET": lark.HttpMethod.GET,
                "POST": lark.HttpMethod.POST,
                "PUT": lark.HttpMethod.PUT,
                "DELETE": lark.HttpMethod.DELETE,
                "PATCH": lark.HttpMethod.PATCH,
            }.get(http_method)
            if http_method_enum is None:
                return self._wrap_result(code=-1, msg=f"不支持的HTTP方法: {method}", data=None)

            final_headers: Dict[str, str] = {}
            if headers:
                final_headers.update({str(k): str(v) for k, v in headers.items()})

            token_types = {lark.AccessTokenType.TENANT}
            if token_type == "user":
                token_types = {lark.AccessTokenType.USER}
                token = self._get_user_access_token(user_access_token)
                if token:
                    final_headers["Authorization"] = f"Bearer {token}"

            queries: List[Tuple[str, str]] = []
            if params:
                queries = [(str(k), str(v)) for k, v in params.items() if v is not None]

            def send_request(headers_payload: Dict[str, str]) -> Dict:
                req_builder = lark.BaseRequest.builder() \
                    .http_method(http_method_enum) \
                    .uri(uri) \
                    .token_types(token_types)
                if queries:
                    req_builder = req_builder.queries(queries)
                if headers_payload:
                    req_builder = req_builder.headers(headers_payload)
                if body is not None:
                    req_builder = req_builder.body(body)
                req = req_builder.build()
                resp = self.client.request(req)
                return self._parse_lark_response(resp)

            result = send_request(final_headers)
            if token_type == "user" and result.get("code") in TOKEN_RETRY_CODES:
                refreshed = self._refresh_user_access_token()
                if refreshed:
                    retry_headers = dict(final_headers)
                    retry_headers["Authorization"] = f"Bearer {refreshed}"
                    result = send_request(retry_headers)
            return self._map_auth_result(result, path)
        except Exception as e:
            return self._wrap_exception(e, "请求")

    def _request_raw_with_token(
        self,
        *,
        method: str,
        path: str,
        token_type: str = "tenant",
        user_access_token: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        body: Optional[Any] = None,
    ) -> Dict:
        try:
            uri = path
            if uri.startswith("http://") or uri.startswith("https://"):
                if uri.startswith(self.domain):
                    uri = uri[len(self.domain):]
                else:
                    idx = uri.find("/open-apis/")
                    uri = uri[idx:] if idx >= 0 else uri
            if not uri.startswith("/"):
                uri = "/" + uri

            http_method = method.upper()
            http_method_enum = {
                "GET": lark.HttpMethod.GET,
                "POST": lark.HttpMethod.POST,
                "PUT": lark.HttpMethod.PUT,
                "DELETE": lark.HttpMethod.DELETE,
                "PATCH": lark.HttpMethod.PATCH,
            }.get(http_method)
            if http_method_enum is None:
                return self._wrap_result(code=-1, msg=f"不支持的HTTP方法: {method}", data=None)

            final_headers: Dict[str, str] = {}
            if headers:
                final_headers.update({str(k): str(v) for k, v in headers.items()})

            token_types = {lark.AccessTokenType.TENANT}
            if token_type == "user":
                token_types = {lark.AccessTokenType.USER}
                token = self._get_user_access_token(user_access_token)
                if token:
                    final_headers["Authorization"] = f"Bearer {token}"

            queries: List[Tuple[str, str]] = []
            if params:
                queries = [(str(k), str(v)) for k, v in params.items() if v is not None]

            def send_request(headers_payload: Dict[str, str]) -> Dict:
                req_builder = lark.BaseRequest.builder() \
                    .http_method(http_method_enum) \
                    .uri(uri) \
                    .token_types(token_types)
                if queries:
                    req_builder = req_builder.queries(queries)
                if headers_payload:
                    req_builder = req_builder.headers(headers_payload)
                if body is not None:
                    req_builder = req_builder.body(body)
                req = req_builder.build()

                resp = self.client.request(req)
                raw = getattr(getattr(resp, "raw", None), "content", None)
                content = raw if isinstance(raw, (bytes, bytearray)) else b""
                log_id = None
                get_log_id = getattr(resp, "get_log_id", None)
                if callable(get_log_id):
                    log_id = get_log_id()
                success = resp.success()
                code = 0 if success else int(getattr(resp, "code", -1) or -1)
                return self._wrap_result(code=code, msg=resp.msg, data={"content": content, "log_id": log_id})

            result = send_request(final_headers)
            if token_type == "user" and result.get("code") in TOKEN_RETRY_CODES:
                refreshed = self._refresh_user_access_token()
                if refreshed:
                    retry_headers = dict(final_headers)
                    retry_headers["Authorization"] = f"Bearer {refreshed}"
                    result = send_request(retry_headers)
            return self._map_auth_result(result, path)
        except Exception as e:
            return self._wrap_exception(e, "请求")

    def _safe_json_loads(self, raw: Any) -> Optional[Any]:
        if raw is None:
            return None
        try:
            if isinstance(raw, (bytes, bytearray)):
                return json.loads(raw.decode("utf-8"))
            if isinstance(raw, str):
                return json.loads(raw)
            return json.loads(raw)
        except Exception:
            return None

    def _wrap_result(
        self,
        *,
        code: int,
        msg: str,
        data: Any = None,
        log_id: Optional[str] = None,
        text: Optional[str] = None,
    ) -> Dict:
        result: Dict[str, Any] = {"code": code, "msg": msg, "data": data}
        if log_id:
            result["log_id"] = log_id
        if text:
            result["text"] = text
        return result

    def _map_auth_result(self, result: Dict, api_name: str) -> Dict:
        code = result.get("code")
        if code == LARK_ERROR["APP_SCOPE_MISSING"]:
            return self._wrap_result(
                code=code,
                msg="应用权限不足，请管理员在开放平台开通权限",
                data={"api": api_name, "auth_required": "app", "raw": result.get("data")},
                log_id=result.get("log_id"),
                text=result.get("text"),
            )
        if code == LARK_ERROR["USER_SCOPE_INSUFFICIENT"]:
            return self._wrap_result(
                code=code,
                msg="用户权限不足，需要授权",
                data={"api": api_name, "auth_required": "user", "raw": result.get("data")},
                log_id=result.get("log_id"),
                text=result.get("text"),
            )
        return result

    def _resolve_oauth_endpoints(self, brand: Optional[str] = None) -> Dict[str, str]:
        brand_value = (brand or "").strip().lower()
        if not brand_value:
            domain = (self.domain or "").lower()
            brand_value = "lark" if "larksuite.com" in domain else "feishu"
        if brand_value == "lark":
            return {
                "device_authorization": "https://accounts.larksuite.com/oauth/v1/device_authorization",
                "token": "https://open.larksuite.com/open-apis/authen/v2/oauth/token",
            }
        return {
            "device_authorization": "https://accounts.feishu.cn/oauth/v1/device_authorization",
            "token": "https://open.feishu.cn/open-apis/authen/v2/oauth/token",
        }

    def _http_post_form(self, url: str, data: Dict[str, str], headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        payload = urlencode(data).encode("utf-8")
        req_headers = {"Content-Type": "application/x-www-form-urlencoded"}
        if headers:
            req_headers.update(headers)
        req = Request(url, data=payload, headers=req_headers, method="POST")
        try:
            with urlopen(req, timeout=30) as resp:
                raw = resp.read()
            return json.loads(raw.decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, ValueError) as e:
            raise RuntimeError(f"oauth http failed: {e}")

    def _scope_covers(self, granted_scope: str, required_scopes: List[str]) -> bool:
        granted = set([s for s in (granted_scope or "").split() if s])
        required = set([s for s in required_scopes if s])
        return required.issubset(granted)

    def set_user_token(self, user_open_id: str, *, access_token: str, refresh_token: str = "", scope: str = "", expires_in: int = 7200, refresh_expires_in: int = 604800) -> None:
        now = int(time.time() * 1000)
        record = {
            "user_open_id": user_open_id,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "scope": scope,
            "expires_at": now + int(expires_in) * 1000,
            "refresh_expires_at": now + int(refresh_expires_in) * 1000,
            "granted_at": now,
        }
        with self._uat_store_lock:
            self._uat_store[user_open_id] = record
            if user_open_id not in self._uat_refresh_locks:
                self._uat_refresh_locks[user_open_id] = Lock()

    def _get_user_token_record(self, user_open_id: str) -> Optional[Dict[str, Any]]:
        with self._uat_store_lock:
            record = self._uat_store.get(user_open_id)
            return dict(record) if isinstance(record, dict) else None

    def _refresh_user_token_for_user(self, user_open_id: str, brand: Optional[str] = None) -> Optional[str]:
        record = self._get_user_token_record(user_open_id)
        if not record:
            return None
        now_ms = int(time.time() * 1000)
        refresh_expires_at = int(record.get("refresh_expires_at") or 0)
        if refresh_expires_at and now_ms >= refresh_expires_at:
            with self._uat_store_lock:
                self._uat_store.pop(user_open_id, None)
            return None

        lock = self._uat_refresh_locks.get(user_open_id)
        if lock is None:
            lock = Lock()
            self._uat_refresh_locks[user_open_id] = lock

        with lock:
            record = self._get_user_token_record(user_open_id)
            if not record:
                return None
            endpoints = self._resolve_oauth_endpoints(brand)
            payload = {
                "grant_type": "refresh_token",
                "refresh_token": str(record.get("refresh_token") or ""),
                "client_id": str(self.app_id),
                "client_secret": str(self.app_secret),
            }

            data = self._http_post_form(endpoints["token"], payload)
            code = data.get("code")
            error = data.get("error")

            if (code is not None and int(code) != 0) or error:
                if code is not None and int(code) in REFRESH_TOKEN_RETRYABLE:
                    data = self._http_post_form(endpoints["token"], payload)
                    code = data.get("code")
                    error = data.get("error")
                    if (code is not None and int(code) != 0) or error:
                        with self._uat_store_lock:
                            self._uat_store.pop(user_open_id, None)
                        return None
                else:
                    with self._uat_store_lock:
                        self._uat_store.pop(user_open_id, None)
                    return None

            access_token = data.get("access_token")
            if not access_token:
                with self._uat_store_lock:
                    self._uat_store.pop(user_open_id, None)
                return None

            refresh_token = data.get("refresh_token") or record.get("refresh_token") or ""
            expires_in = int(data.get("expires_in") or 7200)
            refresh_expires_in = int(data.get("refresh_token_expires_in") or 0)
            scope = str(data.get("scope") or record.get("scope") or "")
            if not refresh_expires_in:
                refresh_expires_in = max(int((refresh_expires_at - now_ms) / 1000), expires_in)
            self.set_user_token(
                user_open_id,
                access_token=str(access_token),
                refresh_token=str(refresh_token),
                scope=scope,
                expires_in=expires_in,
                refresh_expires_in=refresh_expires_in,
            )
            return str(access_token)

    def get_valid_user_access_token(self, user_open_id: str, required_scopes: Optional[List[str]] = None, brand: Optional[str] = None) -> Optional[str]:
        record = self._get_user_token_record(user_open_id)
        if not record:
            return None
        if required_scopes and not self._scope_covers(str(record.get("scope") or ""), required_scopes):
            return None
        now_ms = int(time.time() * 1000)
        expires_at = int(record.get("expires_at") or 0)
        if expires_at and now_ms < expires_at - 60_000:
            return str(record.get("access_token") or "")
        refreshed = self._refresh_user_token_for_user(user_open_id, brand=brand)
        return refreshed

    def oauth_request_device_authorization(self, scope: str, brand: Optional[str] = None) -> Dict:
        endpoints = self._resolve_oauth_endpoints(brand)
        scope_value = (scope or "").strip()
        if "offline_access" not in scope_value.split():
            scope_value = (scope_value + " offline_access").strip() if scope_value else "offline_access"
        basic = base64.b64encode(f"{self.app_id}:{self.app_secret}".encode("utf-8")).decode("utf-8")
        data = self._http_post_form(
            endpoints["device_authorization"],
            {"client_id": str(self.app_id), "scope": scope_value},
            headers={"Authorization": f"Basic {basic}"},
        )
        if data.get("error"):
            return self._wrap_result(code=-1, msg=str(data.get("error_description") or data.get("error")), data=data)
        if not data.get("device_code"):
            return self._wrap_result(code=-1, msg="device_authorization failed", data=data)
        return self._wrap_result(
            code=0,
            msg="ok",
            data={
                "device_code": data.get("device_code"),
                "user_code": data.get("user_code"),
                "verification_uri": data.get("verification_uri"),
                "verification_uri_complete": data.get("verification_uri_complete") or data.get("verification_uri"),
                "expires_in": int(data.get("expires_in") or 240),
                "interval": int(data.get("interval") or 5),
                "scope": scope_value,
            },
        )

    def oauth_poll_device_token(
        self,
        *,
        user_open_id: str,
        device_code: str,
        interval: int,
        expires_in: int,
        brand: Optional[str] = None,
    ) -> Dict:
        endpoints = self._resolve_oauth_endpoints(brand)
        deadline = time.time() + int(expires_in)
        poll_interval = max(int(interval), 1)
        while time.time() < deadline:
            time.sleep(poll_interval)
            data = self._http_post_form(
                endpoints["token"],
                {
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "device_code": device_code,
                    "client_id": str(self.app_id),
                    "client_secret": str(self.app_secret),
                },
            )
            if data.get("access_token"):
                access_token = str(data.get("access_token"))
                refresh_token = str(data.get("refresh_token") or "")
                token_scope = str(data.get("scope") or "")
                token_expires_in = int(data.get("expires_in") or 7200)
                refresh_expires_in = int(data.get("refresh_token_expires_in") or 604800)
                if not refresh_token:
                    refresh_expires_in = token_expires_in
                self.set_user_token(
                    user_open_id,
                    access_token=access_token,
                    refresh_token=refresh_token,
                    scope=token_scope,
                    expires_in=token_expires_in,
                    refresh_expires_in=refresh_expires_in,
                )
                return self._wrap_result(code=0, msg="ok", data={"user_open_id": user_open_id, "scope": token_scope})
            err = str(data.get("error") or "")
            if err == "authorization_pending":
                continue
            if err == "slow_down":
                poll_interval = min(poll_interval + 5, 60)
                continue
            if err == "access_denied":
                return self._wrap_result(code=-1, msg="用户拒绝了授权", data=data)
            if err in {"expired_token", "invalid_grant"}:
                return self._wrap_result(code=-1, msg="授权码已过期，请重新发起", data=data)
            if err:
                return self._wrap_result(code=-1, msg=str(data.get("error_description") or err), data=data)
        return self._wrap_result(code=-1, msg="授权超时，请重新发起", data=None)

    def build_oauth_auth_card(self, *, verification_uri_complete: str, expires_min: int, scope: str) -> Dict[str, Any]:
        url = verification_uri_complete
        multi_url = {"url": url, "pc_url": url, "android_url": url, "ios_url": url}
        scope_lines = "\n".join([f"- {s}" for s in (scope or "").split() if s])
        content = f"请点击下方按钮完成授权。\n\n需要的权限：\n{scope_lines}\n\n有效期：{int(expires_min)} 分钟"
        return {
            "schema": "2.0",
            "config": {"wide_screen_mode": False},
            "header": {
                "title": {"tag": "plain_text", "content": "需要授权"},
                "template": "blue",
                "icon": {"tag": "standard_icon", "token": "lock-chat_filled"},
            },
            "body": {
                "elements": [
                    {"tag": "markdown", "content": content},
                    {
                        "tag": "action",
                        "actions": [
                            {"tag": "button", "text": {"tag": "plain_text", "content": "去授权"}, "type": "primary", "multi_url": multi_url}
                        ],
                    },
                ]
            },
        }

    def send_oauth_auth_card(self, *, receive_id_type: str, receive_id: str, card: Dict[str, Any]) -> Dict:
        return self._request_with_token(
            method="POST",
            path="/open-apis/im/v1/messages",
            params={"receive_id_type": receive_id_type},
            body={
                "receive_id": receive_id,
                "msg_type": "interactive",
                "content": json.dumps(card, ensure_ascii=False),
            },
        )

    def user_request_with_auto_auth(
        self,
        *,
        user_open_id: str,
        required_scopes: List[str],
        receive_id_type: str,
        receive_id: str,
        method: str,
        path: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        body: Optional[Any] = None,
        wait_for_auth: bool = False,
        auth_timeout_sec: int = 300,
        brand: Optional[str] = None,
    ) -> Dict:
        token = self.get_valid_user_access_token(user_open_id, required_scopes=required_scopes, brand=brand)
        if not token:
            scope = " ".join([s for s in required_scopes if s]).strip()
            auth = self.oauth_request_device_authorization(scope, brand=brand)
            if auth.get("code") != 0:
                return auth
            info = auth.get("data") or {}
            card = self.build_oauth_auth_card(
                verification_uri_complete=str(info.get("verification_uri_complete") or ""),
                expires_min=max(int(info.get("expires_in") or 240) // 60, 1),
                scope=str(info.get("scope") or scope),
            )
            self.send_oauth_auth_card(receive_id_type=receive_id_type, receive_id=receive_id, card=card)
            if not wait_for_auth:
                return self._wrap_result(
                    code=LARK_ERROR["USER_SCOPE_INSUFFICIENT"],
                    msg="need_user_authorization",
                    data={
                        "auth_required": "user",
                        "user_open_id": user_open_id,
                        "required_scopes": required_scopes,
                        "device_code": info.get("device_code"),
                        "interval": info.get("interval"),
                        "expires_in": info.get("expires_in"),
                        "verification_uri_complete": info.get("verification_uri_complete"),
                    },
                )
            poll = self.oauth_poll_device_token(
                user_open_id=user_open_id,
                device_code=str(info.get("device_code") or ""),
                interval=int(info.get("interval") or 5),
                expires_in=min(int(info.get("expires_in") or 240), int(auth_timeout_sec)),
                brand=brand,
            )
            if poll.get("code") != 0:
                return poll
            token = self.get_valid_user_access_token(user_open_id, required_scopes=required_scopes, brand=brand)
            if not token:
                return self._wrap_result(code=-1, msg="授权完成但未获取到 token", data=None)

        result = self._request_with_token(
            method=method,
            path=path,
            token_type="user",
            user_access_token=token,
            headers=headers,
            params=params,
            body=body,
        )
        if result.get("code") in TOKEN_RETRY_CODES:
            refreshed = self._refresh_user_token_for_user(user_open_id, brand=brand)
            if refreshed:
                result = self._request_with_token(
                    method=method,
                    path=path,
                    token_type="user",
                    user_access_token=refreshed,
                    headers=headers,
                    params=params,
                    body=body,
                )
        return result

    def _parse_lark_response(self, resp: Any) -> Dict:
        success = bool(getattr(resp, "success", lambda: False)())
        default_code = 0 if success else int(getattr(resp, "code", -1) or -1)
        default_msg = str(getattr(resp, "msg", "success" if success else "请求失败") or "")

        log_id = None
        get_log_id = getattr(resp, "get_log_id", None)
        if callable(get_log_id):
            log_id = get_log_id()

        raw = getattr(getattr(resp, "raw", None), "content", None)
        parsed = self._safe_json_loads(raw)
        if isinstance(parsed, dict):
            code = int(parsed.get("code", default_code) or default_code)
            msg = str(parsed.get("msg", default_msg) or default_msg)
            data = parsed.get("data", parsed)
            return self._wrap_result(code=code, msg=msg, data=data, log_id=log_id)

        text = None
        if isinstance(raw, (bytes, bytearray)):
            text = raw.decode("utf-8", errors="replace")[:500]
        elif isinstance(raw, str):
            text = raw[:500]
        return self._wrap_result(code=default_code, msg=default_msg, data=None, log_id=log_id, text=text)

    def _wrap_exception(self, exc: Exception, context: str) -> Dict:
        return self._wrap_result(code=-1, msg=f"{context}失败: {exc}", data=None)
    
    def get_tenant_access_token(self) -> str:
        """获取租户访问凭证，SDK会自动缓存，无需手动调用"""
        if InternalTenantAccessTokenRequest is None:
            raise ModuleNotFoundError("缺少依赖 lark-oapi，请先安装：pip install lark-oapi")
        req = InternalTenantAccessTokenRequest.builder() \
            .request_body(InternalTenantAccessTokenRequestBody.builder()
                      .app_id(self.app_id)
                      .app_secret(self.app_secret)
                      .build()) \
            .build()
        resp = self.client.auth.v3.tenant_access_token.internal(req)
        if not resp.success():
            raise Exception(f"获取token失败: {resp.msg}")
        data = json.loads(resp.raw.content)
        return data['tenant_access_token']

    def _request(self, method: str, path: str, **kwargs) -> Dict:
        try:
            uri = path
            if uri.startswith("http://") or uri.startswith("https://"):
                if uri.startswith(self.domain):
                    uri = uri[len(self.domain):]
                else:
                    idx = uri.find("/open-apis/")
                    uri = uri[idx:] if idx >= 0 else uri
            if not uri.startswith("/"):
                uri = "/" + uri

            http_method = method.upper()
            http_method_enum = {
                "GET": lark.HttpMethod.GET,
                "POST": lark.HttpMethod.POST,
                "PUT": lark.HttpMethod.PUT,
                "DELETE": lark.HttpMethod.DELETE,
                "PATCH": lark.HttpMethod.PATCH,
            }.get(http_method)
            if http_method_enum is None:
                return self._wrap_result(code=-1, msg=f"不支持的HTTP方法: {method}", data=None)

            headers = kwargs.get("headers") or {}
            params = kwargs.get("params") or {}
            queries = [(str(k), str(v)) for k, v in params.items()]

            body = None
            if "json" in kwargs and kwargs["json"] is not None:
                body = kwargs["json"]
            elif "data" in kwargs and kwargs["data"] is not None:
                body = kwargs["data"]

            req_builder = lark.BaseRequest.builder() \
                .http_method(http_method_enum) \
                .uri(uri) \
                .token_types({lark.AccessTokenType.TENANT})
            if queries:
                req_builder = req_builder.queries(queries)
            if headers:
                req_builder = req_builder.headers(headers)
            if body is not None:
                req_builder = req_builder.body(body)
            req = req_builder.build()

            resp = self.client.request(req)
            return self._parse_lark_response(resp)
        except Exception as e:
            return self._wrap_exception(e, "原生请求")


FeishuClient = type('FeishuClient', tuple(mixin_classes + [_FeishuCore]), {})
