"""Send file tool for sending files to users."""

from pathlib import Path
from typing import Any, Callable, Awaitable

from nanobot.agent.tools.base import Tool
from nanobot.bus.events import OutboundMessage


class SendFileTool(Tool):
    """Tool to send files (images, documents) to users on chat channels."""
    
    def __init__(
        self, 
        send_callback: Callable[[OutboundMessage], Awaitable[None]] | None = None,
        default_channel: str = "",
        default_chat_id: str = ""
    ):
        self._send_callback = send_callback
        self._default_channel = default_channel
        self._default_chat_id = default_chat_id
    
    def set_context(self, channel: str, chat_id: str) -> None:
        """Set the current message context."""
        self._default_channel = channel
        self._default_chat_id = chat_id
    
    def set_send_callback(self, callback: Callable[[OutboundMessage], Awaitable[None]]) -> None:
        """Set the callback for sending messages."""
        self._send_callback = callback
    
    @property
    def name(self) -> str:
        return "send_file"
    
    @property
    def description(self) -> str:
        return (
            "Send a file (image, document, etc.) to the user. "
            "Use this when the user wants to receive a file from the local filesystem."
        )
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute path to the file to send"
                },
                "caption": {
                    "type": "string",
                    "description": "Optional caption/message to accompany the file"
                },
                "channel": {
                    "type": "string",
                    "description": "Optional: target channel (telegram, discord, etc.)"
                },
                "chat_id": {
                    "type": "string",
                    "description": "Optional: target chat/user ID"
                }
            },
            "required": ["path"]
        }
    
    async def execute(
        self, 
        path: str,
        caption: str = "",
        channel: str | None = None, 
        chat_id: str | None = None,
        **kwargs: Any
    ) -> str:
        channel = channel or self._default_channel
        chat_id = chat_id or self._default_chat_id

        if not channel or not chat_id:
            return "Error: No target channel/chat specified"
        
        if not self._send_callback:
            return "Error: Message sending not configured"
        
        # Validate file exists
        file_path = Path(path)
        if not file_path.exists():
            return f"Error: File not found: {path}"
        
        if not file_path.is_file():
            return f"Error: Path is not a file: {path}"
        
        msg = OutboundMessage(
            channel=channel,
            chat_id=chat_id,
            content=caption,
            media=[str(file_path.absolute())]
        )
        
        try:
            await self._send_callback(msg)
            return f"File '{file_path.name}' sent to {channel}:{chat_id}"
        except Exception as e:
            return f"Error sending file: {str(e)}"
