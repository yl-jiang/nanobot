"""Task retrieval tool for querying UIH Task knowledge bases."""

import json
from typing import Any

import httpx
from loguru import logger

from nanobot.agent.tools.base import Tool


class TaskRetrievalTool(Tool):
    """Query UIH Task knowledge bases via the TaskRetrieval service."""

    def __init__(self, ip: str, port: str, collection_names: list[str]):
        self._base_url = f"http://{ip}:{port}/api/v1"
        self._collection_names = collection_names

    @property
    def name(self) -> str:
        return "task_retrieval"

    @property
    def description(self) -> str:
        collections = ", ".join(self._collection_names) if self._collection_names else "none configured"
        return (
            "Query UIH internal Task knowledge bases for information retrieval. "
            "Use this tool when the user wants to search or ask questions about UIH Tasks, "
            "TFS tasks, system parameters, or related knowledge bases. "
            f"Available knowledge bases: [{collections}]. "
            "If the user does not specify which knowledge base to use, "
            "set collection_name to empty string and ask the user to choose one. "
            "IMPORTANT: Return the tool's result to the user EXACTLY as-is, "
            "do NOT summarize, rephrase, translate, or modify the content in any way."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The question or search query to send to the knowledge base",
                },
                "collection_name": {
                    "type": "string",
                    "description": (
                        f"Knowledge base to query. Available: {', '.join(self._collection_names)}. "
                        "Leave empty if the user did not specify, then ask them to choose."
                    ),
                },
            },
            "required": ["query"],
        }

    async def execute(self, query: str, collection_name: str = "", **kwargs: Any) -> str:
        if not collection_name:
            lines = ["请选择要查询的知识库："]
            for i, name in enumerate(self._collection_names, 1):
                lines.append(f"{i}. {name}")
            return "\n".join(lines)

        if collection_name not in self._collection_names:
            return (
                f"错误：未知的知识库 '{collection_name}'。"
                f"可用的知识库：{', '.join(self._collection_names)}"
            )

        try:
            payload = {
                "query": query,
                "collection_name": collection_name,
                "history": [],
            }

            # Stream SSE response — each event carries cumulative response text
            last_response = ""
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST", f"{self._base_url}/ask", json=payload
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        raw = line[6:].strip()
                        if raw == "[DONE]":
                            break
                        try:
                            event = json.loads(raw)
                            if event.get("response"):
                                last_response = event["response"]
                        except json.JSONDecodeError:
                            continue

            if not last_response:
                return f"知识库 {collection_name} 未返回结果。"

            logger.debug(f"Task retrieval from {collection_name}: {last_response[:100]}...")
            return last_response

        except httpx.HTTPStatusError as e:
            return f"查询失败 (HTTP {e.response.status_code}): {e.response.text[:200]}"
        except Exception as e:
            return f"查询出错: {str(e)}"
