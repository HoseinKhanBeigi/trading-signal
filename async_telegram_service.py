#!/usr/bin/env python3
"""
Async Telegram Service Module
Handles Telegram notifications with rate limiting using async/await.
"""

import asyncio
import time
from collections import defaultdict
from typing import Dict, List, Optional
import aiohttp
import ssl


class AsyncTelegramService:
    """Async Telegram service for sending notifications with rate limiting"""
    
    def __init__(self, bot_token: str, chat_ids: List[int], *, ssl_verify: bool = None, ca_bundle_path: str = None):
        """
        Initialize Async Telegram Service
        
        Args:
            bot_token: Telegram bot token from BotFather
            chat_ids: List of chat IDs to send messages to
            ssl_verify: Override SSL verification (defaults to config)
            ca_bundle_path: Optional custom CA bundle path
        """
        self.bot_token = bot_token
        self.chat_ids = chat_ids
        self.telegram_api_url = f"https://api.telegram.org/bot{self.bot_token}"
        
        # Rate limiting: Telegram allows 20 messages per minute per chat
        self.max_messages_per_minute = 15  # Conservative limit
        self.message_queue: Dict[int, List[float]] = defaultdict(list)  # chatId -> timestamps
        
        # Semaphore to limit concurrent requests
        self.semaphore = asyncio.Semaphore(5)  # Max 5 concurrent requests
        
        # SSL handling
        try:
            import config
            default_ssl_verify = getattr(config, "TELEGRAM_SSL_VERIFY", True)
            default_ca_bundle = getattr(config, "TELEGRAM_CA_BUNDLE_PATH", None)
        except Exception:
            default_ssl_verify = True
            default_ca_bundle = None
        self.ssl_verify = default_ssl_verify if ssl_verify is None else ssl_verify
        self.ca_bundle_path = ca_bundle_path or default_ca_bundle
        
        # Build SSL context / connector
        self._connector = self._create_connector()
        
        # Persistent session (will be initialized in start())
        self._session: Optional[aiohttp.ClientSession] = None
        self._session_lock = asyncio.Lock()
    
    def _create_connector(self) -> aiohttp.TCPConnector:
        """Create an aiohttp connector based on SSL config."""
        if not self.ssl_verify:
            # Disable verification entirely (use only if necessary)
            return aiohttp.TCPConnector(ssl=False, limit=20, ttl_dns_cache=300)
        
        # Verified SSL, possibly with a custom CA bundle
        ssl_context = ssl.create_default_context()
        if self.ca_bundle_path:
            try:
                ssl_context.load_verify_locations(self.ca_bundle_path)
            except Exception as e:
                print(f"⚠️ Failed to load custom CA bundle '{self.ca_bundle_path}': {e}. Falling back to system CAs.")
        return aiohttp.TCPConnector(ssl=ssl_context, limit=20, ttl_dns_cache=300)
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """
        Get or create the persistent session (thread-safe)
        
        Returns:
            The persistent aiohttp session
        """
        async with self._session_lock:
            if self._session is None or self._session.closed:
                timeout = aiohttp.ClientTimeout(total=15, connect=10, sock_read=10)
                self._session = aiohttp.ClientSession(
                    connector=self._connector, 
                    timeout=timeout, 
                    trust_env=True
                )
            return self._session
    
    async def start(self):
        """Initialize the persistent session"""
        await self._get_session()
    
    async def close(self):
        """Close the persistent session and cleanup"""
        async with self._session_lock:
            if self._session and not self._session.closed:
                await self._session.close()
                self._session = None
            if self._connector:
                await self._connector.close()
    
    def can_send_message(self, chat_id: int) -> bool:
        """Check if we can send a message to a chat (rate limit check)"""
        now = time.time()
        one_minute_ago = now - 60
        
        # Remove timestamps older than 1 minute
        timestamps = self.message_queue[chat_id]
        recent_timestamps = [ts for ts in timestamps if ts > one_minute_ago]
        self.message_queue[chat_id] = recent_timestamps
        
        # Check if we're under the limit
        return len(recent_timestamps) < self.max_messages_per_minute
    
    def record_message_sent(self, chat_id: int):
        """Record that a message was sent"""
        self.message_queue[chat_id].append(time.time())
    
    async def send_message(self, chat_id: int, text: str, retry_count: int = 0, 
                         parse_mode: str = "HTML") -> bool:
        """
        Send a message to a Telegram chat with rate limiting and retry logic (async)
        
        Args:
            chat_id: Telegram chat ID
            text: Message text to send
            retry_count: Current retry attempt (for recursive retries)
            parse_mode: Parse mode for message formatting (HTML or Markdown)
        
        Returns:
            True if message was sent successfully, False otherwise
        """
        async with self.semaphore:  # Limit concurrent requests
            try:
                # Check rate limit
                if not self.can_send_message(chat_id):
                    print(f"⏳ Rate limit reached for chat {chat_id}, skipping message")
                    return False
                
                payload = {
                    "chat_id": chat_id,
                    "text": text
                }
                if parse_mode:
                    payload["parse_mode"] = parse_mode
                
                # Use persistent session
                session = await self._get_session()
                return await self._send_request(session, chat_id, payload, retry_count, parse_mode)
                    
            except Exception as e:
                print(f"❌ Unexpected error sending to chat {chat_id}: {str(e)}")
                return False
    
    async def _send_request(self, session: aiohttp.ClientSession, chat_id: int, 
                           payload: dict, retry_count: int, parse_mode: str) -> bool:
        """Internal method to send HTTP request"""
        try:
            async with session.post(
                f"{self.telegram_api_url}/sendMessage",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    self.record_message_sent(chat_id)
                    return True
                elif response.status == 429:
                    # Rate limited - retry with backoff
                    error_data = await response.json()
                    retry_after = error_data.get('parameters', {}).get('retry_after', 5)
                    
                    print(f"⏳ Rate limited for chat {chat_id}. Retry after {retry_after} seconds. "
                          f"Retry attempt: {retry_count + 1}/3")
                    
                    # Retry up to 3 times with exponential backoff
                    if retry_count < 3:
                        await asyncio.sleep(retry_after)
                        # Get fresh session in case the old one was closed
                        fresh_session = await self._get_session()
                        retry_payload = payload.copy()
                        return await self._send_request(fresh_session, chat_id, retry_payload, retry_count + 1, parse_mode)
                    else:
                        print(f"❌ Max retries reached for chat {chat_id}")
                        return False
                elif response.status == 403:
                    error_data = await response.json()
                    print(f"❌ Failed to send to chat {chat_id}: Bot blocked or user hasn't started the bot. "
                          f"Error: {error_data.get('description', 'Unknown error')}")
                    return False
                elif response.status == 400:
                    error_data = await response.json()
                    print(f"❌ Failed to send to chat {chat_id}: Bad request. "
                          f"Error: {error_data.get('description', 'Unknown error')}")
                    return False
                else:
                    error_data = await response.json() if response.content_length else {}
                    print(f"❌ Failed to send to chat {chat_id}: Request failed with status code {response.status}. "
                          f"Error: {error_data.get('description', 'Unknown error')}")
                    return False
                    
        except asyncio.TimeoutError:
            print(f"❌ Timeout sending to chat {chat_id}")
            return False
        except RuntimeError as e:
            # Recover from 'Session is closed' by getting a fresh session
            if "Session is closed" in str(e) or "closed" in str(e).lower():
                if retry_count < 3:
                    await asyncio.sleep(0.5)
                    # Force session recreation
                    async with self._session_lock:
                        if self._session and not self._session.closed:
                            await self._session.close()
                        self._session = None
                    fresh_session = await self._get_session()
                    return await self._send_request(fresh_session, chat_id, payload, retry_count + 1, parse_mode)
            print(f"❌ Failed to send to chat {chat_id}: {str(e)}")
            return False
        except Exception as e:
            print(f"❌ Failed to send to chat {chat_id}: {str(e)}")
            return False
    
    async def send_to_all_chats(self, text: str, parse_mode: str = "HTML"):
        """Send a message to all configured chat IDs concurrently using persistent session"""
        tasks = [
            self.send_message(chat_id, text, parse_mode=parse_mode)
            for chat_id in self.chat_ids
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

