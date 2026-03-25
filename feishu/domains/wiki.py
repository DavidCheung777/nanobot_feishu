from typing import Dict


class WikiMixin:
    def get_wiki_node(self, token: str) -> Dict:
        return self._request_with_token(
            method="GET",
            path="/open-apis/wiki/v2/spaces/get_node",
            params={"token": token},
        )
