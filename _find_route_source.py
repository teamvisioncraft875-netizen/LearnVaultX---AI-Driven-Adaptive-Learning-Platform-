from app import app
import inspect

# Create a request context to match the URL
with app.test_request_context('/api/classes/available', method='GET'):
    try:
        # Match the URL
        adapter = app.url_map.bind('', '/')
        endpoint, args = adapter.match('/api/classes/available', method='GET')
        
        print(f"Endpoint: {endpoint}")
        
        # Get the view function
        func = app.view_functions[endpoint]
        print(f"Function: {func.__name__}")
        
        # Get source location
        source_file = inspect.getsourcefile(func)
        source_lines = inspect.getsourcelines(func)
        print(f"File: {source_file}")
        print(f"Line: {source_lines[1]}")
        
    except Exception as e:
        print(f"Error finding route: {e}")
