"""
Feishu/Lark OpenAPI Python Client
**完全基于官方 larksuite-oapi SDK 实现**
兼容所有原有接口，自动管理token，更稳定可靠
"""
import os
import json
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Union, Callable, List, Tuple

try:
    import lark_oapi as lark
    from lark_oapi.api.auth.v3 import InternalTenantAccessTokenRequestBody
    from lark_oapi.api.auth.v3.tenant_access_token.internal import InternalTenantAccessTokenRequest
except ModuleNotFoundError:
    lark = None
    InternalTenantAccessTokenRequest = None
    InternalTenantAccessTokenRequestBody = None

from .domains import (
    ImMixin,
    DocxMixin,
    BitableMixin,
    CalendarMixin,
    DriveMixin,
    TaskMixin,
    WikiMixin,
    TroubleshootMixin,
)


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

    def set_user_access_token_provider(self, provider: Optional[Callable[[], str]]) -> "FeishuClient":
        self._user_access_token_provider = provider
        return self

    def _get_user_access_token(self, user_access_token: Optional[str] = None) -> str:
        if user_access_token:
            return user_access_token
        if self._user_access_token_provider is not None:
            token = self._user_access_token_provider()
            if token:
                return token
        token = os.environ.get("FEISHU_USER_ACCESS_TOKEN")
        if token:
            return token
        raise ValueError("缺少 user_access_token：请传参或通过 set_user_access_token_provider 提供，或设置环境变量 FEISHU_USER_ACCESS_TOKEN")

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

            req_builder = lark.BaseRequest.builder() \
                .http_method(http_method_enum) \
                .uri(uri) \
                .token_types(token_types)
            if queries:
                req_builder = req_builder.queries(queries)
            if final_headers:
                req_builder = req_builder.headers(final_headers)
            if body is not None:
                req_builder = req_builder.body(body)
            req = req_builder.build()

            resp = self.client.request(req)
            return self._parse_lark_response(resp)
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

            req_builder = lark.BaseRequest.builder() \
                .http_method(http_method_enum) \
                .uri(uri) \
                .token_types(token_types)
            if queries:
                req_builder = req_builder.queries(queries)
            if final_headers:
                req_builder = req_builder.headers(final_headers)
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


class FeishuClient(ImMixin, DocxMixin, BitableMixin, CalendarMixin, DriveMixin, TaskMixin, WikiMixin, TroubleshootMixin, _FeishuCore):
    pass
