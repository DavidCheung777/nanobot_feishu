from typing import Any, Dict, Optional, Union, List


class CalendarMixin:
    def list_calendars(
        self,
        user_access_token: Optional[str] = None,
        page_token: Optional[str] = None,
        page_size: int = 100,
    ) -> Dict:
        return self._request_with_token(
            method="GET",
            path="/open-apis/calendar/v4/calendars",
            token_type="user",
            user_access_token=user_access_token,
            params={"page_token": page_token, "page_size": page_size},
        )

    def list_calendar_events(
        self,
        calendar_id: str,
        start_time: Optional[Union[str, int]] = None,
        end_time: Optional[Union[str, int]] = None,
        page_token: Optional[str] = None,
        page_size: int = 100,
        user_access_token: Optional[str] = None,
    ) -> Dict:
        params: Dict[str, Any] = {"page_token": page_token, "page_size": page_size}
        if start_time is not None:
            params["start_time"] = self._coerce_datetime_to_ms(start_time)
        if end_time is not None:
            params["end_time"] = self._coerce_datetime_to_ms(end_time)
        return self._request_with_token(
            method="GET",
            path=f"/open-apis/calendar/v4/calendars/{calendar_id}/events",
            token_type="user",
            user_access_token=user_access_token,
            params=params,
        )

    def get_calendar_event(
        self,
        calendar_id: str,
        event_id: str,
        user_access_token: Optional[str] = None,
    ) -> Dict:
        return self._request_with_token(
            method="GET",
            path=f"/open-apis/calendar/v4/calendars/{calendar_id}/events/{event_id}",
            token_type="user",
            user_access_token=user_access_token,
        )

    def create_calendar_event(
        self,
        calendar_id: str,
        event: Optional[Dict[str, Any]] = None,
        summary: Optional[str] = None,
        start_time: Optional[Union[str, int]] = None,
        end_time: Optional[Union[str, int]] = None,
        description: Optional[str] = None,
        timezone: str = "Asia/Shanghai",
        attendees: Optional[List[Dict[str, Any]]] = None,
        user_open_id: Optional[str] = None,
        user_access_token: Optional[str] = None,
    ) -> Dict:
        body: Dict[str, Any] = {}
        if event:
            body.update(event)
        if summary is not None:
            body["summary"] = summary
        if description is not None:
            body["description"] = description
        if start_time is not None:
            body["start_time"] = {"timestamp": self._coerce_datetime_to_ms(start_time), "timezone": timezone}
        if end_time is not None:
            body["end_time"] = {"timestamp": self._coerce_datetime_to_ms(end_time), "timezone": timezone}
        if attendees is not None:
            body["attendees"] = attendees
        if user_open_id:
            attendee_list = body.get("attendees") or []
            exists = any(a.get("id") == user_open_id for a in attendee_list)
            if not exists:
                attendee_list.append({"type": "user", "id": user_open_id})
            body["attendees"] = attendee_list
        return self._request_with_token(
            method="POST",
            path=f"/open-apis/calendar/v4/calendars/{calendar_id}/events",
            token_type="user",
            user_access_token=user_access_token,
            body=body,
        )

    def update_calendar_event(
        self,
        calendar_id: str,
        event_id: str,
        event: Dict[str, Any],
        user_access_token: Optional[str] = None,
    ) -> Dict:
        return self._request_with_token(
            method="PATCH",
            path=f"/open-apis/calendar/v4/calendars/{calendar_id}/events/{event_id}",
            token_type="user",
            user_access_token=user_access_token,
            body=event,
        )

    def delete_calendar_event(
        self,
        calendar_id: str,
        event_id: str,
        user_access_token: Optional[str] = None,
    ) -> Dict:
        return self._request_with_token(
            method="DELETE",
            path=f"/open-apis/calendar/v4/calendars/{calendar_id}/events/{event_id}",
            token_type="user",
            user_access_token=user_access_token,
        )

    def search_calendar_events(
        self,
        query: str,
        calendar_id: Optional[str] = None,
        user_access_token: Optional[str] = None,
        page_token: Optional[str] = None,
        page_size: int = 50,
    ) -> Dict:
        body: Dict[str, Any] = {"query": query, "page_size": page_size}
        if page_token:
            body["page_token"] = page_token
        if calendar_id:
            body["calendar_id"] = calendar_id
        return self._request_with_token(
            method="POST",
            path="/open-apis/calendar/v4/events/search",
            token_type="user",
            user_access_token=user_access_token,
            body=body,
        )

    def reply_calendar_event(
        self,
        calendar_id: str,
        event_id: str,
        rsvp_status: str,
        user_access_token: Optional[str] = None,
    ) -> Dict:
        body = {"rsvp_status": rsvp_status}
        return self._request_with_token(
            method="POST",
            path=f"/open-apis/calendar/v4/calendars/{calendar_id}/events/{event_id}/reply",
            token_type="user",
            user_access_token=user_access_token,
            body=body,
        )

    def list_calendar_event_instances(
        self,
        calendar_id: str,
        event_id: str,
        start_time: Optional[Union[str, int]] = None,
        end_time: Optional[Union[str, int]] = None,
        user_access_token: Optional[str] = None,
    ) -> Dict:
        params: Dict[str, Any] = {}
        if start_time is not None:
            params["start_time"] = self._coerce_datetime_to_ms(start_time)
        if end_time is not None:
            params["end_time"] = self._coerce_datetime_to_ms(end_time)
        return self._request_with_token(
            method="GET",
            path=f"/open-apis/calendar/v4/calendars/{calendar_id}/events/{event_id}/instances",
            token_type="user",
            user_access_token=user_access_token,
            params=params,
        )

    def list_calendar_freebusy(
        self,
        time_min: Union[str, int],
        time_max: Union[str, int],
        user_ids: List[str],
        user_access_token: Optional[str] = None,
    ) -> Dict:
        body = {
            "time_min": {"timestamp": self._coerce_datetime_to_ms(time_min), "timezone": "Asia/Shanghai"},
            "time_max": {"timestamp": self._coerce_datetime_to_ms(time_max), "timezone": "Asia/Shanghai"},
            "user_ids": user_ids,
        }
        return self._request_with_token(
            method="POST",
            path="/open-apis/calendar/v4/freebusy/list",
            token_type="user",
            user_access_token=user_access_token,
            body=body,
        )

    def create_calendar_event_attendees(
        self,
        calendar_id: str,
        event_id: str,
        attendees: List[Dict[str, Any]],
        user_access_token: Optional[str] = None,
    ) -> Dict:
        body = {"attendees": attendees}
        return self._request_with_token(
            method="POST",
            path=f"/open-apis/calendar/v4/calendars/{calendar_id}/events/{event_id}/attendees",
            token_type="user",
            user_access_token=user_access_token,
            body=body,
        )

    def list_calendar_event_attendees(
        self,
        calendar_id: str,
        event_id: str,
        user_access_token: Optional[str] = None,
        page_token: Optional[str] = None,
        page_size: int = 100,
    ) -> Dict:
        params: Dict[str, Any] = {"page_token": page_token, "page_size": page_size}
        return self._request_with_token(
            method="GET",
            path=f"/open-apis/calendar/v4/calendars/{calendar_id}/events/{event_id}/attendees",
            token_type="user",
            user_access_token=user_access_token,
            params=params,
        )
