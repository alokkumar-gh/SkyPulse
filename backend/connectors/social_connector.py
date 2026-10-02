import time
import logging
from typing import Any, Dict, List, Optional
import httpx

from connectors.base import BaseConnector
from connectors.schema import CanonicalRawEvent, ConnectorStatusEnum

logger = logging.getLogger("skypulse.connectors.social")


class SocialFeedConnector(BaseConnector):
    """
    Public/Authorized social media and microblogging feed connector (e.g. Mastodon, Bluesky,
    or authorized public Twitter/X weather monitoring endpoints).
    Requires explicit API bearer token; otherwise status is gracefully reported as NOT_CONFIGURED.
    """

    def __init__(
        self,
        source_id: str,
        name: str = "Authorized Public Weather Dispatches",
        api_token: Optional[str] = None,
        endpoint_url: Optional[str] = None,
    ):
        super().__init__(
            source_id=source_id,
            name=name,
            source_type="PUBLIC_DATASET",
            config={"endpoint_url": endpoint_url},
            is_demo=False,
        )
        self.api_token = api_token
        self.endpoint_url = endpoint_url
        self.status = (
            ConnectorStatusEnum.HEALTHY
            if (api_token and endpoint_url)
            else ConnectorStatusEnum.NOT_CONFIGURED
        )

    async def poll(self) -> List[CanonicalRawEvent]:
        if not self.api_token or not self.endpoint_url:
            self.status = ConnectorStatusEnum.NOT_CONFIGURED
            return []

        t0 = time.time()
        events: List[CanonicalRawEvent] = []

        headers = {"Authorization": f"Bearer {self.api_token}"}
        try:
            async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
                resp = await client.get(self.endpoint_url)
                if resp.status_code == 200:
                    data = resp.json()
                    posts = data.get("posts", data.get("statuses", []))
                    for p in posts:
                        events.append(self.parse(p))
                    self.record_success(len(events), (time.time() - t0) * 1000)
                else:
                    self.record_error(f"Social feed returned HTTP {resp.status_code}")
        except Exception as e:
            self.record_error(e)

        return events

    def parse(self, raw_post: Dict[str, Any]) -> CanonicalRawEvent:
        post_id = str(raw_post.get("id", f"post-{hash(str(raw_post))}"))
        content = raw_post.get("text", raw_post.get("content", ""))

        return CanonicalRawEvent(
            source_id=self.source_id,
            source_type="PUBLIC_DATASET",
            external_id=post_id,
            text=content,
            city=raw_post.get("city"),
            state=raw_post.get("state"),
            raw_payload=raw_post,
            is_demo=False,
        )
