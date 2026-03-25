from typing import Dict

try:
    from lark_oapi.api.drive.v1 import AddPermissionCollaboratorRequest
except ModuleNotFoundError:
    AddPermissionCollaboratorRequest = None


class DriveMixin:
    def add_collaborator(
        self,
        document_id: str,
        user_open_id: str,
        perm_type: str = "edit",
        need_notification: bool = True,
    ) -> Dict:
        try:
            if AddPermissionCollaboratorRequest is None:
                raise ModuleNotFoundError("缺少依赖 lark-oapi，请先安装：pip install lark-oapi")

            req = (
                AddPermissionCollaboratorRequest.builder()
                .token(document_id)
                .type("doc")
                .role(perm_type)
                .need_notification(need_notification)
                .collaborators([user_open_id])
                .build()
            )
            resp = self.client.drive.v1.permission.add_collaborator(req)
            return self._parse_lark_response(resp)
        except Exception as e:
            return self._wrap_exception(e, "添加协作者")
