# memos_api.py
#
# Copyright 2025 Rishi Ghan
#
# SPDX-License-Identifier: GPL-3.0-or-later

import requests
from typing import Optional, Dict, Any, Tuple, List


class MemosAPI:
    """Simple Memos API client using Bearer token authentication"""

    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }

    def test_connection(self) -> Tuple[bool, str]:
        """Test if we can connect to the Memos server"""
        try:
            response = requests.get(
                f'{self.base_url}/api/v1/memos',
                headers=self.headers,
                params={'pageSize': 1},
                timeout=10
            )
            if response.status_code == 200:
                return True, "Connected successfully"
            else:
                return False, f"HTTP {response.status_code}"
        except requests.exceptions.Timeout:
            return False, "Connection timed out"
        except requests.exceptions.ConnectionError:
            return False, "Could not connect to server"
        except Exception as e:
            return False, str(e)

    def get_user_info(self) -> Optional[Dict[str, Any]]:
        """Get current user information"""
        try:
            response = requests.get(
                f'{self.base_url}/api/v1/user/me',
                headers=self.headers,
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
            return None
        except:
            return None

    def get_memos(self, page_size: int = 50, page_token: str = None) -> Tuple[bool, List[Dict[str, Any]], str]:
        """Get list of memos with pagination - NO attachment fetching here"""
        try:
            params = {'pageSize': page_size}
            if page_token:
                params['pageToken'] = page_token

            response = requests.get(
                f'{self.base_url}/api/v1/memos',
                headers=self.headers,
                params=params,
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                memos = data.get('memos', [])
                next_page_token = data.get('nextPageToken', None)
                return True, memos, next_page_token
            return False, [], None
        except:
            return False, [], None

    def get_memo_attachments(self, memo_name: str) -> List[Dict[str, Any]]:
        """Get attachments for a specific memo"""
        try:
            url = f'{self.base_url}/api/v1/{memo_name}/attachments'
            response = requests.get(
                url,
                headers=self.headers,
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                return data.get('attachments', [])
            return []
        except:
            return []
