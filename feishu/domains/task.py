from typing import Any, Dict, List, Optional, Union


class TaskMixin:
    def create_task(
        self,
        summary: str,
        description: Optional[str] = None,
        members: Optional[List[Dict[str, Any]]] = None,
        due: Optional[Dict[str, Any]] = None,
        current_user_id: Optional[str] = None,
        user_access_token: Optional[str] = None,
    ) -> Dict:
        body: Dict[str, Any] = {"summary": summary}
        if description is not None:
            body["description"] = description
        if members is not None:
            body["members"] = members
        if due is not None:
            timestamp = due.get("timestamp")
            if timestamp is not None:
                due = dict(due)
                due["timestamp"] = self._coerce_datetime_to_ms(timestamp)
            body["due"] = due
        if current_user_id:
            members_list = body.get("members") or []
            exists = any(m.get("id") == current_user_id for m in members_list)
            if not exists:
                members_list.append({"id": current_user_id, "role": "follower"})
            body["members"] = members_list
        return self._request_with_token(
            method="POST",
            path="/open-apis/task/v1/tasks",
            token_type="user",
            user_access_token=user_access_token,
            body=body,
        )

    def list_tasks(
        self,
        completed: Optional[bool] = None,
        page_token: Optional[str] = None,
        page_size: int = 50,
        user_access_token: Optional[str] = None,
    ) -> Dict:
        params: Dict[str, Any] = {"page_token": page_token, "page_size": page_size}
        if completed is not None:
            params["completed"] = str(completed).lower()
        return self._request_with_token(
            method="GET",
            path="/open-apis/task/v1/tasks",
            token_type="user",
            user_access_token=user_access_token,
            params=params,
        )

    def get_task(self, task_guid: str, user_access_token: Optional[str] = None) -> Dict:
        return self._request_with_token(
            method="GET",
            path=f"/open-apis/task/v1/tasks/{task_guid}",
            token_type="user",
            user_access_token=user_access_token,
        )

    def update_task(
        self,
        task_guid: str,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        completed_at: Optional[Union[str, int]] = None,
        due: Optional[Dict[str, Any]] = None,
        members: Optional[List[Dict[str, Any]]] = None,
        user_access_token: Optional[str] = None,
    ) -> Dict:
        body: Dict[str, Any] = {}
        if summary is not None:
            body["summary"] = summary
        if description is not None:
            body["description"] = description
        if completed_at is not None:
            body["completed_at"] = "0" if str(completed_at) == "0" else self._coerce_datetime_to_ms(completed_at)
        if due is not None:
            timestamp = due.get("timestamp")
            if timestamp is not None:
                due = dict(due)
                due["timestamp"] = self._coerce_datetime_to_ms(timestamp)
            body["due"] = due
        if members is not None:
            body["members"] = members
        return self._request_with_token(
            method="PATCH",
            path=f"/open-apis/task/v1/tasks/{task_guid}",
            token_type="user",
            user_access_token=user_access_token,
            body=body,
        )

    def create_tasklist(
        self,
        name: str,
        members: Optional[List[Dict[str, Any]]] = None,
        user_access_token: Optional[str] = None,
    ) -> Dict:
        body: Dict[str, Any] = {"name": name}
        if members is not None:
            body["members"] = members
        return self._request_with_token(
            method="POST",
            path="/open-apis/task/v1/tasklists",
            token_type="user",
            user_access_token=user_access_token,
            body=body,
        )

    def list_tasklist_tasks(
        self,
        tasklist_guid: str,
        completed: Optional[bool] = None,
        page_token: Optional[str] = None,
        page_size: int = 50,
        user_access_token: Optional[str] = None,
    ) -> Dict:
        params: Dict[str, Any] = {"page_token": page_token, "page_size": page_size}
        if completed is not None:
            params["completed"] = str(completed).lower()
        return self._request_with_token(
            method="GET",
            path=f"/open-apis/task/v1/tasklists/{tasklist_guid}/tasks",
            token_type="user",
            user_access_token=user_access_token,
            params=params,
        )

    def add_tasklist_members(
        self,
        tasklist_guid: str,
        members: List[Dict[str, Any]],
        user_access_token: Optional[str] = None,
    ) -> Dict:
        body = {"members": members}
        return self._request_with_token(
            method="POST",
            path=f"/open-apis/task/v1/tasklists/{tasklist_guid}/members",
            token_type="user",
            user_access_token=user_access_token,
            body=body,
        )
