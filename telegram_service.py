#!/usr/bin/env python3
"""
Telegram Service Module
Handles Telegram notifications with rate limiting and retry logic.
"""

import time
from collections import defaultdict
from typing import Dict, List
import requests
import ssl


class TelegramService:
    """Telegram service for sending notifications with rate limiting"""
    
    def __init__(self, bot_token: str, chat_ids: List[int], *, ssl_verify: bool = None, ca_bundle_path: str = None):
        """
        Initialize Telegram Service
        
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
    
    def send_message(self, chat_id: int, text: str, retry_count: int = 0, parse_mode: str = "HTML") -> bool:
        """
        Send a message to a Telegram chat with rate limiting and retry logic
        
        Args:
            chat_id: Telegram chat ID
            text: Message text to send
            retry_count: Current retry attempt (for recursive retries)
            parse_mode: Parse mode for message formatting (HTML or Markdown)
        
        Returns:
            True if message was sent successfully, False otherwise
        """
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
            
            response = requests.post(
                f"{self.telegram_api_url}/sendMessage",
                json=payload,
                timeout=10,
                verify=(self.ca_bundle_path or self.ssl_verify)
            )
            
            if response.status_code == 200:
                self.record_message_sent(chat_id)
                return True
            elif response.status_code == 429:
                # Rate limited - retry with backoff
                error_data = response.json()
                retry_after = error_data.get('parameters', {}).get('retry_after', 5)
                
                print(f"⏳ Rate limited for chat {chat_id}. Retry after {retry_after} seconds. "
                      f"Retry attempt: {retry_count + 1}/3")
                
                # Retry up to 3 times with exponential backoff
                if retry_count < 3:
                    time.sleep(retry_after)
                    return self.send_message(chat_id, text, retry_count + 1, parse_mode)
                else:
                    print(f"❌ Max retries reached for chat {chat_id}")
                    return False
            elif response.status_code == 403:
                error_data = response.json()
                print(f"❌ Failed to send to chat {chat_id}: Bot blocked or user hasn't started the bot. "
                      f"Error: {error_data.get('description', 'Unknown error')}")
                return False
            elif response.status_code == 400:
                error_data = response.json()
                print(f"❌ Failed to send to chat {chat_id}: Bad request. "
                      f"Error: {error_data.get('description', 'Unknown error')}")
                return False
            else:
                error_data = response.json() if response.content else {}
                print(f"❌ Failed to send to chat {chat_id}: Request failed with status code {response.status_code}. "
                      f"Error: {error_data.get('description', 'Unknown error')}")
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to send to chat {chat_id}: {str(e)}")
            return False
        except Exception as e:
            print(f"❌ Unexpected error sending to chat {chat_id}: {str(e)}")
            return False
    
    def send_to_all_chats(self, text: str, parse_mode: str = "HTML"):
        """Send a message to all configured chat IDs"""
        for chat_id in self.chat_ids:
            self.send_message(chat_id, text, parse_mode=parse_mode)

