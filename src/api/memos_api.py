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
            
    def search_memos(self, query: str, page_size: int = 50) -> Tuple[bool, List[Dict[str, Any]], str]:
        """Search memos by content"""
        try:
            # Use the v1 API format
            params = {
                'filter': f'content.contains("{query}")'
            }
            
            print(f"Searching with params: {params}")
            
            response = requests.get(
                f'{self.base_url}/api/v1/memos',
                headers=self.headers,
                params=params,
                timeout=10
            )
            
            print(f"Search response status: {response.status_code}")
            print(f"Search URL: {response.url}")
            
            if response.status_code == 200:
                data = response.json()
                memos = data.get('memos', [])
                print(f"Found {len(memos)} memos")
                next_page_token = data.get('nextPageToken', None)
                return True, memos, next_page_token
            else:
                print(f"Search failed: {response.text[:200]}")
            return False, [], None
        except Exception as e:
            print(f"Search error: {e}")
            return False, [], None

    def create_memo_with_attachments(self, content: str, attachments: list) -> Tuple[bool, Dict[str, Any]]:
        """Create a memo with attachments"""
        try:
            import base64
            import os

            # Step 1: Upload attachments first
            attachment_refs = []
            for attachment in attachments:
                file_path = attachment['file'].get_path()
                file_name = os.path.basename(file_path)

                # Read and encode file
                with open(file_path, 'rb') as f:
                    file_content = f.read()
                    content_base64 = base64.b64encode(file_content).decode('utf-8')

                # Determine MIME type
                mime_type = 'application/octet-stream'
                if file_name.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                    ext = file_name.lower().split('.')[-1]
                    if ext == 'jpg':
                        ext = 'jpeg'
                    mime_type = f'image/{ext}'

                # Create attachment
                attach_data = {
                    'filename': file_name,
                    'type': mime_type,
                    'content': content_base64
                }

                response = requests.post(
                    f'{self.base_url}/api/v1/attachments',
                    headers=self.headers,
                    json=attach_data,
                    timeout=30
                )

                if response.status_code in [200, 201]:
                    attach_result = response.json()
                    attachment_refs.append({
                        'name': attach_result.get('name', ''),
                        'filename': file_name,
                        'type': mime_type
                    })
                    print(f"Created attachment: {attach_result.get('name')}")
                else:
                    print(f"Failed to create attachment: {response.text}")

            # Step 2: Create memo
            memo_data = {
                'content': content
            }

            response = requests.post(
                f'{self.base_url}/api/v1/memos',
                headers=self.headers,
                json=memo_data,
                timeout=10
            )

            print(f"Create memo response: {response.status_code}")

            if response.status_code not in [200, 201]:
                print(f"Failed to create memo: {response.text}")
                return False, {}

            memo = response.json()
            memo_name = memo.get('name', '')

            # Step 3: Link attachments to memo
            if attachment_refs:
                attach_response = requests.patch(
                    f'{self.base_url}/api/v1/{memo_name}/attachments',
                    headers=self.headers,
                    json={
                        'attachments': attachment_refs
                    },
                    timeout=30
                )

                print(f"Link attachments response: {attach_response.status_code}")
                print(f"Link response: {attach_response.text}")

                if attach_response.status_code in [200]:
                    print(f"Successfully linked {len(attachment_refs)} files")
                else:
                    print(f"Failed to link files: {attach_response.text}")

            return True, memo

        except Exception as e:
            print(f"Error creating memo: {e}")
            import traceback
            traceback.print_exc()
            return False, {}

    def upload_file(self, file_path: str) -> Tuple[bool, str]:
        """Upload a file and return the resource name"""
        try:
            import os

            file_name = os.path.basename(file_path)

            # Determine MIME type
            mime_type = 'application/octet-stream'
            if file_name.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                ext = file_name.lower().split('.')[-1]
                if ext == 'jpg':
                    ext = 'jpeg'
                mime_type = f'image/{ext}'

            print(f"Uploading: {file_name} ({mime_type})")

            with open(file_path, 'rb') as f:
                files = {
                    'file': (file_name, f, mime_type)
                }

                # Use multipart, not JSON
                headers = {
                    'Authorization': self.headers['Authorization']
                }

                response = requests.post(
                    f'{self.base_url}/api/v1/attachments',
                    headers=headers,
                    files=files,
                    timeout=30
                )

            print(f"Upload response: {response.status_code}")
            print(f"Upload response body: {response.text}")

            if response.status_code in [200, 201]:
                attachment = response.json()
                print(f"Full attachment response: {attachment}")
                attachment_name = attachment.get('name', '')
                print(f"Uploaded attachment: {attachment_name}")
                return True, attachment_name
            else:
                print(f"Failed to upload: {response.text}")
                return False, ''
        except Exception as e:
            print(f"Error uploading file: {e}")
            import traceback
            traceback.print_exc()
            return False, ''

    def update_memo(self, memo_name: str, content: str) -> Tuple[bool, Dict[str, Any]]:
        """Update an existing memo"""
        try:
            data = {
                'content': content
            }

            response = requests.patch(
                f'{self.base_url}/api/v1/{memo_name}',
                headers=self.headers,
                json=data,
                timeout=10
            )

            print(f"Update memo response: {response.status_code}")

            if response.status_code in [200, 201]:
                memo = response.json()
                return True, memo
            else:
                print(f"Failed to update memo: {response.text}")
                return False, {}
        except Exception as e:
            print(f"Error updating memo: {e}")
            return False, {}

    def update_memo_with_attachments(self, memo_name: str, content: str, new_attachments: list, existing_attachments: list = None) -> Tuple[bool, Dict[str, Any]]:
        """Update a memo and add new attachments"""
        try:
            import base64
            import os

            # Start with existing attachments
            attachment_refs = []
            if existing_attachments:
                for attach in existing_attachments:
                    attachment_refs.append({
                        'name': attach.get('name', ''),
                        'filename': attach.get('filename', ''),
                        'type': attach.get('type', '')
                    })

            # Upload new attachments
            for attachment in new_attachments:
                file_path = attachment['file'].get_path()
                file_name = os.path.basename(file_path)

                with open(file_path, 'rb') as f:
                    file_content = f.read()
                    content_base64 = base64.b64encode(file_content).decode('utf-8')

                mime_type = 'application/octet-stream'
                if file_name.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                    ext = file_name.lower().split('.')[-1]
                    if ext == 'jpg':
                        ext = 'jpeg'
                    mime_type = f'image/{ext}'

                attach_data = {
                    'filename': file_name,
                    'type': mime_type,
                    'content': content_base64
                }

                response = requests.post(
                    f'{self.base_url}/api/v1/attachments',
                    headers=self.headers,
                    json=attach_data,
                    timeout=30
                )

                if response.status_code in [200, 201]:
                    attach_result = response.json()
                    attachment_refs.append({
                        'name': attach_result.get('name', ''),
                        'filename': file_name,
                        'type': mime_type
                    })
                    print(f"Created attachment: {attach_result.get('name')}")
                else:
                    print(f"Failed to create attachment: {response.text}")

            # Update memo content
            success, memo = self.update_memo(memo_name, content)

            if not success:
                return False, {}

            # Link ALL attachments (existing + new)
            if attachment_refs:
                attach_response = requests.patch(
                    f'{self.base_url}/api/v1/{memo_name}/attachments',
                    headers=self.headers,
                    json={'attachments': attachment_refs},
                    timeout=30
                )

                print(f"Link attachments response: {attach_response.status_code}")

                if attach_response.status_code in [200]:
                    print(f"Linked {len(attachment_refs)} attachments")
                else:
                    print(f"Failed to link attachments: {attach_response.text}")

            return True, memo

        except Exception as e:
            print(f"Error updating memo with attachments: {e}")
            import traceback
            traceback.print_exc()
            return False, {}

    def delete_memo(self, memo_name: str) -> bool:
        """Delete a memo"""
        try:
            response = requests.delete(
                f'{self.base_url}/api/v1/{memo_name}',
                headers=self.headers,
                timeout=10
            )

            print(f"Delete memo response: {response.status_code}")

            return response.status_code in [200, 204]
        except Exception as e:
            print(f"Error deleting memo: {e}")
            return False
