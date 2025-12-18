# memos_api.py
# Memos API client: auth, CRUD, attachments, search

import requests
import base64
import os
from typing import Optional, Dict, Any, Tuple, List


class MemosAPI:
    """Memos API client with Bearer token auth"""

    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }

    # -------------------------------------------------------------------------
    # CONNECTION
    # -------------------------------------------------------------------------

    def test_connection(self) -> Tuple[bool, str]:
        """Verify server connection"""
        try:
            r = requests.get(
                f'{self.base_url}/api/v1/memos',
                headers=self.headers,
                params={'pageSize': 1},
                timeout=10
            )
            return (True, "Connected") if r.status_code == 200 else (False, f"HTTP {r.status_code}")
        except requests.exceptions.Timeout:
            return False, "Timeout"
        except requests.exceptions.ConnectionError:
            return False, "Connection failed"
        except Exception as e:
            return False, str(e)

    def get_user_info(self) -> Optional[Dict]:
        """Get current user info"""
        try:
            r = requests.get(
                f'{self.base_url}/api/v1/user/me',
                headers=self.headers,
                timeout=10
            )
            return r.json() if r.status_code == 200 else None
        except:
            return None

    # -------------------------------------------------------------------------
    # MEMOS
    # -------------------------------------------------------------------------

    def get_memos(self, page_size: int = 50, page_token: str = None) -> Tuple[bool, List[Dict], str]:
        """Fetch memos with pagination"""
        try:
            params = {'pageSize': page_size}
            if page_token:
                params['pageToken'] = page_token

            r = requests.get(
                f'{self.base_url}/api/v1/memos',
                headers=self.headers,
                params=params,
                timeout=10
            )
            if r.status_code == 200:
                data = r.json()
                return True, data.get('memos', []), data.get('nextPageToken')
            return False, [], None
        except:
            return False, [], None

    def get_memo(self, memo_name: str) -> Tuple[bool, Dict]:
        """Fetch single memo"""
        try:
            r = requests.get(
                f'{self.base_url}/api/v1/{memo_name}',
                headers=self.headers,
                timeout=10
            )
            if r.status_code == 200:
                return True, r.json()
            return False, {}
        except:
            return False, {}

    def search_memos(self, query: str) -> Tuple[bool, List[Dict], str]:
        """Search memos by content"""
        try:
            r = requests.get(
                f'{self.base_url}/api/v1/memos',
                headers=self.headers,
                params={'filter': f'content.contains("{query}")'},
                timeout=10
            )
            if r.status_code == 200:
                data = r.json()
                return True, data.get('memos', []), data.get('nextPageToken')
            return False, [], None
        except:
            return False, [], None

    def create_memo(self, content: str) -> Tuple[bool, Dict]:
        """Create memo without attachments"""
        try:
            r = requests.post(
                f'{self.base_url}/api/v1/memos',
                headers=self.headers,
                json={'content': content},
                timeout=10
            )
            return (True, r.json()) if r.status_code in [200, 201] else (False, {})
        except:
            return False, {}

    def update_memo(self, memo_name: str, content: str) -> Tuple[bool, Dict]:
        """Update memo content"""
        try:
            r = requests.patch(
                f'{self.base_url}/api/v1/{memo_name}',
                headers=self.headers,
                json={'content': content},
                timeout=10
            )
            return (True, r.json()) if r.status_code in [200, 201] else (False, {})
        except:
            return False, {}

    def delete_memo(self, memo_name: str) -> bool:
        """Delete memo"""
        try:
            r = requests.delete(
                f'{self.base_url}/api/v1/{memo_name}',
                headers=self.headers,
                timeout=10
            )
            return r.status_code in [200, 204]
        except:
            return False

    # -------------------------------------------------------------------------
    # ATTACHMENTS
    # -------------------------------------------------------------------------

    def get_memo_attachments(self, memo_name: str) -> List[Dict]:
        """Fetch attachments for a memo"""
        try:
            r = requests.get(
                f'{self.base_url}/api/v1/{memo_name}/attachments',
                headers=self.headers,
                timeout=5
            )
            return r.json().get('attachments', []) if r.status_code == 200 else []
        except:
            return []

    def _upload_attachment(self, file_path: str) -> Optional[Dict]:
        """Upload single attachment, return ref dict or None"""
        try:
            file_name = os.path.basename(file_path)
            mime_type = self._get_mime_type(file_name)

            with open(file_path, 'rb') as f:
                content_b64 = base64.b64encode(f.read()).decode('utf-8')

            r = requests.post(
                f'{self.base_url}/api/v1/attachments',
                headers=self.headers,
                json={'filename': file_name, 'type': mime_type, 'content': content_b64},
                timeout=30
            )

            if r.status_code in [200, 201]:
                result = r.json()
                return {'name': result.get('name', ''), 'filename': file_name, 'type': mime_type}
            return None
        except:
            return None

    def _link_attachments(self, memo_name: str, attachment_refs: List[Dict]) -> bool:
        """Link attachments to memo"""
        if not attachment_refs:
            return True
        try:
            r = requests.patch(
                f'{self.base_url}/api/v1/{memo_name}/attachments',
                headers=self.headers,
                json={'attachments': attachment_refs},
                timeout=30
            )
            return r.status_code == 200
        except:
            return False

    def _get_mime_type(self, filename: str) -> str:
        """Determine MIME type from filename"""
        ext = filename.lower().split('.')[-1] if '.' in filename else ''
        if ext in ['png', 'jpg', 'jpeg', 'gif', 'webp']:
            return f'image/{"jpeg" if ext == "jpg" else ext}'
        return 'application/octet-stream'

    # -------------------------------------------------------------------------
    # MEMOS WITH ATTACHMENTS
    # -------------------------------------------------------------------------

    def create_memo_with_attachments(self, content: str, attachments: list) -> Tuple[bool, Dict]:
        """Create memo and link attachments"""
        try:
            # Upload attachments
            refs = []
            for a in attachments:
                ref = self._upload_attachment(a['file'].get_path())
                if ref:
                    refs.append(ref)

            # Create memo
            success, memo = self.create_memo(content)
            if not success:
                return False, {}

            # Link attachments
            self._link_attachments(memo.get('name', ''), refs)
            return True, memo
        except:
            return False, {}

    def update_memo_with_attachments(self, memo_name: str, content: str,
                                      new_attachments: list,
                                      existing_attachments: list = None) -> Tuple[bool, Dict]:
        """Update memo content and attachments"""
        try:
            # Start with existing attachment refs
            refs = []
            if existing_attachments:
                for a in existing_attachments:
                    refs.append({
                        'name': a.get('name', ''),
                        'filename': a.get('filename', ''),
                        'type': a.get('type', '')
                    })

            # Upload new attachments
            for a in new_attachments:
                ref = self._upload_attachment(a['file'].get_path())
                if ref:
                    refs.append(ref)

            # Update memo
            success, memo = self.update_memo(memo_name, content)
            if not success:
                return False, {}

            # Link all attachments
            self._link_attachments(memo_name, refs)
            return True, memo
        except:
            return False, {}


    def get_memo_comments(self, memo_name: str) -> List[Dict]:
        """Fetch comments for a memo"""
        try:
            r = requests.get(
                f'{self.base_url}/api/v1/{memo_name}/comments',
                headers=self.headers,
                timeout=5
            )
            print(f"Comments URL: {self.base_url}/api/v1/{memo_name}/comments")
            print(f"Comments response: {r.status_code} - {r.text[:200]}")
            return r.json().get('memos', []) if r.status_code == 200 else []
        except Exception as e:
            print(f"Comments error: {e}")
            return []
