# app/connectors/canvas_api.py
import requests
import json
from typing import Dict, Any, Optional, List, Union
from urllib.parse import urljoin

class CanvasAPI:
    def __init__(self, config: Dict[str, Any]):
        """
        Initializes the CanvasAPI client.

        Args:
            config (Dict[str, Any]): The application configuration, expected to contain
                                     'canvas': {'base_url': '...', 'api_token': '...'}
                                     and 'class_meta': {'canvas_course_id': '...'}
        """
        self.canvas_config = config.get('canvas', {})
        self.base_url = self.canvas_config.get('base_url')
        self.api_token = self.canvas_config.get('api_token')
        
        # The course ID can also be passed per method if preferred,
        # but often it's tied to the instance of the class being processed.
        self.course_id = config.get('class_meta', {}).get('canvas_course_id')

        if not self.base_url or not self.api_token:
            raise ValueError("Canvas API base_url and api_token must be configured.")
        
        self.headers = {
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json'
        }
        print(f"CanvasAPI initialized for base URL: {self.base_url}")

    def _make_request(self, method: str, endpoint: str, params: Optional[Dict] = None, data: Optional[Dict] = None) -> Optional[Dict]:
        """
        Helper function to make requests to the Canvas API.

        Args:
            method (str): HTTP method (GET, POST, PUT, DELETE).
            endpoint (str): API endpoint path.
            params (Optional[Dict]): URL parameters.
            data (Optional[Dict]): JSON payload for POST/PUT requests.

        Returns:
            Optional[Dict]: JSON response from API, or None if an error occurs.
        """
        url = urljoin(self.base_url, endpoint)

        # --- ADD THESE DEBUG LINES ---
        print("\n--- NEW HTTP REQUEST ---")
        print(f"URL: {url}")
        print(f"Method: {method}")
        print(f"Headers: {self.headers}")
        if params:
            print(f"Params: {params}")
        if data:
            # Use json.dumps for a nicely formatted view of the payload
            print(f"Data Payload:\n{json.dumps(data, indent=2)}")
            print("------------------------\n")
        # --- END OF DEBUG LINES ---

        
        try:
            response = requests.request(method, url, headers=self.headers, params=params, json=data, timeout=30)
            response.raise_for_status()  # Raises HTTPError for bad responses (4XX or 5XX)
            
            # Some Canvas API calls might return 204 No Content on success (e.g. delete)
            if response.status_code == 204:
                return {"status": "success", "message": "Operation successful with no content."}
            return response.json()
        except requests.exceptions.HTTPError as e:
            print(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
            try:
                error_details = e.response.json()
                print(f"Error details: {json.dumps(error_details, indent=2)}")
            except json.JSONDecodeError:
                print("Could not parse error response as JSON.")
            return None
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            return None
        except json.JSONDecodeError:
            print(f"Failed to decode JSON response from {url}. Response text: {response.text[:200]}...") # Log snippet
            return None


    def get_course_pages(self, course_id: Optional[Union[str, int]] = None) -> Optional[List[Dict]]:
        """
        Lists pages in a course.

        Args:
            course_id (Optional[Union[str, int]]): The ID of the course. Defaults to self.course_id.

        Returns:
            Optional[List[Dict]]: A list of page objects, or None on error.
        """
        target_course_id = course_id or self.course_id
        if not target_course_id:
            print("Error: Course ID not provided for get_course_pages.")
            return None
        
        endpoint = f'/api/v1/courses/{target_course_id}/pages'
        # Canvas API uses pagination. For a full list, one would need to handle 'Link' headers.
        # For simplicity, this example gets the first page (default 10 items).
        # Add `params={'per_page': 100}` to get more, or implement pagination.
        return self._make_request('GET', endpoint, params={'per_page': 50})


    def create_or_update_page(self,
                              title: str,
                              body_html: str,
                              page_url: Optional[str] = None, # page_url is the 'slug' for the page
                              published: bool = False,
                              course_id: Optional[Union[str, int]] = None) -> Optional[Dict]:
        """
        Creates a new page or updates an existing one if page_url matches.
        Canvas uses the page_url (slug) to identify pages for updates via PUT.
        If page_url is not provided for creation, Canvas typically generates one from the title.

        Args:
            title (str): The title of the page.
            body_html (str): The HTML content of the page.
            page_url (Optional[str]): The URL slug for the page. If updating, this is required.
                                      If creating and not provided, Canvas may auto-generate.
            published (bool): Whether the page should be published.
            course_id (Optional[Union[str, int]]): The ID of the course. Defaults to self.course_id.

        Returns:
            Optional[Dict]: The page object from Canvas API, or None on error.
        """
        target_course_id = course_id or self.course_id
        if not target_course_id:
            print("Error: Course ID not provided for create_or_update_page.")
            return None

        payload = {
            'wiki_page': {
                'title': title,
                'body': body_html,
                'published': published,
                # Add other fields as needed: editing_roles, notify_of_update, etc.
            }
        }
        
        # To create a page, POST to /api/v1/courses/:course_id/pages
        # To update a page, PUT to /api/v1/courses/:course_id/pages/:page_url
        # This function simplifies by attempting an update if page_url is given,
        # otherwise creates. A more robust approach might first check if page exists.

        if page_url: # Attempt to update if page_url is provided
            print(f"Attempting to update page with URL/slug: {page_url}")
            endpoint = f'/api/v1/courses/{target_course_id}/pages/{page_url}'
            return self._make_request('PUT', endpoint, data=payload)
        else: # Create a new page
            print(f"Attempting to create page with title: {title}")
            endpoint = f'/api/v1/courses/{target_course_id}/pages'
            return self._make_request('POST', endpoint, data=payload)


    def create_assignment(self,
                          name: str,
                          description_html: str,
                          points_possible: Optional[float] = None,
                          due_at: Optional[str] = None, # ISO 8601 format e.g., "2025-12-31T23:59:00Z"
                          published: bool = False,
                          submission_types: Optional[List[str]] = None, # e.g., ["online_text_entry", "online_upload"]
                          course_id: Optional[Union[str, int]] = None,
                          extra_assignment_args: Optional[Dict[str, Any]] = None) -> Optional[Dict]:
        """
        Creates a new assignment in a course.

        Args:
            name (str): The name of the assignment.
            description_html (str): HTML content for the assignment's description.
            points_possible (Optional[float]): Maximum points for the assignment.
            due_at (Optional[str]): Due date in ISO 8601 format.
            published (bool): Whether the assignment should be published.
            submission_types (Optional[List[str]]): List of submission types.
            course_id (Optional[Union[str, int]]): The ID of the course. Defaults to self.course_id.
            extra_assignment_args (Optional[Dict[str, Any]]): Other assignment attributes.

        Returns:
            Optional[Dict]: The assignment object from Canvas API, or None on error.
        """
        target_course_id = course_id or self.course_id
        if not target_course_id:
            print("Error: Course ID not provided for create_assignment.")
            return None

        payload = {
            'assignment': {
                'name': name,
                'description': description_html,
                'published': published,
                'submission_types': submission_types or ['none'],
            }
        }
        if points_possible is not None:
            payload['assignment']['points_possible'] = points_possible
        if due_at:
            payload['assignment']['due_at'] = due_at
        if submission_types: # Default is usually 'none' if not specified
            payload['assignment']['submission_types'] = submission_types
        else: # Provide a sensible default if not specified, e.g. no submission needed or online text
            payload['assignment']['submission_types'] = ['none']


        if extra_assignment_args:
            payload['assignment'].update(extra_assignment_args)

        endpoint = f'/api/v1/courses/{target_course_id}/assignments'
        print(f"Attempting to create assignment: {name}")
        return self._make_request('POST', endpoint, data=payload)

    # Add methods for updating assignments, listing assignments, etc. as needed.
    # For example, to update an assignment, you'd use:
    # PUT /api/v1/courses/:course_id/assignments/:assignment_id


if __name__ == '__main__':
    print("Testing CanvasAPI (with mocked requests)...")

    # --- Mocking requests.request ---
    # This allows testing without making real API calls.
    original_requests_request = requests.request
    mock_responses = {}

    def mocked_requests_request(method, url, **kwargs):
        print(f"MOCKED {method} request to URL: {url}")
        print(f"MOCKED Headers: {kwargs.get('headers')}")
        if kwargs.get('json'):
            print(f"MOCKED JSON Payload: {json.dumps(kwargs.get('json'), indent=2)}")

        # Find a matching mock response based on method and URL
        # This is a simple mock; more sophisticated mocking might use libraries like 'responses' or 'unittest.mock'
        for (mock_method, mock_url_pattern), response_data in mock_responses.items():
            if method.upper() == mock_method and mock_url_pattern in url:
                print(f"Found mock for {method} {url} -> status {response_data['status_code']}")
                mock_response = requests.Response()
                mock_response.status_code = response_data['status_code']
                # _content needs to be bytes
                mock_response._content = json.dumps(response_data.get('json_data', {})).encode('utf-8')
                if response_data['status_code'] >= 400:
                    mock_response.reason = response_data.get('reason', 'Mocked Error')
                    raise requests.exceptions.HTTPError(response=mock_response)
                return mock_response
        
        # Default fallback if no specific mock is found
        print(f"Warning: No specific mock found for {method} {url}. Returning default success.")
        mock_response = requests.Response()
        mock_response.status_code = 200
        mock_response._content = json.dumps({"message": "Default mock success"}).encode('utf-8')
        return mock_response

    requests.request = mocked_requests_request # Monkey patch requests.request
    # --- End of Mocking ---

    dummy_config_canvas = {
        'canvas': {
            'base_url': 'https://yourinstitution.instructure.com', # Replace with your Canvas URL if you want to test URL formation
            'api_token': 'YOUR_DUMMY_API_TOKEN'
        },
        'class_meta': {
            'canvas_course_id': '12345' # Dummy course ID
        }
    }

    try:
        canvas_client = CanvasAPI(config=dummy_config_canvas)

        # --- Define Mock Responses ---
        # Key: (METHOD, URL_CONTAINS_PATTERN)
        # Value: {'status_code': ..., 'json_data': ... (optional), 'reason': ... (for errors)}
        
        # Mock for listing pages
        mock_responses[('GET', f'/api/v1/courses/{canvas_client.course_id}/pages')] = {
            'status_code': 200,
            'json_data': [
                {"id": 1, "url": "existing-page", "title": "Existing Page", "body": "<p>Old content</p>"},
                {"id": 2, "url": "another-page", "title": "Another Page", "body": "<p>Content here</p>"}
            ]
        }
        # Mock for creating a new page
        mock_responses[('POST', f'/api/v1/courses/{canvas_client.course_id}/pages')] = {
            'status_code': 201, # 201 Created
            'json_data': {"id": 3, "url": "newly-created-page", "title": "New Page Title", "body": "<p>New HTML Body</p>", "published": False}
        }
        # Mock for updating an existing page (identified by page_url)
        existing_page_url_to_update = "existing-page-to-update"
        mock_responses[('PUT', f'/api/v1/courses/{canvas_client.course_id}/pages/{existing_page_url_to_update}')] = {
            'status_code': 200,
            'json_data': {"id": 4, "url": existing_page_url_to_update, "title": "Updated Page Title", "body": "<p>Updated HTML Content</p>", "published": True}
        }
        # Mock for creating an assignment
        mock_responses[('POST', f'/api/v1/courses/{canvas_client.course_id}/assignments')] = {
            'status_code': 201,
            'json_data': {"id": 101, "name": "New Test Assignment", "description": "<p>Assignment details.</p>", "points_possible": 100, "published": False}
        }


        # --- Test Operations ---
        print("\n--- Testing get_course_pages ---")
        pages = canvas_client.get_course_pages()
        if pages:
            print(f"Retrieved {len(pages)} pages (mocked). First page title: {pages[0]['title'] if pages else 'N/A'}")
            assert len(pages) > 0

        print("\n--- Testing create_or_update_page (CREATE new) ---")
        new_page_response = canvas_client.create_or_update_page(
            title="New Page Title",
            body_html="<p>New HTML Body</p>",
            published=False
        )
        if new_page_response:
            print(f"Create page response (mocked): ID {new_page_response.get('id')}, URL {new_page_response.get('url')}")
            assert new_page_response.get('id') is not None

        print("\n--- Testing create_or_update_page (UPDATE existing) ---")
        updated_page_response = canvas_client.create_or_update_page(
            page_url=existing_page_url_to_update, # This slug must match the mock setup
            title="Updated Page Title",
            body_html="<p>Updated HTML Content</p>",
            published=True
        )
        if updated_page_response:
            print(f"Update page response (mocked): ID {updated_page_response.get('id')}, Title: {updated_page_response.get('title')}")
            assert updated_page_response.get('title') == "Updated Page Title"


        print("\n--- Testing create_assignment ---")
        new_assignment_response = canvas_client.create_assignment(
            name="New Test Assignment",
            description_html="<p>Assignment details.</p>",
            points_possible=100,
            submission_types=["online_upload"],
            published=False
        )
        if new_assignment_response:
            print(f"Create assignment response (mocked): ID {new_assignment_response.get('id')}, Name: {new_assignment_response.get('name')}")
            assert new_assignment_response.get('name') == "New Test Assignment"

        # Example of a failing request (if you set up a mock for it)
        # mock_responses[('GET', '/api/v1/courses/99999/pages')] = {'status_code': 404, 'reason': 'Not Found'}
        # print("\n--- Testing a failing request (mocked 404) ---")
        # non_existent_pages = canvas_client.get_course_pages(course_id='99999') # Should trigger HTTPError in mock
        # if non_existent_pages is None:
        #     print("Correctly handled mocked 404 error for non_existent_pages.")
        # else:
        #     print("Error: Mocked 404 for non_existent_pages was not handled as None.")


    except ValueError as e:
        print(f"Configuration error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during testing: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Restore original requests.request
        requests.request = original_requests_request
        print("\nCanvasAPI test completed (mocked).")

