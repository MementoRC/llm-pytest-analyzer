"""MCP resource handlers for test data and analysis results.

Implements resource handlers for the three main resource types:
- Test Results: test-results://session/{id}
- Fix Suggestions: suggestions://session/{id}
- Analysis History: history://recent
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

from mcp.types import Resource, ResourceContents, TextResourceContents

from .session_manager import SessionManager

logger = logging.getLogger(__name__)


class ResourceError(Exception):
    """Base exception for resource handling errors."""

    def __init__(self, status_code: int, message: str, details: Optional[Dict] = None):
        self.status_code = status_code
        self.message = message
        self.details = details or {}
        super().__init__(message)


class BaseResourceHandler:
    """Base class for MCP resource handlers."""

    def __init__(self, session_manager: SessionManager):
        """Initialize resource handler.

        Args:
            session_manager: Session manager instance
        """
        self.session_manager = session_manager

    def parse_uri(self, uri: str) -> Dict[str, Any]:
        """Parse resource URI and extract components.

        Args:
            uri: Resource URI to parse

        Returns:
            Dictionary with parsed URI components

        Raises:
            ResourceError: If URI format is invalid
        """
        try:
            parsed = urlparse(uri)
            return {
                "scheme": parsed.scheme,
                "path": parsed.path,
                "query": parse_qs(parsed.query),
                "netloc": parsed.netloc,
            }
        except Exception as e:
            raise ResourceError(400, f"Invalid URI format: {uri}", {"error": str(e)})

    def get_query_param(
        self, query_params: Dict[str, List[str]], key: str, default: Any = None
    ) -> Any:
        """Get query parameter value with default.

        Args:
            query_params: Parsed query parameters
            key: Parameter key
            default: Default value if key not found

        Returns:
            Parameter value or default
        """
        values = query_params.get(key, [])
        return values[0] if values else default

    def paginate_results(
        self, items: List[Any], page: int = 1, page_size: int = 50
    ) -> Dict[str, Any]:
        """Paginate a list of items.

        Args:
            items: List of items to paginate
            page: Page number (1-based)
            page_size: Number of items per page

        Returns:
            Dictionary with paginated results and metadata
        """
        total = len(items)
        start = (page - 1) * page_size
        end = start + page_size
        paginated_items = items[start:end]

        return {
            "items": paginated_items,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "pages": (total + page_size - 1) // page_size if total > 0 else 0,
                "has_next": end < total,
                "has_prev": page > 1,
            },
        }


class TestResultsResourceHandler(BaseResourceHandler):
    """Handler for test-results://session/{id} resources."""

    async def handle_request(self, uri: str) -> ResourceContents:
        """Handle test results resource request.

        Args:
            uri: Resource URI in format test-results://session/{id}

        Returns:
            Resource contents with test results data

        Raises:
            ResourceError: If session not found or URI invalid
        """
        try:
            parsed = self.parse_uri(uri)

            # Validate URI format: test-results://session/{id}
            if parsed["scheme"] != "test-results":
                raise ResourceError(400, f"Invalid scheme: {parsed['scheme']}")

            path_parts = parsed["path"].strip("/").split("/")
            if len(path_parts) != 2 or path_parts[0] != "session":
                raise ResourceError(
                    400, "Invalid URI format. Expected: test-results://session/{id}"
                )

            session_id = path_parts[1]
            session = self.session_manager.get_session(session_id)
            if not session:
                raise ResourceError(404, f"Session not found: {session_id}")

            # Parse query parameters for filtering
            query_params = parsed["query"]
            filters = {}

            # Extract filter parameters
            if "status" in query_params:
                filters["status"] = self.get_query_param(query_params, "status")
            if "type" in query_params:
                filters["type"] = self.get_query_param(query_params, "type")
            if "file" in query_params:
                filters["file"] = self.get_query_param(query_params, "file")

            # Get filtered results
            results = session.filter_test_results(filters)

            # Parse pagination parameters
            page = int(self.get_query_param(query_params, "page", "1"))
            page_size = int(self.get_query_param(query_params, "page_size", "50"))

            # Paginate results
            paginated = self.paginate_results(
                [result.__dict__ for result in results], page, page_size
            )

            # Build response
            response_data = {
                "session_id": session_id,
                "test_results": paginated["items"],
                "pagination": paginated["pagination"],
                "filters_applied": filters,
                "generated_at": time.time(),
            }

            content = json.dumps(response_data, indent=2)
            logger.info(
                f"Served test results for session {session_id}: "
                f"{len(paginated['items'])} results"
            )

            return TextResourceContents(
                uri=uri, mimeType="application/json", text=content
            )

        except ResourceError:
            raise
        except Exception as e:
            logger.error(f"Error handling test results request for {uri}: {e}")
            raise ResourceError(500, f"Internal error: {str(e)}")


class SuggestionsResourceHandler(BaseResourceHandler):
    """Handler for suggestions://session/{id} resources."""

    async def handle_request(self, uri: str) -> ResourceContents:
        """Handle suggestions resource request.

        Args:
            uri: Resource URI in format suggestions://session/{id}

        Returns:
            Resource contents with fix suggestions data

        Raises:
            ResourceError: If session not found or URI invalid
        """
        try:
            parsed = self.parse_uri(uri)

            # Validate URI format: suggestions://session/{id}
            if parsed["scheme"] != "suggestions":
                raise ResourceError(400, f"Invalid scheme: {parsed['scheme']}")

            path_parts = parsed["path"].strip("/").split("/")
            if len(path_parts) != 2 or path_parts[0] != "session":
                raise ResourceError(
                    400, "Invalid URI format. Expected: suggestions://session/{id}"
                )

            session_id = path_parts[1]
            session = self.session_manager.get_session(session_id)
            if not session:
                raise ResourceError(404, f"Session not found: {session_id}")

            # Parse query parameters for filtering
            query_params = parsed["query"]
            filters = {}

            # Extract filter parameters
            if "min_confidence" in query_params:
                filters["min_confidence"] = self.get_query_param(
                    query_params, "min_confidence"
                )
            if "failure_id" in query_params:
                filters["failure_id"] = self.get_query_param(query_params, "failure_id")

            # Get filtered suggestions
            suggestions = session.filter_suggestions(filters)

            # Parse pagination parameters
            page = int(self.get_query_param(query_params, "page", "1"))
            page_size = int(self.get_query_param(query_params, "page_size", "50"))

            # Sort by confidence score (descending) for better organization
            suggestions.sort(key=lambda s: s.confidence_score, reverse=True)

            # Paginate suggestions
            paginated = self.paginate_results(
                [suggestion.__dict__ for suggestion in suggestions], page, page_size
            )

            # Group by confidence level for better organization
            confidence_groups = {"high": [], "medium": [], "low": []}
            for suggestion in suggestions:
                if suggestion.confidence_score >= 0.8:
                    confidence_groups["high"].append(suggestion.__dict__)
                elif suggestion.confidence_score >= 0.5:
                    confidence_groups["medium"].append(suggestion.__dict__)
                else:
                    confidence_groups["low"].append(suggestion.__dict__)

            # Build response
            response_data = {
                "session_id": session_id,
                "suggestions": paginated["items"],
                "confidence_groups": confidence_groups,
                "pagination": paginated["pagination"],
                "filters_applied": filters,
                "generated_at": time.time(),
            }

            content = json.dumps(response_data, indent=2)
            logger.info(
                f"Served suggestions for session {session_id}: "
                f"{len(paginated['items'])} suggestions"
            )

            return TextResourceContents(
                uri=uri, mimeType="application/json", text=content
            )

        except ResourceError:
            raise
        except Exception as e:
            logger.error(f"Error handling suggestions request for {uri}: {e}")
            raise ResourceError(500, f"Internal error: {str(e)}")


class HistoryResourceHandler(BaseResourceHandler):
    """Handler for history://recent resources."""

    async def handle_request(self, uri: str) -> ResourceContents:
        """Handle analysis history resource request.

        Args:
            uri: Resource URI in format history://recent

        Returns:
            Resource contents with analysis history data

        Raises:
            ResourceError: If URI invalid
        """
        try:
            parsed = self.parse_uri(uri)

            # Validate URI format: history://recent
            if parsed["scheme"] != "history":
                raise ResourceError(400, f"Invalid scheme: {parsed['scheme']}")

            if parsed["path"].strip("/") != "recent":
                raise ResourceError(
                    400, "Invalid URI format. Expected: history://recent"
                )

            # Parse query parameters
            query_params = parsed["query"]

            # Parse time filtering parameters
            limit = int(self.get_query_param(query_params, "limit", "10"))
            since_hours = self.get_query_param(query_params, "since_hours")

            # Get recent sessions
            sessions = self.session_manager.get_recent_sessions(limit=limit)

            # Apply time filtering if specified
            if since_hours:
                since_timestamp = time.time() - (float(since_hours) * 3600)
                sessions = [s for s in sessions if s.updated_at >= since_timestamp]

            # Parse pagination parameters
            page = int(self.get_query_param(query_params, "page", "1"))
            page_size = int(self.get_query_param(query_params, "page_size", "20"))

            # Convert sessions to dict and paginate
            session_summaries = [session.to_dict() for session in sessions]
            paginated = self.paginate_results(session_summaries, page, page_size)

            # Build response with summary statistics
            total_failures = sum(
                s.get("test_results_count", 0) for s in session_summaries
            )
            total_suggestions = sum(
                s.get("suggestions_count", 0) for s in session_summaries
            )

            response_data = {
                "recent_sessions": paginated["items"],
                "pagination": paginated["pagination"],
                "summary": {
                    "total_sessions": len(session_summaries),
                    "total_failures": total_failures,
                    "total_suggestions": total_suggestions,
                    "active_sessions": self.session_manager.get_session_count(),
                },
                "filters_applied": {
                    "limit": limit,
                    "since_hours": since_hours,
                },
                "generated_at": time.time(),
            }

            content = json.dumps(response_data, indent=2)
            logger.info(f"Served analysis history: {len(paginated['items'])} sessions")

            return TextResourceContents(
                uri=uri, mimeType="application/json", text=content
            )

        except ResourceError:
            raise
        except Exception as e:
            logger.error(f"Error handling history request for {uri}: {e}")
            raise ResourceError(500, f"Internal error: {str(e)}")


class ResourceManager:
    """Manages all MCP resource handlers."""

    def __init__(self, session_manager: SessionManager):
        """Initialize resource manager.

        Args:
            session_manager: Session manager instance
        """
        self.session_manager = session_manager
        self.handlers = {
            "test-results": TestResultsResourceHandler(session_manager),
            "suggestions": SuggestionsResourceHandler(session_manager),
            "history": HistoryResourceHandler(session_manager),
        }

    async def list_resources(self) -> List[Resource]:
        """List available resources.

        Returns:
            List of available resource definitions
        """
        resources = []

        # Add template resources for each type
        resources.extend(
            [
                Resource(
                    uri="test-results://session/{id}",
                    name="Test Results",
                    description="Access test execution results for a specific session",
                    mimeType="application/json",
                ),
                Resource(
                    uri="suggestions://session/{id}",
                    name="Fix Suggestions",
                    description="Access fix suggestions for a specific session",
                    mimeType="application/json",
                ),
                Resource(
                    uri="history://recent",
                    name="Analysis History",
                    description="Access recent analysis sessions and history",
                    mimeType="application/json",
                ),
            ]
        )

        # Add actual session resources
        sessions = self.session_manager.get_recent_sessions(limit=100)
        for session in sessions:
            resources.extend(
                [
                    Resource(
                        uri=f"test-results://session/{session.id}",
                        name=f"Test Results - Session {session.id[:8]}",
                        description=f"Test results from session {session.id} "
                        f"({len(session.test_results)} failures)",
                        mimeType="application/json",
                    ),
                    Resource(
                        uri=f"suggestions://session/{session.id}",
                        name=f"Fix Suggestions - Session {session.id[:8]}",
                        description=f"Fix suggestions from session {session.id} "
                        f"({len(session.suggestions)} suggestions)",
                        mimeType="application/json",
                    ),
                ]
            )

        return resources

    async def read_resource(self, uri: str) -> ResourceContents:
        """Read resource contents.

        Args:
            uri: Resource URI to read

        Returns:
            Resource contents

        Raises:
            ResourceError: If resource not found or cannot be read
        """
        try:
            parsed = urlparse(uri)
            scheme = parsed.scheme

            if scheme not in self.handlers:
                raise ResourceError(404, f"Unknown resource type: {scheme}")

            handler = self.handlers[scheme]
            return await handler.handle_request(uri)

        except ResourceError:
            raise
        except Exception as e:
            logger.error(f"Error reading resource {uri}: {e}")
            raise ResourceError(500, f"Internal error: {str(e)}")


__all__ = [
    "ResourceError",
    "BaseResourceHandler",
    "TestResultsResourceHandler",
    "SuggestionsResourceHandler",
    "HistoryResourceHandler",
    "ResourceManager",
]
