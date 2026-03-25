import base64
import re
from typing import Any, Dict, Optional

try:
    from lark_oapi.api.docx.v1 import GetDocumentRequest
except ModuleNotFoundError:
    GetDocumentRequest = None


class DocxMixin:
    def _extract_doc_token(self, doc_id_or_url: str) -> str:
        if "/docx/" in doc_id_or_url:
            return doc_id_or_url.split("/docx/")[-1].split("?")[0].strip()
        if "/wiki/" in doc_id_or_url:
            return doc_id_or_url.split("/wiki/")[-1].split("?")[0].strip()
        return doc_id_or_url.strip()

    def _extract_markdown_from_raw(self, data: Any) -> Optional[str]:
        if isinstance(data, dict):
            content = data.get("content")
            if isinstance(content, str):
                try:
                    return base64.b64decode(content).decode("utf-8")
                except Exception:
                    return content
        return None

    def get_document(self, document_id: str) -> Dict:
        try:
            if GetDocumentRequest is None:
                raise ModuleNotFoundError("缺少依赖 lark-oapi，请先安装：pip install lark-oapi")

            req = GetDocumentRequest.builder().document_id(document_id).build()
            resp = self.client.docx.v1.document.get(req)
            return self._parse_lark_response(resp)
        except Exception as e:
            return self._wrap_exception(e, "获取文档")

    def create_document(self, title: str, content: str, folder_token: Optional[str] = None) -> Dict:
        content_b64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        body: Dict[str, Any] = {"title": title, "content": content_b64, "content_type": 1}
        if folder_token:
            body["folder_token"] = folder_token
        return self._request_with_token(method="POST", path="/open-apis/docx/v1/documents", body=body)

    def create_doc_from_markdown(
        self,
        markdown: str,
        title: Optional[str] = None,
        folder_token: Optional[str] = None,
        wiki_node: Optional[str] = None,
        wiki_space: Optional[str] = None,
    ) -> Dict:
        content_b64 = base64.b64encode(markdown.encode("utf-8")).decode("utf-8")
        body: Dict[str, Any] = {"content": content_b64, "content_type": 1}
        if title:
            body["title"] = title
        if folder_token and not wiki_node and not wiki_space:
            body["folder_token"] = folder_token
        create_resp = self._request_with_token(method="POST", path="/open-apis/docx/v1/documents", body=body)
        if create_resp.get("code") != 0 or (not wiki_node and not wiki_space):
            return create_resp
        data = create_resp.get("data") or {}
        doc_token = data.get("document_id") or data.get("document", {}).get("document_id") or data.get("document", {}).get("document_token")
        if not doc_token:
            return create_resp
        if wiki_node:
            wiki_token = self._extract_doc_token(wiki_node)
            node = self.get_wiki_node(wiki_token)
            space_id = (node.get("data") or {}).get("space_id")
            if space_id:
                return self._request_with_token(
                    method="POST",
                    path=f"/open-apis/wiki/v2/spaces/{space_id}/nodes",
                    body={"parent_node_token": wiki_token, "obj_type": "docx", "obj_token": doc_token, "title": title or ""},
                )
        if wiki_space:
            space_id = wiki_space
            return self._request_with_token(
                method="POST",
                path=f"/open-apis/wiki/v2/spaces/{space_id}/nodes",
                body={"obj_type": "docx", "obj_token": doc_token, "title": title or ""},
            )
        return create_resp

    def get_document_raw_content(self, document_id: str) -> Dict:
        return self._request_with_token(
            method="GET",
            path=f"/open-apis/docx/v1/documents/{document_id}/raw_content",
        )

    def update_document(self, document_id: str, content: str) -> Dict:
        content_b64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        body: Dict[str, Any] = {"content": content_b64, "content_type": 1}
        return self._request_with_token(
            method="PATCH",
            path=f"/open-apis/docx/v1/documents/{document_id}/raw_content",
            body=body,
        )

    def fetch_doc_markdown(self, doc_id_or_url: str) -> Dict:
        doc_token = self._extract_doc_token(doc_id_or_url)
        if "/wiki/" in doc_id_or_url:
            wiki = self.get_wiki_node(doc_token)
            data = wiki.get("data") or {}
            obj_type = data.get("obj_type")
            obj_token = data.get("obj_token")
            if obj_type != "docx" or not obj_token:
                return self._wrap_result(code=-1, msg="不支持的文档类型", data=wiki)
            doc_token = obj_token
        resp = self.get_document_raw_content(doc_token)
        data = resp.get("data") or {}
        markdown = self._extract_markdown_from_raw(data)
        return self._wrap_result(code=resp.get("code", -1), msg=resp.get("msg", ""), data={"markdown": markdown, "raw": data})

    def update_doc(
        self,
        *,
        doc_id_or_url: str,
        mode: str,
        markdown: Optional[str] = None,
        selection_with_ellipsis: Optional[str] = None,
        selection_by_title: Optional[str] = None,
        new_title: Optional[str] = None,
    ) -> Dict:
        fetch = self.fetch_doc_markdown(doc_id_or_url)
        if fetch.get("code") != 0:
            return fetch
        raw = fetch.get("data") or {}
        content = raw.get("markdown") or ""
        if mode == "overwrite":
            updated = markdown or ""
        elif mode == "append":
            updated = content + ("\n" + markdown if markdown else "")
        elif mode in {"replace_range", "replace_all", "insert_before", "insert_after", "delete_range"}:
            target = content
            if selection_by_title:
                title = selection_by_title.lstrip("#").strip()
                pattern = re.compile(r"^(#{1,9})\\s+(.+)$", re.MULTILINE)
                matches = list(pattern.finditer(target))
                start_idx = None
                end_idx = None
                current_level = None
                for idx, match in enumerate(matches):
                    if match.group(2).strip() == title:
                        start_idx = match.start()
                        current_level = len(match.group(1))
                        for nxt in matches[idx + 1 :]:
                            if len(nxt.group(1)) <= current_level:
                                end_idx = nxt.start()
                                break
                        break
                if start_idx is None:
                    return self._wrap_result(code=-1, msg="未找到目标标题", data=None)
                end_idx = end_idx or len(target)
                replacement = markdown or ""
                if mode == "insert_before":
                    updated = target[:start_idx] + replacement + target[start_idx:]
                elif mode == "insert_after":
                    updated = target[:end_idx] + replacement + target[end_idx:]
                elif mode == "delete_range":
                    updated = target[:start_idx] + target[end_idx:]
                else:
                    updated = target[:start_idx] + replacement + target[end_idx:]
            elif selection_with_ellipsis:
                ellipsis = selection_with_ellipsis.replace("\\.\\.\\.", "\u0000")
                if "..." in ellipsis:
                    left, right = ellipsis.split("...", 1)
                    left = left.replace("\u0000", "...")
                    right = right.replace("\u0000", "...")
                    start = target.find(left)
                    if start < 0:
                        return self._wrap_result(code=-1, msg="未找到起始匹配", data=None)
                    end = target.find(right, start + len(left))
                    if end < 0:
                        return self._wrap_result(code=-1, msg="未找到结束匹配", data=None)
                    end = end + len(right)
                    replacement = markdown or ""
                    if mode == "insert_before":
                        updated = target[:start] + replacement + target[start:]
                    elif mode == "insert_after":
                        updated = target[:end] + replacement + target[end:]
                    elif mode == "delete_range":
                        updated = target[:start] + target[end:]
                    elif mode == "replace_all":
                        updated = target.replace(target[start:end], replacement)
                    else:
                        updated = target[:start] + replacement + target[end:]
                else:
                    literal = ellipsis.replace("\u0000", "...")
                    if literal not in target:
                        return self._wrap_result(code=-1, msg="未找到匹配内容", data=None)
                    if mode == "insert_before":
                        updated = target.replace(literal, (markdown or "") + literal, 1)
                    elif mode == "insert_after":
                        updated = target.replace(literal, literal + (markdown or ""), 1)
                    elif mode == "delete_range":
                        updated = target.replace(literal, "", 1)
                    elif mode == "replace_all":
                        updated = target.replace(literal, markdown or "")
                    else:
                        updated = target.replace(literal, markdown or "", 1)
            else:
                return self._wrap_result(code=-1, msg="缺少定位参数", data=None)
        else:
            return self._wrap_result(code=-1, msg="不支持的模式", data=None)

        doc_token = self._extract_doc_token(doc_id_or_url)
        update_resp = self.update_document(doc_token, updated)
        if new_title:
            self._request_with_token(
                method="PATCH",
                path=f"/open-apis/docx/v1/documents/{doc_token}",
                body={"title": new_title},
            )
        return update_resp

    def download_doc_media(
        self,
        resource_token: str,
        resource_type: str = "media",
        output_path: Optional[str] = None,
    ) -> Dict:
        result = self._request_raw_with_token(
            method="GET",
            path=f"/open-apis/drive/v1/medias/{resource_token}/download",
            params={"type": resource_type},
        )
        data = result.get("data") or {}
        content = data.get("content") if isinstance(data, dict) else None
        if output_path and isinstance(content, (bytes, bytearray)):
            with open(output_path, "wb") as f:
                f.write(content)
            return self._wrap_result(code=result.get("code", 0), msg=result.get("msg", ""), data={"output_path": output_path})
        return self._wrap_result(code=result.get("code", 0), msg=result.get("msg", ""), data={"content": content})
