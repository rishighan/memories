# memos_api.py
#
# Copyright 2025 Rishi Ghan
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import requests
from typing import Optional, Dict, Any, Tuple


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
