import json
import unittest
from unittest import mock

import feishu.feishu_client as fc


class _DummyRaw:
    def __init__(self, content):
        self.content = content


class _DummyResp:
    def __init__(self, *, success, code=None, msg=None, raw_content=None, log_id=None):
        self._success = success
        self.code = code
        self.msg = msg
        self.raw = _DummyRaw(raw_content)
        self._log_id = log_id

    def success(self):
        return self._success

    def get_log_id(self):
        return self._log_id


class _FakeHttpMethod:
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


class _FakeAccessTokenType:
    TENANT = "TENANT"
    USER = "USER"


class _FakeBaseRequest:
    @classmethod
    def builder(cls):
        return _FakeBaseRequestBuilder()


class _FakeBaseRequestBuilder:
    def __init__(self):
        self._http_method = None
        self._uri = None
        self._token_types = None
        self._queries = None
        self._headers = None
        self._body = None

    def http_method(self, http_method):
        self._http_method = http_method
        return self

    def uri(self, uri):
        self._uri = uri
        return self

    def token_types(self, token_types):
        self._token_types = token_types
        return self

    def queries(self, queries):
        self._queries = queries
        return self

    def headers(self, headers):
        self._headers = headers
        return self

    def body(self, body):
        self._body = body
        return self

    def build(self):
        return {
            "http_method": self._http_method,
            "uri": self._uri,
            "token_types": self._token_types,
            "queries": self._queries,
            "headers": self._headers,
            "body": self._body,
        }


class TestFeishuClient(unittest.TestCase):
    def setUp(self):
        self._orig_lark = fc.lark
        fc.lark = mock.Mock()
        fc.lark.HttpMethod = _FakeHttpMethod
        fc.lark.AccessTokenType = _FakeAccessTokenType
        fc.lark.BaseRequest = _FakeBaseRequest

    def tearDown(self):
        fc.lark = self._orig_lark

    def _make_client(self):
        client = fc.FeishuClient.__new__(fc.FeishuClient)
        client.domain = "https://open.feishu.cn"
        client.client = mock.Mock()
        client._user_access_token_provider = None
        return client

    def test_parse_lark_response_success_prefers_data(self):
        resp = _DummyResp(
            success=True,
            raw_content=json.dumps({"code": 0, "msg": "ok", "data": {"k": "v"}}).encode("utf-8"),
            log_id="log-1",
        )
        client = self._make_client()
        result = client._parse_lark_response(resp)
        self.assertEqual(result["code"], 0)
        self.assertEqual(result["msg"], "ok")
        self.assertEqual(result["data"], {"k": "v"})
        self.assertEqual(result["log_id"], "log-1")

    def test_parse_lark_response_non_json_includes_text(self):
        resp = _DummyResp(success=False, code=100, msg="bad", raw_content=b"not-json", log_id="log-2")
        client = self._make_client()
        result = client._parse_lark_response(resp)
        self.assertEqual(result["code"], 100)
        self.assertEqual(result["msg"], "bad")
        self.assertIsNone(result["data"])
        self.assertEqual(result["log_id"], "log-2")
        self.assertIn("text", result)

    def test_request_with_token_wraps_exceptions(self):
        client = self._make_client()
        client.client.request.side_effect = RuntimeError("boom")
        result = client._request_with_token(method="GET", path="/open-apis/im/v1/messages")
        self.assertEqual(result["code"], -1)
        self.assertIn("请求失败", result["msg"])

    def test_request_with_token_normalizes_uri_and_user_token(self):
        client = self._make_client()
        client.client.request.return_value = _DummyResp(
            success=True,
            raw_content=json.dumps({"code": 0, "msg": "ok", "data": {"ok": True}}).encode("utf-8"),
        )
        result = client._request_with_token(
            method="GET",
            path="https://open.feishu.cn/open-apis/calendar/v4/calendars",
            token_type="user",
            user_access_token="u-1",
        )
        self.assertEqual(result["code"], 0)
        args, _ = client.client.request.call_args
        built_req = args[0]
        self.assertEqual(built_req["uri"], "/open-apis/calendar/v4/calendars")
        self.assertEqual(built_req["headers"]["Authorization"], "Bearer u-1")
        self.assertEqual(built_req["token_types"], {_FakeAccessTokenType.USER})

    def test_request_with_token_unsupported_method_returns_error(self):
        client = self._make_client()
        result = client._request_with_token(method="TRACE", path="/open-apis/im/v1/messages")
        self.assertEqual(result["code"], -1)
        self.assertIn("不支持的HTTP方法", result["msg"])

    def test_request_raw_with_token_defaults_code(self):
        client = self._make_client()
        client.client.request.return_value = _DummyResp(
            success=False,
            code=None,
            msg="bad",
            raw_content=b"payload",
            log_id="log-3",
        )
        result = client._request_raw_with_token(method="GET", path="/open-apis/drive/v1/medias/download")
        self.assertEqual(result["code"], -1)
        data = result.get("data") or {}
        self.assertEqual(data.get("content"), b"payload")
        self.assertEqual(data.get("log_id"), "log-3")

    def test_coerce_datetime_to_ms(self):
        client = self._make_client()
        self.assertEqual(client._coerce_datetime_to_ms(1710000000), "1710000000000")
        self.assertEqual(client._coerce_datetime_to_ms("1710000000000"), "1710000000000")
        self.assertTrue(client._coerce_datetime_to_ms("2026-02-25T14:00:00+08:00").isdigit())
