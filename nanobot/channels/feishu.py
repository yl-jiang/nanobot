"""Feishu/Lark channel implementation using lark-oapi SDK with WebSocket long connection."""

import asyncio
import json
import re
import threading
from collections import OrderedDict
from typing import Any

from loguru import logger

from nanobot.bus.events import OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.channels.base import BaseChannel
from nanobot.config.schema import FeishuConfig, ImageParserConfig
from nanobot.providers.image_parser import VLLMImageProvider
from nanobot.providers.transcription import GroqTranscriptionProvider
from nanobot.session.manager import SessionManager

try:
    import lark_oapi as lark
    from lark_oapi.api.im.v1 import (
        CreateFileRequest,
        CreateFileRequestBody,
        CreateImageRequest,
        CreateImageRequestBody,
        CreateMessageRequest,
        CreateMessageRequestBody,
        CreateMessageReactionRequest,
        CreateMessageReactionRequestBody,
        Emoji,
        GetMessageResourceRequest,
        P2ImMessageReceiveV1,
    )
    FEISHU_AVAILABLE = True
except ImportError:
    FEISHU_AVAILABLE = False
    lark = None
    Emoji = None

# Message type display mapping
MSG_TYPE_MAP = {
    "image": "[image]",
    "audio": "[audio]",
    "media": "[video]",
    "file": "[file]",
    "sticker": "[sticker]",
}

# Feishu msg_type to resource type mapping for download API
_RESOURCE_TYPE_MAP = {
    "image": "image",
    "audio": "file",
    "media": "file",
    "file": "file",
}

# File extension guesses by msg_type (fallback when filename is absent)
_DEFAULT_EXT_MAP = {
    "image": ".png",
    "audio": ".opus",
    "media": ".mp4",
    "file": ".bin",
}


class FeishuChannel(BaseChannel):
    """
    Feishu/Lark channel using WebSocket long connection.
    
    Uses WebSocket to receive events - no public IP or webhook required.
    
    Requires:
    - App ID and App Secret from Feishu Open Platform
    - Bot capability enabled
    - Event subscription enabled (im.message.receive_v1)
    """
    
    name = "feishu"
    
    def __init__(
        self,
        config: FeishuConfig,
        bus: MessageBus,
        groq_api_key: str | None = None,
        image_parser_config: ImageParserConfig | None = None,
        session_manager: SessionManager | None = None,
    ):
        super().__init__(config, bus)
        self.config: FeishuConfig = config
        self._client: Any = None
        self._ws_client: Any = None
        self._ws_thread: threading.Thread | None = None
        self._processed_message_ids: OrderedDict[str, None] = OrderedDict()  # Ordered dedup cache
        self._loop: asyncio.AbstractEventLoop | None = None
        self._transcriber = GroqTranscriptionProvider(api_key=groq_api_key) if groq_api_key else None
        self._image_parser = self._build_image_parser(image_parser_config)
        self.session_manager = session_manager

    @staticmethod
    def _build_image_parser(cfg: ImageParserConfig | None) -> VLLMImageProvider | None:
        """Build VLLMImageProvider from global providers.imageParser config."""
        if not cfg or not cfg.enabled:
            return None
        if not cfg.api_base or not cfg.model:
            logger.warning("Image parser enabled but api_base or model missing")
            return None
        return VLLMImageProvider(
            api_base=cfg.api_base,
            api_key=cfg.api_key or None,
            model=cfg.model,
            prompt=cfg.prompt,
            system_prompt=cfg.system_prompt,
            max_tokens=cfg.max_tokens,
            timeout_seconds=cfg.timeout_seconds,
        )
    
    async def _handle_command(self, text: str, sender_id: str, reply_to: str) -> bool:
        """Handle slash commands. Returns True if command was handled."""
        cmd = text.split()[0].lower()
        if cmd == "/reset":
            if self.session_manager is None:
                await self._send_text_reply(reply_to, "⚠️ 会话管理不可用。")
                return True
            session_key = f"{self.name}:{reply_to}"
            session = self.session_manager.get_or_create(session_key)
            msg_count = len(session.messages)
            session.clear()
            self.session_manager.save(session)
            logger.info(f"Session reset for {session_key} (cleared {msg_count} messages)")
            await self._send_text_reply(reply_to, f"🔄 对话历史已清空（共 {msg_count} 条消息），重新开始吧！")
            return True
        elif cmd == "/help":
            help_text = (
                "🐈 nanobot 命令列表\n\n"
                "/reset — 清空对话历史\n"
                "/help — 显示此帮助信息\n\n"
                "直接发送消息即可开始对话！"
            )
            await self._send_text_reply(reply_to, help_text)
            return True
        return False

    async def start(self) -> None:
        """Start the Feishu bot with WebSocket long connection."""
        if not FEISHU_AVAILABLE:
            logger.error("Feishu SDK not installed. Run: pip install lark-oapi")
            return
        
        if not self.config.app_id or not self.config.app_secret:
            logger.error("Feishu app_id and app_secret not configured")
            return
        
        self._running = True
        self._loop = asyncio.get_running_loop()
        
        # Create Lark client for sending messages
        self._client = lark.Client.builder() \
            .app_id(self.config.app_id) \
            .app_secret(self.config.app_secret) \
            .log_level(lark.LogLevel.INFO) \
            .build()
        
        # Create event handler
        # Register handlers for subscribed events; unhandled events cause SDK errors.
        event_handler = lark.EventDispatcherHandler.builder(
            self.config.encrypt_key or "",
            self.config.verification_token or "",
        ).register_p2_im_message_receive_v1(
            self._on_message_sync
        ).register_p2_im_message_message_read_v1(
            self._on_message_read
        ).register_p2_im_message_reaction_created_v1(
            self._on_reaction_created
        ).register_p2_im_message_reaction_deleted_v1(
            self._on_reaction_deleted
        ).register_p2_im_chat_access_event_bot_p2p_chat_entered_v1(
            self._on_bot_p2p_chat_entered
        ).register_p2_task_task_update_tenant_v1(
            self._on_noop_event
        ).build()
        
        # Create WebSocket client for long connection
        self._ws_client = lark.ws.Client(
            self.config.app_id,
            self.config.app_secret,
            event_handler=event_handler,
            log_level=lark.LogLevel.INFO
        )
        
        # Start WebSocket client in a separate thread
        def run_ws():
            try:
                self._ws_client.start()
            except Exception as e:
                logger.error(f"Feishu WebSocket error: {e}")
        
        self._ws_thread = threading.Thread(target=run_ws, daemon=True)
        self._ws_thread.start()
        
        logger.info("Feishu bot started with WebSocket long connection")
        logger.info("No public IP required - using WebSocket to receive events")
        
        # Keep running until stopped
        while self._running:
            await asyncio.sleep(1)
    
    async def stop(self) -> None:
        """Stop the Feishu bot."""
        self._running = False
        if self._ws_client:
            try:
                self._ws_client.stop()
            except Exception as e:
                logger.warning(f"Error stopping WebSocket client: {e}")
        logger.info("Feishu bot stopped")
    
    def _add_reaction_sync(self, message_id: str, emoji_type: str) -> None:
        """Sync helper for adding reaction (runs in thread pool)."""
        try:
            request = CreateMessageReactionRequest.builder() \
                .message_id(message_id) \
                .request_body(
                    CreateMessageReactionRequestBody.builder()
                    .reaction_type(Emoji.builder().emoji_type(emoji_type).build())
                    .build()
                ).build()
            
            response = self._client.im.v1.message_reaction.create(request)
            
            if not response.success():
                logger.warning(f"Failed to add reaction: code={response.code}, msg={response.msg}")
            else:
                logger.debug(f"Added {emoji_type} reaction to message {message_id}")
        except Exception as e:
            logger.warning(f"Error adding reaction: {e}")

    async def _add_reaction(self, message_id: str, emoji_type: str = "THUMBSUP") -> None:
        """
        Add a reaction emoji to a message (non-blocking).
        
        Common emoji types: THUMBSUP, OK, EYES, DONE, OnIt, HEART
        """
        if not self._client or not Emoji:
            return
        
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._add_reaction_sync, message_id, emoji_type)
    
    def _download_resource_sync(
        self, message_id: str, file_key: str, msg_type: str, file_name: str = "",
    ) -> str | None:
        """Download a media resource from Feishu and save to ~/.nanobot/media/."""
        from pathlib import Path

        resource_type = _RESOURCE_TYPE_MAP.get(msg_type)
        if not resource_type:
            logger.warning(f"Unsupported resource type for download: {msg_type}")
            return None

        try:
            request = GetMessageResourceRequest.builder() \
                .message_id(message_id) \
                .file_key(file_key) \
                .type(resource_type) \
                .build()
            response = self._client.im.v1.message_resource.get(request)

            if not response.success():
                logger.error(
                    f"Failed to download resource: code={response.code}, msg={response.msg}"
                )
                return None

            # Determine file name & path
            media_dir = Path.home() / ".nanobot" / "media"
            media_dir.mkdir(parents=True, exist_ok=True)

            if file_name:
                safe_name = file_name.replace("/", "_").replace("\\", "_")
            else:
                ext = _DEFAULT_EXT_MAP.get(msg_type, ".bin")
                safe_name = f"{file_key[:20]}{ext}"
            file_path = media_dir / safe_name

            # Write content
            with open(file_path, "wb") as f:
                f.write(response.file.read())

            logger.debug(f"Downloaded {msg_type} resource -> {file_path}")
            return str(file_path)

        except Exception as e:
            logger.error(f"Error downloading resource from Feishu: {e}")
            return None
    
    # Regex to match markdown tables (header + separator + data rows)
    _TABLE_RE = re.compile(
        r"((?:^[ \t]*\|.+\|[ \t]*\n)(?:^[ \t]*\|[-:\s|]+\|[ \t]*\n)(?:^[ \t]*\|.+\|[ \t]*\n?)+)",
        re.MULTILINE,
    )

    @staticmethod
    def _parse_md_table(table_text: str) -> dict | None:
        """Parse a markdown table into a Feishu table element."""
        lines = [l.strip() for l in table_text.strip().split("\n") if l.strip()]
        if len(lines) < 3:
            return None
        split = lambda l: [c.strip() for c in l.strip("|").split("|")]
        headers = split(lines[0])
        rows = [split(l) for l in lines[2:]]
        columns = [{"tag": "column", "name": f"c{i}", "display_name": h, "width": "auto"}
                   for i, h in enumerate(headers)]
        return {
            "tag": "table",
            "page_size": len(rows) + 1,
            "columns": columns,
            "rows": [{f"c{i}": r[i] if i < len(r) else "" for i in range(len(headers))} for r in rows],
        }

    # Regex to match markdown headings
    _HEADING_RE = re.compile(r"^#{1,4}\s+(.+)$", re.MULTILINE)

    @staticmethod
    def _convert_headings(text: str) -> str:
        """Convert markdown headings to bold text for Feishu compatibility."""
        return FeishuChannel._HEADING_RE.sub(r"**\1**", text)

    def _build_card_elements(self, content: str) -> list[dict]:
        """Split content into markdown + table elements for Feishu card."""
        elements, last_end = [], 0
        for m in self._TABLE_RE.finditer(content):
            before = content[last_end:m.start()].strip()
            if before:
                elements.append({"tag": "markdown", "content": self._convert_headings(before)})
            elements.append(self._parse_md_table(m.group(1)) or {"tag": "markdown", "content": m.group(1)})
            last_end = m.end()
        remaining = content[last_end:].strip()
        if remaining:
            elements.append({"tag": "markdown", "content": self._convert_headings(remaining)})
        return elements or [{"tag": "markdown", "content": self._convert_headings(content)}]

    # File extension to Feishu file_type mapping
    _FILE_TYPE_MAP = {
        ".opus": "opus", ".mp4": "mp4", ".pdf": "pdf",
        ".doc": "doc", ".xls": "xls", ".ppt": "ppt",
        ".docx": "doc", ".xlsx": "xls", ".pptx": "ppt",
    }
    _IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}

    def _upload_image_sync(self, file_path: str) -> str | None:
        """Upload an image to Feishu and return the image_key."""
        try:
            with open(file_path, "rb") as f:
                request = CreateImageRequest.builder() \
                    .request_body(
                        CreateImageRequestBody.builder()
                        .image_type("message")
                        .image(f)
                        .build()
                    ).build()
                response = self._client.im.v1.image.create(request)
            if not response.success():
                logger.error(f"Failed to upload image: code={response.code}, msg={response.msg}")
                return None
            image_key = response.data.image_key
            logger.debug(f"Uploaded image {file_path} -> {image_key}")
            return image_key
        except Exception as e:
            logger.error(f"Error uploading image to Feishu: {e}")
            return None

    def _upload_file_sync(self, file_path: str) -> str | None:
        """Upload a file to Feishu and return the file_key."""
        from pathlib import Path
        path = Path(file_path)
        ext = path.suffix.lower()
        file_type = self._FILE_TYPE_MAP.get(ext, "stream")
        try:
            with open(file_path, "rb") as f:
                request = CreateFileRequest.builder() \
                    .request_body(
                        CreateFileRequestBody.builder()
                        .file_type(file_type)
                        .file_name(path.name)
                        .file(f)
                        .build()
                    ).build()
                response = self._client.im.v1.file.create(request)
            if not response.success():
                logger.error(f"Failed to upload file: code={response.code}, msg={response.msg}")
                return None
            file_key = response.data.file_key
            logger.debug(f"Uploaded file {file_path} -> {file_key}")
            return file_key
        except Exception as e:
            logger.error(f"Error uploading file to Feishu: {e}")
            return None

    async def _send_media(self, msg: OutboundMessage) -> None:
        """Upload and send media files through Feishu."""
        from pathlib import Path

        receive_id_type = "chat_id" if msg.chat_id.startswith("oc_") else "open_id"
        loop = asyncio.get_running_loop()

        for path_str in msg.media:
            path = Path(path_str)
            if not path.exists():
                logger.warning(f"Media file not found: {path}")
                continue

            ext = path.suffix.lower()
            try:
                if ext in self._IMAGE_EXTS:
                    image_key = await loop.run_in_executor(None, self._upload_image_sync, path_str)
                    if not image_key:
                        continue
                    content = json.dumps({"image_key": image_key})
                    msg_type = "image"
                else:
                    file_key = await loop.run_in_executor(None, self._upload_file_sync, path_str)
                    if not file_key:
                        continue
                    content = json.dumps({"file_key": file_key})
                    msg_type = "file"

                request = CreateMessageRequest.builder() \
                    .receive_id_type(receive_id_type) \
                    .request_body(
                        CreateMessageRequestBody.builder()
                        .receive_id(msg.chat_id)
                        .msg_type(msg_type)
                        .content(content)
                        .build()
                    ).build()

                response = self._client.im.v1.message.create(request)
                if not response.success():
                    logger.error(
                        f"Failed to send Feishu {msg_type}: code={response.code}, msg={response.msg}"
                    )
                else:
                    logger.info(f"Sent {msg_type}: {path.name}")
            except Exception as e:
                logger.error(f"Error sending media {path.name}: {e}")

    async def _send_text_reply(self, chat_id: str, text: str) -> None:
        """Send a plain text reply to the specified chat/user."""
        if not self._client:
            return
        if chat_id.startswith("oc_"):
            receive_id_type = "chat_id"
        else:
            receive_id_type = "open_id"
        content = json.dumps({"text": text}, ensure_ascii=False)
        request = CreateMessageRequest.builder() \
            .receive_id_type(receive_id_type) \
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(chat_id)
                .msg_type("text")
                .content(content)
                .build()
            ).build()
        try:
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(None, self._client.im.v1.message.create, request)
            if not response.success():
                logger.error(f"Failed to send text reply: code={response.code}, msg={response.msg}")
        except Exception as e:
            logger.error(f"Error sending text reply: {e}")

    async def send(self, msg: OutboundMessage) -> None:
        """Send a message through Feishu."""
        if not self._client:
            logger.warning("Feishu client not initialized")
            return
        
        try:
            # Send media files if present
            if msg.media:
                logger.info(f"Sending message with {len(msg.media)} media files to {msg.chat_id}")
                await self._send_media(msg)

            # Send text content (as card with markdown/table support)
            if msg.content:
                # Determine receive_id_type based on chat_id format
                if msg.chat_id.startswith("oc_"):
                    receive_id_type = "chat_id"
                else:
                    receive_id_type = "open_id"
                
                # Build card with markdown support (headings converted to bold)
                elements = self._build_card_elements(msg.content)
                card = {
                    "config": {"wide_screen_mode": True},
                    "elements": elements,
                }
                content = json.dumps(card, ensure_ascii=False)
                
                request = CreateMessageRequest.builder() \
                    .receive_id_type(receive_id_type) \
                    .request_body(
                        CreateMessageRequestBody.builder()
                        .receive_id(msg.chat_id)
                        .msg_type("interactive")
                        .content(content)
                        .build()
                    ).build()
                
                response = self._client.im.v1.message.create(request)
                
                if not response.success():
                    logger.error(
                        f"Failed to send Feishu message: code={response.code}, "
                        f"msg={response.msg}, log_id={response.get_log_id()}"
                    )
                else:
                    logger.debug(f"Feishu message sent to {msg.chat_id}")
                
        except Exception as e:
            logger.error(f"Error sending Feishu message: {e}")
    
    def _on_message_read(self, data: Any) -> None:
        """Handle message read event."""
        pass

    def _on_reaction_created(self, data: Any) -> None:
        """Handle reaction added event."""
        pass

    def _on_reaction_deleted(self, data: Any) -> None:
        """Handle reaction removed event."""
        pass

    def _on_bot_p2p_chat_entered(self, data: Any) -> None:
        """Handle user entering bot chat event."""
        pass

    def _on_noop_event(self, data: Any) -> None:
        """No-op handler for subscribed but unused events (e.g. task updates)."""
        pass

    def _on_message_sync(self, data: "P2ImMessageReceiveV1") -> None:
        """
        Sync handler for incoming messages (called from WebSocket thread).
        Schedules async handling in the main event loop.
        """
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._on_message(data), self._loop)
    
    async def _on_message(self, data: "P2ImMessageReceiveV1") -> None:
        """Handle incoming message from Feishu (text, images, files, audio, video)."""
        try:
            event = data.event
            message = event.message
            sender = event.sender
            
            # Deduplication check
            message_id = message.message_id
            if message_id in self._processed_message_ids:
                return
            self._processed_message_ids[message_id] = None
            
            # Trim cache: keep most recent 500 when exceeds 1000
            while len(self._processed_message_ids) > 1000:
                self._processed_message_ids.popitem(last=False)
            
            # Skip bot messages
            sender_type = sender.sender_type
            if sender_type == "bot":
                return
            
            sender_id = sender.sender_id.open_id if sender.sender_id else "unknown"
            chat_id = message.chat_id
            chat_type = message.chat_type  # "p2p" or "group"
            msg_type = message.message_type
            
            # In group chats, only respond when bot is @mentioned
            if chat_type == "group":
                mentions = getattr(message, "mentions", None)
                if not mentions:
                    return
            
            # Add reaction to indicate "seen"
            await self._add_reaction(message_id, "FISTBUMP")
            
            # Parse message content & download media
            content_parts: list[str] = []
            media_paths: list[str] = []

            raw = {}
            try:
                raw = json.loads(message.content) if message.content else {}
            except json.JSONDecodeError:
                pass

            if msg_type == "text":
                text = raw.get("text", message.content or "")
                # Strip @mention placeholders (e.g. @_user_1) in group messages
                if chat_type == "group":
                    text = re.sub(r"@_user_\d+\s*", "", text).strip()
                # Handle slash commands
                if text.strip().startswith("/"):
                    reply_to = chat_id if chat_type == "group" else sender_id
                    handled = await self._handle_command(text.strip(), sender_id, reply_to)
                    if handled:
                        return
                if text:
                    content_parts.append(text)

            elif msg_type == "image":
                image_key = raw.get("image_key", "")
                if image_key:
                    loop = asyncio.get_running_loop()
                    path = await loop.run_in_executor(
                        None, self._download_resource_sync,
                        message_id, image_key, "image", "",
                    )
                    if path:
                        content_parts.append(f"[image: {path}]")
                        if self._image_parser:
                            analysis = await self._image_parser.parse(path, raw.get("text", ""))
                            if analysis:
                                content_parts.append(f"[image_analysis: {analysis}]")
                            else:
                                # Analysis failed, pass raw image to main LLM
                                media_paths.append(path)
                        else:
                            # No image parser, pass raw image to main LLM
                            media_paths.append(path)
                    else:
                        content_parts.append("[image: download failed]")
                else:
                    content_parts.append("[image]")

            elif msg_type == "file":
                file_key = raw.get("file_key", "")
                file_name = raw.get("file_name", "")
                if file_key:
                    loop = asyncio.get_running_loop()
                    path = await loop.run_in_executor(
                        None, self._download_resource_sync,
                        message_id, file_key, "file", file_name,
                    )
                    if path:
                        media_paths.append(path)
                        content_parts.append(f"[file: {path}]")
                    else:
                        content_parts.append(f"[file: download failed ({file_name})]")
                else:
                    content_parts.append("[file]")

            elif msg_type == "audio":
                file_key = raw.get("file_key", "")
                if file_key:
                    loop = asyncio.get_running_loop()
                    path = await loop.run_in_executor(
                        None, self._download_resource_sync,
                        message_id, file_key, "audio", "",
                    )
                    if path:
                        content_parts.append(f"[audio: {path}]")
                        if self._transcriber:
                            transcription = await self._transcriber.transcribe(path)
                            if transcription:
                                content_parts.append(f"[transcription: {transcription}]")
                            else:
                                media_paths.append(path)
                        else:
                            media_paths.append(path)
                    else:
                        content_parts.append("[audio: download failed]")
                else:
                    content_parts.append("[audio]")

            elif msg_type == "post":
                # Rich text (post) message: contains paragraphs with text, images, links, etc.
                # Feishu SDK already unwraps to locale level: {"title": "...", "content": [[...]]}
                title = raw.get("title", "")
                if title:
                    content_parts.append(title)
                paragraphs = raw.get("content", [])
                for paragraph in paragraphs:
                    line_parts: list[str] = []
                    for element in paragraph:
                        tag = element.get("tag", "")
                        if tag == "text":
                            line_parts.append(element.get("text", ""))
                        elif tag == "a":
                            href = element.get("href", "")
                            link_text = element.get("text", href)
                            line_parts.append(f"{link_text}({href})" if href else link_text)
                        elif tag == "at":
                            pass  # skip @mentions in post content
                        elif tag == "img":
                            image_key = element.get("image_key", "")
                            if image_key:
                                loop = asyncio.get_running_loop()
                                path = await loop.run_in_executor(
                                    None, self._download_resource_sync,
                                    message_id, image_key, "image", "",
                                )
                                if path:
                                    content_parts.append(f"[image: {path}]")
                                    if self._image_parser:
                                        analysis = await self._image_parser.parse(path, title or "")
                                        if analysis:
                                            content_parts.append(f"[image_analysis: {analysis}]")
                                        else:
                                            media_paths.append(path)
                                    else:
                                        media_paths.append(path)
                                else:
                                    content_parts.append("[image: download failed]")
                        elif tag == "media":
                            file_key = element.get("file_key", "")
                            if file_key:
                                loop = asyncio.get_running_loop()
                                path = await loop.run_in_executor(
                                    None, self._download_resource_sync,
                                    message_id, file_key, "media", element.get("file_name", ""),
                                )
                                if path:
                                    media_paths.append(path)
                                    content_parts.append(f"[video: {path}]")
                        elif tag == "emotion":
                            line_parts.append(f"[{element.get('emoji_type', 'emoji')}]")
                    if line_parts:
                        line_text = "".join(line_parts)
                        if chat_type == "group":
                            line_text = re.sub(r"@_user_\d+\s*", "", line_text).strip()
                        if line_text:
                            content_parts.append(line_text)

            elif msg_type == "media":
                # "media" is Feishu's type for video messages
                file_key = raw.get("file_key", "")
                file_name = raw.get("file_name", "")
                if file_key:
                    loop = asyncio.get_running_loop()
                    path = await loop.run_in_executor(
                        None, self._download_resource_sync,
                        message_id, file_key, "media", file_name,
                    )
                    if path:
                        media_paths.append(path)
                        content_parts.append(f"[video: {path}]")
                    else:
                        content_parts.append(f"[video: download failed]")
                else:
                    content_parts.append("[video]")

            else:
                content_parts.append(MSG_TYPE_MAP.get(msg_type, f"[{msg_type}]"))

            content = "\n".join(content_parts) if content_parts else "[empty message]"
            
            if not content.strip():
                return
            
            logger.debug(f"Feishu message from {sender_id} ({msg_type}): {content[:80]}...")
            
            # Forward to message bus
            reply_to = chat_id if chat_type == "group" else sender_id
            await self._handle_message(
                sender_id=sender_id,
                chat_id=reply_to,
                content=content,
                media=media_paths,
                metadata={
                    "message_id": message_id,
                    "chat_type": chat_type,
                    "msg_type": msg_type,
                }
            )
            
        except Exception as e:
            logger.error(f"Error processing Feishu message: {e}")
