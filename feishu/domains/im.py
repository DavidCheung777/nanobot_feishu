from typing import Any, Dict, Optional, Union, List

try:
    from lark_oapi.api.im.v1 import (
        CreateMessageRequest,
        CreateMessageRequestBody,
        ReplyMessageRequest,
        CreateReactionRequest,
        ReactionType,
    )
except ModuleNotFoundError:
    CreateMessageRequest = None
    CreateMessageRequestBody = None
    ReplyMessageRequest = None
    CreateReactionRequest = None
    ReactionType = None


class ImMixin:
    def send_message(
        self,
        receive_id_type: str,
        receive_id: str,
        content: Union[str, Dict],
        msg_type: str = "text",
    ) -> Dict:
        try:
            if CreateMessageRequest is None:
                raise ModuleNotFoundError("缺少依赖 lark-oapi，请先安装：pip install lark-oapi")

            formatted_content = self._normalize_message_content(msg_type, content)
            req = (
                CreateMessageRequest.builder()
                .receive_id_type(receive_id_type)
                .request_body(
                    CreateMessageRequestBody.builder()
                    .receive_id(receive_id)
                    .msg_type(msg_type)
                    .content(formatted_content)
                    .build()
                )
                .build()
            )
            resp = self.client.im.v1.message.create(req)
            return self._parse_lark_response(resp)
        except Exception as e:
            return self._wrap_exception(e, "发送消息")

    def reply_message(
        self,
        message_id: str,
        content: Union[str, Dict],
        msg_type: str = "text",
    ) -> Dict:
        try:
            if ReplyMessageRequest is None:
                raise ModuleNotFoundError("缺少依赖 lark-oapi，请先安装：pip install lark-oapi")

            formatted_content = self._normalize_message_content(msg_type, content)
            req = (
                ReplyMessageRequest.builder()
                .message_id(message_id)
                .msg_type(msg_type)
                .content(formatted_content)
                .build()
            )
            resp = self.client.im.v1.message.reply(req)
            return self._parse_lark_response(resp)
        except Exception as e:
            return self._wrap_exception(e, "回复消息")

    def add_reaction(self, message_id: str, reaction_type: str) -> Dict:
        try:
            if CreateReactionRequest is None:
                raise ModuleNotFoundError("缺少依赖 lark-oapi，请先安装：pip install lark-oapi")

            req = (
                CreateReactionRequest.builder()
                .message_id(message_id)
                .reaction_type(ReactionType.builder().emoji_type(reaction_type).build())
                .build()
            )
            resp = self.client.im.v1.reaction.create(req)
            return self._parse_lark_response(resp)
        except Exception as e:
            return self._wrap_exception(e, "添加反应")

    def list_messages(
        self,
        container_id_type: str,
        container_id: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        sort_type: Optional[str] = None,
        page_token: Optional[str] = None,
        page_size: int = 20,
    ) -> Dict:
        params: Dict[str, Any] = {
            "container_id_type": container_id_type,
            "container_id": container_id,
            "start_time": start_time,
            "end_time": end_time,
            "sort_type": sort_type,
            "page_token": page_token,
            "page_size": page_size,
        }
        return self._request_with_token(method="GET", path="/open-apis/im/v1/messages", params=params)

    def user_get_messages(
        self,
        *,
        chat_id: Optional[str] = None,
        open_id: Optional[str] = None,
        relative_time: Optional[str] = None,
        start_time: Optional[Union[str, int]] = None,
        end_time: Optional[Union[str, int]] = None,
        page_token: Optional[str] = None,
        page_size: int = 50,
        sort_rule: Optional[str] = None,
        user_access_token: Optional[str] = None,
    ) -> Dict:
        params: Dict[str, Any] = {
            "chat_id": chat_id,
            "open_id": open_id,
            "relative_time": relative_time,
            "page_token": page_token,
            "page_size": page_size,
            "sort_rule": sort_rule,
        }
        if start_time is not None:
            params["start_time"] = self._coerce_datetime_to_ms(start_time)
        if end_time is not None:
            params["end_time"] = self._coerce_datetime_to_ms(end_time)
        return self._request_with_token(
            method="GET",
            path="/open-apis/im/v1/messages",
            token_type="user",
            user_access_token=user_access_token,
            params=params,
        )

    def user_get_thread_messages(
        self,
        thread_id: str,
        page_token: Optional[str] = None,
        page_size: int = 50,
        sort_rule: Optional[str] = None,
        user_access_token: Optional[str] = None,
    ) -> Dict:
        params: Dict[str, Any] = {
            "page_token": page_token,
            "page_size": page_size,
            "sort_rule": sort_rule,
        }
        return self._request_with_token(
            method="GET",
            path=f"/open-apis/im/v1/messages/{thread_id}/replies",
            token_type="user",
            user_access_token=user_access_token,
            params=params,
        )

    def user_search_messages(
        self,
        *,
        query: Optional[str] = None,
        sender_ids: Optional[List[str]] = None,
        chat_id: Optional[str] = None,
        relative_time: Optional[str] = None,
        start_time: Optional[Union[str, int]] = None,
        end_time: Optional[Union[str, int]] = None,
        mention_ids: Optional[List[str]] = None,
        message_type: Optional[str] = None,
        sender_type: Optional[str] = None,
        chat_type: Optional[str] = None,
        page_token: Optional[str] = None,
        page_size: int = 50,
        user_access_token: Optional[str] = None,
    ) -> Dict:
        body: Dict[str, Any] = {
            "query": query,
            "sender_ids": sender_ids,
            "chat_id": chat_id,
            "relative_time": relative_time,
            "mention_ids": mention_ids,
            "message_type": message_type,
            "sender_type": sender_type,
            "chat_type": chat_type,
            "page_token": page_token,
            "page_size": page_size,
        }
        if start_time is not None:
            body["start_time"] = self._coerce_datetime_to_ms(start_time)
        if end_time is not None:
            body["end_time"] = self._coerce_datetime_to_ms(end_time)
        return self._request_with_token(
            method="POST",
            path="/open-apis/im/v1/messages/search",
            token_type="user",
            user_access_token=user_access_token,
            body=body,
        )

    def user_fetch_resource(
        self,
        message_id: str,
        file_key: str,
        resource_type: str,
        output_path: Optional[str] = None,
        user_access_token: Optional[str] = None,
    ) -> Dict:
        params = {"type": resource_type}
        result = self._request_raw_with_token(
            method="GET",
            path=f"/open-apis/im/v1/messages/{message_id}/resources/{file_key}",
            token_type="user",
            user_access_token=user_access_token,
            params=params,
        )
        data = result.get("data") or {}
        content = data.get("content") if isinstance(data, dict) else None
        if output_path and isinstance(content, (bytes, bytearray)):
            with open(output_path, "wb") as f:
                f.write(content)
            return self._wrap_result(code=result.get("code", 0), msg=result.get("msg", ""), data={"output_path": output_path})
        return self._wrap_result(code=result.get("code", 0), msg=result.get("msg", ""), data={"content": content})
