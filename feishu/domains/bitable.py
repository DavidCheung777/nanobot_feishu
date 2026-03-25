import json
from typing import Any, Dict, Iterable, Optional, List, Union


class BitableMixin:
    def create_bitable_app(self, name: str, folder_token: Optional[str] = None) -> Dict:
        body: Dict[str, Any] = {"name": name}
        if folder_token:
            body["folder_token"] = folder_token
        return self._request_with_token(method="POST", path="/open-apis/bitable/v1/apps", body=body)

    def list_bitable_tables(self, app_token: str, page_token: Optional[str] = None, page_size: int = 100) -> Dict:
        params: Dict[str, Any] = {"page_token": page_token, "page_size": page_size}
        return self._request_with_token(
            method="GET",
            path=f"/open-apis/bitable/v1/apps/{app_token}/tables",
            params=params,
        )

    def create_bitable_table(self, app_token: str, name: str, fields: Optional[List[Dict[str, Any]]] = None) -> Dict:
        body: Dict[str, Any] = {"name": name}
        if fields:
            body["fields"] = fields
        return self._request_with_token(
            method="POST",
            path=f"/open-apis/bitable/v1/apps/{app_token}/tables",
            body=body,
        )

    def list_bitable_fields(self, app_token: str, table_id: str, view_id: Optional[str] = None) -> Dict:
        params: Dict[str, Any] = {"view_id": view_id}
        return self._request_with_token(
            method="GET",
            path=f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields",
            params=params,
        )

    def create_bitable_field(
        self,
        app_token: str,
        table_id: str,
        field_name: str,
        field_type: int,
        property: Optional[Dict[str, Any]] = None,
    ) -> Dict:
        body: Dict[str, Any] = {"field_name": field_name, "type": field_type}
        if property is not None:
            body["property"] = property
        return self._request_with_token(
            method="POST",
            path=f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields",
            body=body,
        )

    def update_bitable_field(
        self,
        app_token: str,
        table_id: str,
        field_id: str,
        field_name: Optional[str] = None,
        property: Optional[Dict[str, Any]] = None,
    ) -> Dict:
        body: Dict[str, Any] = {}
        if field_name is not None:
            body["field_name"] = field_name
        if property is not None:
            body["property"] = property
        return self._request_with_token(
            method="PUT",
            path=f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields/{field_id}",
            body=body,
        )

    def delete_bitable_field(self, app_token: str, table_id: str, field_id: str) -> Dict:
        return self._request_with_token(
            method="DELETE",
            path=f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields/{field_id}",
        )

    def list_bitable_views(self, app_token: str, table_id: str, page_token: Optional[str] = None, page_size: int = 100) -> Dict:
        params: Dict[str, Any] = {"page_token": page_token, "page_size": page_size}
        return self._request_with_token(
            method="GET",
            path=f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/views",
            params=params,
        )

    def create_bitable_view(self, app_token: str, table_id: str, view_name: str, view_type: str) -> Dict:
        body: Dict[str, Any] = {"view_name": view_name, "view_type": view_type}
        return self._request_with_token(
            method="POST",
            path=f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/views",
            body=body,
        )

    def delete_bitable_view(self, app_token: str, table_id: str, view_id: str) -> Dict:
        return self._request_with_token(
            method="DELETE",
            path=f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/views/{view_id}",
        )

    def create_bitable_record(self, app_token: str, table_id: str, fields: Dict) -> Dict:
        return self._request_with_token(
            method="POST",
            path=f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records",
            body={"fields": fields},
        )

    def list_bitable_records(
        self,
        app_token: str,
        table_id: str,
        filter: Optional[Union[str, Dict[str, Any]]] = None,
        sort: Optional[Union[str, List[Dict[str, Any]]]] = None,
        view_id: Optional[str] = None,
        field_names: Optional[Iterable[str]] = None,
        page_token: Optional[str] = None,
        page_size: int = 100,
    ) -> Dict:
        params: Dict[str, Any] = {
            "view_id": view_id,
            "page_token": page_token,
            "page_size": page_size,
        }
        if filter is not None:
            params["filter"] = json.dumps(filter, ensure_ascii=False) if isinstance(filter, dict) else filter
        if sort is not None:
            params["sort"] = json.dumps(sort, ensure_ascii=False) if isinstance(sort, list) else sort
        if field_names is not None:
            params["field_names"] = json.dumps(list(field_names), ensure_ascii=False)
        return self._request_with_token(
            method="GET",
            path=f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records",
            params=params,
        )

    def get_bitable_record(self, app_token: str, table_id: str, record_id: str) -> Dict:
        return self._request_with_token(
            method="GET",
            path=f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}",
        )

    def update_bitable_record(self, app_token: str, table_id: str, record_id: str, fields: Dict) -> Dict:
        return self._request_with_token(
            method="PUT",
            path=f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}",
            body={"fields": fields},
        )

    def batch_create_bitable_records(self, app_token: str, table_id: str, records: List[Dict[str, Any]]) -> Dict:
        return self._request_with_token(
            method="POST",
            path=f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create",
            body={"records": records},
        )

    def batch_update_bitable_records(self, app_token: str, table_id: str, records: List[Dict[str, Any]]) -> Dict:
        return self._request_with_token(
            method="POST",
            path=f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_update",
            body={"records": records},
        )

    def delete_bitable_record(self, app_token: str, table_id: str, record_id: str) -> Dict:
        return self._request_with_token(
            method="DELETE",
            path=f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}",
        )

    def batch_delete_bitable_records(self, app_token: str, table_id: str, record_ids: List[str]) -> Dict:
        records = [{"record_id": record_id} for record_id in record_ids]
        return self._request_with_token(
            method="POST",
            path=f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_delete",
            body={"records": records},
        )

    def upload_bitable_attachment(
        self,
        app_token: str,
        table_id: str,
        file_name: str,
        file_base64: str,
        mime_type: Optional[str] = None,
    ) -> Dict:
        body: Dict[str, Any] = {"file_name": file_name, "file": file_base64}
        if mime_type:
            body["mime_type"] = mime_type
        return self._request_with_token(
            method="POST",
            path=f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/upload",
            body=body,
        )
